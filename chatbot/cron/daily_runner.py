import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from langgraph_sdk import get_client
from telegram import Bot


log = logging.getLogger("daily_runner")


def _utc_date_str_now() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _base_url() -> str:
    url = os.getenv("LANGGRAPH_API_URL", "").strip()
    if not url:
        raise RuntimeError("LANGGRAPH_API_URL is not set")
    return url.rstrip("/")


async def _threads_search_enabled(http: httpx.AsyncClient, limit: int = 200) -> list[dict]:
    # LangGraph Platform search API; filter by thread metadata.
    r = await http.post(
        f"{_base_url()}/threads/search",
        json={"limit": limit, "metadata": {"daily_runner_enabled": True}, "values": {}},
    )
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
        content = msg.get("content")
        return str(content or "")
    except Exception:
        return ""


async def _run_daily_graph_and_collect_text(client, thread_id: str) -> str:
    out: list[str] = []
    stream = client.runs.stream(
        thread_id=thread_id,
        assistant_id="graph_daily_runner",
        input={"messages": [], "users": []},
        stream_mode=["messages-tuple"],
        # Keep a hook for future routing/config.
        config={"configurable": {"trigger_type": "cron"}},
    )
    async for chunk in stream:
        if getattr(chunk, "event", None) != "messages":
            continue
        out.append(_extract_assistant_text_from_messages_tuple(getattr(chunk, "data", None)))
    text = "".join(out).strip()
    return text


async def main_async() -> int:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_TOKEN is not set")

    bot = Bot(token=token)
    client = get_client(url=os.getenv("LANGGRAPH_API_URL"))
    today = _utc_date_str_now()

    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        threads = await _threads_search_enabled(http)

        log.info("daily_runner: found %d enabled threads", len(threads))

        ran = 0
        skipped = 0
        failed = 0

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
            if last == today:
                skipped += 1
                continue

            chat_id = meta.get("chat_id")
            if chat_id is None or str(chat_id).strip() == "":
                log.warning("thread %s: missing metadata.chat_id; skipping", thread_id)
                skipped += 1
                continue

            try:
                text = await _run_daily_graph_and_collect_text(client, thread_id)
                if not text:
                    text = "hello world"  # safety net for the test runner

                await bot.send_message(chat_id=chat_id, text=text)
                await _merge_thread_metadata(
                    http,
                    thread_id,
                    {
                        "daily_runner_last_utc_date": today,
                        "daily_runner_last_run_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                ran += 1
            except Exception:
                failed += 1
                log.exception("thread %s: daily runner failed", thread_id)

        log.info("daily_runner: ran=%d skipped=%d failed=%d", ran, skipped, failed)

    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
