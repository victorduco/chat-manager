from __future__ import annotations

import asyncio
from typing import Any
import logging

import httpx

from server.config import LANGGRAPH_API_URL


log = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _message_matches_text(msg: dict[str, Any], expected_text: str) -> bool:
    content = str(msg.get("content") or "")
    return _normalize_text(content) == _normalize_text(expected_text)


def _eligible_assistant_message(msg: dict[str, Any]) -> bool:
    if str(msg.get("type") or "") != "ai":
        return False
    name = str(msg.get("name") or "")
    if name not in {"chat_manager_responder", "intro_responder"}:
        return False
    kwargs = msg.get("additional_kwargs") or {}
    return kwargs.get("tg_message_id") is None


def _same_assistant_text(msg: dict[str, Any], expected_text: str) -> bool:
    if str(msg.get("type") or "") != "ai":
        return False
    name = str(msg.get("name") or "")
    if name not in {"chat_manager_responder", "intro_responder"}:
        return False
    return _message_matches_text(msg, expected_text)


async def backfill_assistant_tg_message_id(
    *,
    thread_id: str,
    chat_id: str,
    tg_message_id: int,
    tg_date_iso: str | None,
    expected_text: str,
    tg_link: str | None = None,
    max_attempts: int = 8,
    retry_delay_sec: float = 0.35,
) -> bool:
    """
    Update the latest assistant message in thread state with real Telegram message id.
    """
    base = (LANGGRAPH_API_URL or "").rstrip("/")
    if not base:
        return False

    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout) as http:
        for attempt in range(1, max_attempts + 1):
            state_resp = await http.get(f"{base}/threads/{thread_id}/state")
            state_resp.raise_for_status()
            state_payload = state_resp.json() or {}
            values = state_payload.get("values") or {}

            external = list(values.get("external_messages") or [])
            reasoning = list(values.get("reasoning_messages") or [])
            messages = list(values.get("messages") or [])
            last_reasoning = list(values.get("last_reasoning") or [])
            if not external and not reasoning and not messages and not last_reasoning:
                await asyncio.sleep(retry_delay_sec)
                continue

            target_msg: dict[str, Any] | None = None
            for msg in reversed(external):
                if not isinstance(msg, dict):
                    continue
                if not _eligible_assistant_message(msg):
                    continue
                if expected_text and not _message_matches_text(msg, expected_text):
                    continue
                target_msg = msg
                break

            if target_msg is None:
                for msg in reversed(reasoning):
                    if not isinstance(msg, dict):
                        continue
                    if not _eligible_assistant_message(msg):
                        continue
                    if expected_text and not _message_matches_text(msg, expected_text):
                        continue
                    target_msg = msg
                    break

            if target_msg is None:
                for msg in reversed(messages):
                    if not isinstance(msg, dict):
                        continue
                    if not _eligible_assistant_message(msg):
                        continue
                    if expected_text and not _message_matches_text(msg, expected_text):
                        continue
                    target_msg = msg
                    break

            if target_msg is None and expected_text:
                # Fallback: if exact text match failed, patch the latest eligible
                # assistant message without tg_message_id.
                for msg in reversed(external):
                    if isinstance(msg, dict) and _eligible_assistant_message(msg):
                        target_msg = msg
                        break
                if target_msg is None:
                    for msg in reversed(reasoning):
                        if isinstance(msg, dict) and _eligible_assistant_message(msg):
                            target_msg = msg
                            break
                if target_msg is None:
                    for msg in reversed(messages):
                        if isinstance(msg, dict) and _eligible_assistant_message(msg):
                            target_msg = msg
                            break

            if target_msg is None:
                await asyncio.sleep(retry_delay_sec)
                continue

            msg_id = target_msg.get("id")
            kwargs = dict(target_msg.get("additional_kwargs") or {})
            kwargs["tg_message_id"] = int(tg_message_id)
            kwargs["chat_id"] = str(chat_id)
            kwargs["tg_chat_id"] = str(chat_id)
            if tg_date_iso:
                kwargs["tg_date"] = tg_date_iso
            if tg_link:
                kwargs["tg_link"] = tg_link

            update_values: dict[str, Any] = {}
            containers = (
                ("external_messages", external),
                ("reasoning_messages", reasoning),
                ("messages", messages),
                ("last_reasoning", last_reasoning),
            )

            # Prefer strict id match, but also patch same-text assistant entries
            # in other state containers because ids can differ between projections.
            for field_name, container in containers:
                patched_items: list[dict[str, Any]] = []
                for m in container:
                    if not isinstance(m, dict):
                        continue
                    is_id_match = bool(msg_id) and (m.get("id") == msg_id)
                    is_same_text = bool(expected_text) and _same_assistant_text(m, expected_text)
                    if not (is_id_match or is_same_text):
                        continue
                    copy_msg = dict(m)
                    merged_kwargs = dict(copy_msg.get("additional_kwargs") or {})
                    merged_kwargs.update(kwargs)
                    copy_msg["additional_kwargs"] = merged_kwargs
                    patched_items.append(copy_msg)
                if patched_items:
                    update_values[field_name] = patched_items

            if not update_values:
                await asyncio.sleep(retry_delay_sec)
                continue

            upd_resp = await http.post(
                f"{base}/threads/{thread_id}/state",
                json={"values": update_values},
            )
            upd_resp.raise_for_status()

            # Verify update survived the latest checkpoint write.
            verify_resp = await http.get(f"{base}/threads/{thread_id}/state")
            verify_resp.raise_for_status()
            verify_values = (verify_resp.json() or {}).get("values") or {}
            verified = False
            for field_name in ("external_messages", "reasoning_messages", "messages", "last_reasoning"):
                for m in list(verify_values.get(field_name) or []):
                    if not isinstance(m, dict):
                        continue
                    if msg_id and m.get("id") != msg_id:
                        if not (expected_text and _same_assistant_text(m, expected_text)):
                            continue
                    v = (m.get("additional_kwargs") or {}).get("tg_message_id")
                    if v == int(tg_message_id):
                        verified = True
                        break
                if verified:
                    break

            if verified:
                log.info(
                    "Backfilled assistant tg_message_id: thread_id=%s tg_message_id=%s msg_id=%s attempt=%s",
                    thread_id,
                    tg_message_id,
                    msg_id,
                    attempt,
                )
                return True

            await asyncio.sleep(retry_delay_sec * attempt)

    return False
