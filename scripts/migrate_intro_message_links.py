#!/usr/bin/env python3
"""
Backfill users[*].intro_message in LangGraph thread state from #intro messages.

How it works (per thread):
1) Read thread metadata and state.
2) Find the latest human message per user containing #intro.
3) Build a Telegram link for that message.
4) Upsert only changed users via /upsert_users admin command.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_API_URL = "https://langgraph-server-611bd1822796.herokuapp.com"
INTRO_TAG_RE = re.compile(r"(?i)(?<!\w)#intro\b")


@dataclass
class IntroHit:
    username: str
    message_id: int | None
    chat_id: str | None
    tg_link: str | None


def _base_url(cli_url: str | None) -> str:
    raw = cli_url or os.getenv("LANGGRAPH_API_URL") or DEFAULT_API_URL
    return raw.rstrip("/")


def _to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text
    return str(content or "")


def _build_tg_link(*, chat_id: str | None, message_id: int | None) -> str | None:
    if not chat_id or not message_id:
        return None
    s = str(chat_id).strip()
    if s.startswith("-100") and len(s) > 4:
        internal_id = s[4:]
        if internal_id.isdigit():
            return f"https://t.me/c/{internal_id}/{message_id}"
    return None


def _b64url_encode(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii")
    return token.rstrip("=")


def _get_json(session: requests.Session, url: str) -> dict[str, Any]:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object JSON from {url}, got {type(data)}")
    return data


def _extract_intro_hits(state: dict[str, Any], thread_chat_id: str | None) -> dict[str, IntroHit]:
    values = state.get("values") if isinstance(state, dict) else {}
    messages = values.get("messages") if isinstance(values, dict) else []
    if not isinstance(messages, list):
        return {}

    hits: dict[str, IntroHit] = {}
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type")
        if msg_type != "human":
            continue

        username = str(msg.get("name") or "").strip()
        if not username:
            continue

        text = _to_text(msg.get("content"))
        if not INTRO_TAG_RE.search(text):
            continue

        kwargs = msg.get("additional_kwargs")
        kwargs = kwargs if isinstance(kwargs, dict) else {}
        raw_mid = kwargs.get("tg_message_id")
        try:
            message_id = int(raw_mid) if raw_mid is not None else None
        except (TypeError, ValueError):
            message_id = None

        message_chat_id = kwargs.get("chat_id") or kwargs.get("tg_chat_id") or thread_chat_id
        message_chat_id = str(message_chat_id) if message_chat_id is not None else None
        tg_link = kwargs.get("tg_link")
        tg_link = str(tg_link).strip() if isinstance(tg_link, str) and tg_link.strip() else None
        if tg_link is None:
            tg_link = _build_tg_link(chat_id=message_chat_id, message_id=message_id)

        hits[username] = IntroHit(
            username=username,
            message_id=message_id,
            chat_id=message_chat_id,
            tg_link=tg_link,
        )
    return hits


def _changed_users(users: list[dict[str, Any]], hits: dict[str, IntroHit]) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    for user in users:
        if not isinstance(user, dict):
            continue
        username = str(user.get("username") or "").strip()
        if not username:
            continue
        hit = hits.get(username)
        if hit is None or not hit.tg_link:
            continue
        current_intro = user.get("intro_message")
        current_intro = str(current_intro).strip() if isinstance(current_intro, str) else ""
        if current_intro == hit.tg_link:
            continue

        changed.append(
            {
                "username": username,
                "first_name": user.get("first_name") or username,
                "last_name": user.get("last_name"),
                "preferred_name": user.get("preferred_name"),
                "intro_completed": bool(user.get("intro_completed", False)),
                "telegram_id": user.get("telegram_id"),
                "information": user.get("information") if isinstance(user.get("information"), dict) else {},
                "intro_message": hit.tg_link,
            }
        )
    return changed


def _run_upsert(session: requests.Session, base_url: str, thread_id: str, changed_users: list[dict[str, Any]]) -> None:
    payload = {"users": changed_users}
    token = _b64url_encode(payload)
    cmd = f"/upsert_users {token}"

    body = {
        "assistant_id": "graph_router",
        "input": {
            "messages": [
                {
                    "type": "human",
                    "name": "admin_panel",
                    "content": cmd,
                }
            ]
        },
        "metadata": {
            "source": "migration-script",
            "command": "upsert_users",
        },
    }
    r = session.post(f"{base_url}/threads/{thread_id}/runs/wait", json=body, timeout=60)
    r.raise_for_status()


def process_thread(session: requests.Session, base_url: str, thread_id: str, apply: bool) -> bool:
    thread = _get_json(session, f"{base_url}/threads/{thread_id}")
    state = _get_json(session, f"{base_url}/threads/{thread_id}/state")
    metadata = thread.get("metadata") if isinstance(thread, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    chat_id = metadata.get("chat_id")
    chat_id = str(chat_id) if chat_id is not None else None

    values = state.get("values") if isinstance(state, dict) else {}
    users = values.get("users") if isinstance(values, dict) else []
    if not isinstance(users, list):
        users = []

    hits = _extract_intro_hits(state, thread_chat_id=chat_id)
    changed = _changed_users(users, hits)

    print(f"\nThread: {thread_id}")
    print(f"Users in state: {len(users)}")
    print(f"Users with detected #intro: {len(hits)}")
    print(f"Users to update intro_message: {len(changed)}")

    if changed:
        for u in changed:
            print(f"  - @{u['username']} -> {u['intro_message']}")

    if not apply:
        print("Dry run only (no writes).")
        return True

    if not changed:
        print("Nothing to update.")
        return True

    _run_upsert(session, base_url, thread_id, changed)
    print("Applied via /upsert_users.")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill intro_message from last #intro messages.")
    ap.add_argument(
        "--thread-id",
        action="append",
        required=True,
        help="LangGraph thread UUID. Repeat flag for multiple threads.",
    )
    ap.add_argument(
        "--api-url",
        default=None,
        help=f"LangGraph API URL (default env LANGGRAPH_API_URL or {DEFAULT_API_URL})",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default is dry-run).",
    )
    args = ap.parse_args()

    base_url = _base_url(args.api_url)
    print(f"API: {base_url}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    ok = True
    for thread_id in args.thread_id:
        try:
            process_thread(session, base_url, thread_id.strip(), apply=args.apply)
        except Exception as exc:
            ok = False
            print(f"\nThread failed: {thread_id}\nError: {exc}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
