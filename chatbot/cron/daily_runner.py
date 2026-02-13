import asyncio
import logging
import os
import json
import io
import base64
from datetime import datetime, timezone

import httpx
from langgraph_sdk import get_client
from telegram import Bot
from telegram.constants import ParseMode

from server.config import DEV_ENV


log = logging.getLogger("daily_runner")


def _utc_date_str_now() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _base_url() -> str:
    url = os.getenv("LANGGRAPH_API_URL", "").strip()
    if not url:
        raise RuntimeError("LANGGRAPH_API_URL is not set")
    return url.rstrip("/")


async def _threads_search_enabled(http: httpx.AsyncClient, limit: int = 200) -> list[dict]:
    return await _threads_search(http, metadata={"daily_runner_enabled": True}, limit=limit)


async def _threads_search(http: httpx.AsyncClient, metadata: dict, limit: int = 200) -> list[dict]:
    # LangGraph Platform search API; filter by thread metadata.
    r = await http.post(f"{_base_url()}/threads/search", json={"limit": limit, "metadata": metadata, "values": {}})
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected /threads/search response: {type(data)}")
    return data


async def _get_thread(http: httpx.AsyncClient, thread_id: str) -> dict:
    r = await http.get(f"{_base_url()}/threads/{thread_id}")
    r.raise_for_status()
    return r.json()


async def _merge_thread_metadata(http: httpx.AsyncClient, thread_id: str, partial: dict) -> None:
    t = await _get_thread(http, thread_id)
    current = (t or {}).get("metadata") or {}
    if not isinstance(current, dict):
        current = {}
    next_meta = {**current, **(partial or {})}
    r = await http.patch(f"{_base_url()}/threads/{thread_id}", json={"metadata": next_meta})
    r.raise_for_status()


def _extract_assistant_text_from_messages_tuple(data) -> str:
    # Stream "messages-tuple" chunks are typically [message, meta].
    # See chatbot/event_handlers/utils/stream/stream_producer.py for a similar parser.
    try:
        msg = data[0] if isinstance(data, (list, tuple)) else None
        if not isinstance(msg, dict):
            return ""
        msg_type = msg.get("type")
        if msg_type not in ("ai", "AIMessage", "AIMessageChunk"):
            return ""
        # Filter to the final digest message emitted by the daily runner graph.
        # This avoids leaking intermediate model outputs (e.g. JSON scaffolding) into Telegram.
        if (msg.get("name") or "").strip() != "daily_runner":
            return ""
        content = msg.get("content")
        return str(content or "")
    except Exception:
        return ""


def _extract_actions_from_custom(data) -> list[dict]:
    try:
        if not isinstance(data, dict):
            return []
        actions = data.get("actions")
        if not isinstance(actions, list):
            return []
        return [a for a in actions if isinstance(a, dict)]
    except Exception:
        return []


def _parse_image_action_value(value: object) -> tuple[bytes | None, str | None]:
    """Return (image_bytes, caption)."""
    if value is None:
        return None, None
    raw = str(value)
    payload = None
    try:
        maybe = json.loads(raw)
        if isinstance(maybe, dict):
            payload = maybe
    except Exception:
        payload = None

    if payload is None:
        # Unsupported in daily runner sender: plain URL/file_id are skipped.
        return None, None

    caption = str(payload.get("caption") or "").strip() or None
    b64 = str(payload.get("b64_json") or payload.get("b64") or payload.get("base64") or "").strip()
    if not b64:
        return None, caption
    try:
        return base64.b64decode(b64), caption
    except Exception:
        return None, caption


def _parse_voice_action_value(value: object) -> tuple[bytes | None, str | None]:
    """Return (voice_bytes, caption)."""
    if value is None:
        return None, None
    raw = str(value)
    payload = None
    try:
        maybe = json.loads(raw)
        if isinstance(maybe, dict):
            payload = maybe
    except Exception:
        payload = None

    if payload is None:
        # Unsupported in daily runner sender: plain URL/file_id are skipped.
        return None, None

    caption = str(payload.get("caption") or "").strip() or None
    b64 = str(payload.get("b64_json") or payload.get("b64") or payload.get("base64") or "").strip()
    if not b64:
        return None, caption
    try:
        return base64.b64decode(b64), caption
    except Exception:
        return None, caption


async def _run_daily_graph_and_collect_output(client, thread_id: str, assistant_id: str) -> tuple[str, list[dict]]:
    out: list[str] = []
    actions: list[dict] = []
    stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        input={"messages": [], "users": []},
        stream_mode=["messages-tuple", "custom"],
        # Keep a hook for future routing/config.
        config={"configurable": {"trigger_type": "cron"}},
    )
    async for chunk in stream:
        event = getattr(chunk, "event", None)
        if event == "messages":
            text = _extract_assistant_text_from_messages_tuple(getattr(chunk, "data", None))
            if text:
                out.append(text)
        elif event == "custom":
            actions.extend(_extract_actions_from_custom(getattr(chunk, "data", None)))
    text = "".join(out).strip()
    return text, actions


async def run_daily(
    *,
    only_enabled: bool = True,
    limit: int = 200,
    force: bool = False,
    bootstrap_enable_n: int = 0,
    assistant_id: str = "graph_daily_runner",
) -> dict:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN is not set")

    bot = Bot(token=token)
    client = get_client(url=os.getenv("LANGGRAPH_API_URL"))
    today = _utc_date_str_now()

    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        threads = (
            await _threads_search_enabled(http, limit=limit)
            if only_enabled
            else await _threads_search(http, metadata={}, limit=limit)
        )

        # Optional dev helper: auto-enable the first N threads that have chat_id set.
        # This makes local testing easy without touching metadata manually.
        bootstrapped: list[str] = []
        if bootstrap_enable_n > 0:
            for t in threads:
                if len(bootstrapped) >= bootstrap_enable_n:
                    break
                thread_id = (t or {}).get("thread_id")
                if not thread_id:
                    continue
                meta = (t or {}).get("metadata") or {}
                if not isinstance(meta, dict):
                    meta = {}
                if meta.get("daily_runner_enabled") is True:
                    continue
                if not str(meta.get("chat_id") or "").strip():
                    continue
                await _merge_thread_metadata(
                    http,
                    thread_id,
                    {"daily_runner_enabled": True, "daily_runner_last_utc_date": ""},
                )
                bootstrapped.append(thread_id)

        if only_enabled:
            # If we bootstrapped, we need the enabled list refreshed to include them.
            if bootstrapped:
                threads = await _threads_search_enabled(http, limit=limit)

        log.info(
            "daily_runner: threads=%d only_enabled=%s bootstrapped=%d force=%s",
            len(threads),
            only_enabled,
            len(bootstrapped),
            force,
        )

        ran = 0
        skipped = 0
        failed = 0
        processed: list[str] = []

        for t in threads:
            thread_id = (t or {}).get("thread_id")
            if not thread_id:
                continue

            try:
                thread_info = await _get_thread(http, thread_id)
            except Exception:
                failed += 1
                log.exception("thread %s: failed to fetch thread info", thread_id)
                continue

            meta = (thread_info or {}).get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}

            last = str(meta.get("daily_runner_last_utc_date") or "").strip()
            if (not force) and last == today:
                skipped += 1
                continue

            chat_id = meta.get("chat_id")
            if chat_id is None or str(chat_id).strip() == "":
                log.warning("thread %s: missing metadata.chat_id; skipping", thread_id)
                skipped += 1
                continue

            try:
                # Collect assistant output; fall back to a deterministic string.
                text, actions = await _run_daily_graph_and_collect_output(client, thread_id, assistant_id)
                if text.strip() == "__NO_UPDATES__":
                    # In prod: send nothing. In dev: send a minimal marker.
                    if DEV_ENV:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="[dev] нет апдейтов",
                        )
                        ran += 1
                        processed.append(thread_id)
                    else:
                        skipped += 1

                    await _merge_thread_metadata(
                        http,
                        thread_id,
                        {
                            "daily_runner_last_utc_date": today,
                            "daily_runner_last_run_at": datetime.now(timezone.utc).isoformat(),
                            "daily_runner_last_had_updates": False,
                        },
                    )
                    continue

                if not text:
                    text = "hello world"  # safety net

                log.info(
                    "thread %s: sendMessage chat_id=%s preview=%r",
                    thread_id,
                    chat_id,
                    text[:500],
                )
                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                log.info("thread %s: sendMessage ok", thread_id)

                # Optional image from custom action emitted by daily runner graph.
                image_sent = False
                for a in actions:
                    if str(a.get("type") or "") != "image":
                        continue
                    img_bytes, caption = _parse_image_action_value(a.get("value"))
                    if not img_bytes:
                        log.info("thread %s: image action without bytes; skipping", thread_id)
                        continue
                    log.info("thread %s: sendPhoto chat_id=%s", thread_id, chat_id)
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=io.BytesIO(img_bytes),
                        caption=caption or None,
                        parse_mode=ParseMode.HTML if caption else None,
                    )
                    log.info("thread %s: sendPhoto ok", thread_id)
                    image_sent = True
                    break
                if not image_sent:
                    log.info("thread %s: no image sent", thread_id)

                # Optional voice from custom action emitted by daily runner graph.
                voice_sent = False
                for a in actions:
                    if str(a.get("type") or "") != "voice":
                        continue
                    voice_bytes, caption = _parse_voice_action_value(a.get("value"))
                    if not voice_bytes:
                        log.info("thread %s: voice action without bytes; skipping", thread_id)
                        continue
                    log.info("thread %s: sendVoice chat_id=%s", thread_id, chat_id)
                    bio = io.BytesIO(voice_bytes)
                    bio.name = "daily_digest.ogg"
                    await bot.send_voice(
                        chat_id=chat_id,
                        voice=bio,
                        caption=caption or None,
                        parse_mode=ParseMode.HTML if caption else None,
                    )
                    log.info("thread %s: sendVoice ok", thread_id)
                    voice_sent = True
                    break
                if not voice_sent:
                    log.info("thread %s: no voice sent", thread_id)

                await _merge_thread_metadata(
                    http,
                    thread_id,
                    {
                        "daily_runner_last_utc_date": today,
                        "daily_runner_last_run_at": datetime.now(timezone.utc).isoformat(),
                        "daily_runner_last_had_updates": True,
                        "daily_runner_last_sent_image": bool(image_sent),
                        "daily_runner_last_sent_voice": bool(voice_sent),
                    },
                )
                ran += 1
                processed.append(thread_id)
            except Exception:
                failed += 1
                log.exception("thread %s: daily runner failed", thread_id)

        log.info("daily_runner: ran=%d skipped=%d failed=%d", ran, skipped, failed)

    return {
        "ran": ran,
        "skipped": skipped,
        "failed": failed,
        "processed_thread_ids": processed,
    }


async def main_async() -> int:
    await run_daily()
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
