#!/usr/bin/env python3
"""
Extract per-chat messages from Telegram export JSONs and build a users YAML with intro status.

Designed for large Telegram exports (hundreds of MB) and even *truncated* JSON files:
we stream-parse message objects and stop gracefully on EOF/parse errors.

Pipeline:
  1) Scan all *.json under --input-dir, find chats whose name/id matches, and write messages to JSONL
  2) Build a unique user list (name + username/telegram_id) from that JSONL
  3) Mark intro=true if a user's message contains #intro (case-insensitive)

Example:
  python scripts/telegram_intro_extract.py \
    --input-dir test_data \
    --chat-name "Test dev" \
    --out-dir out

Outputs:
  out/filtered_messages.jsonl
  out/users.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple


CHAT_MESSAGES_MARKER = '"messages": ['
PRELUDE_TAIL_MAX = 64_000  # bytes/chars kept before a "messages" section for chat header parsing
READ_CHUNK = 1 << 20  # 1 MiB


_RE_CHAT_NAME = re.compile(r'"name"\s*:\s*"([^"]+)"')
_RE_CHAT_ID = re.compile(r'"id"\s*:\s*([0-9]+)')


def _parse_chat_header(prelude_tail: str) -> Tuple[Optional[str], Optional[int]]:
    # Prelude tail ends right before '"messages": [' inside a chat object.
    # In Telegram export JSON, this area includes chat fields: name/type/id.
    names = _RE_CHAT_NAME.findall(prelude_tail)
    ids = _RE_CHAT_ID.findall(prelude_tail)
    chat_name = names[-1] if names else None
    chat_id = int(ids[-1]) if ids else None
    return chat_name, chat_id


def _skip_ws_commas(buf: str, i: int) -> int:
    n = len(buf)
    while i < n and buf[i] in " \r\n\t,":
        i += 1
    return i


def _extract_text(msg: Dict[str, Any]) -> str:
    """
    Telegram export field `text` can be:
      - string
      - list of strings / dicts {type,text}
      - empty string
    """
    t = msg.get("text")
    if isinstance(t, str):
        return t
    if isinstance(t, list):
        parts: list[str] = []
        for item in t:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                v = item.get("text")
                if isinstance(v, str):
                    parts.append(v)
        return "".join(parts)
    return ""


def _extract_user_fields(msg: Dict[str, Any]) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """
    Return (username, telegram_id, first_name, last_name).

    Telegram export typically has:
      from: "Full Name"
      from_id: "user118497177"
    No username is included in basic exports; we fall back to "user<telegram_id>".
    """
    full_name = msg.get("from") if isinstance(msg.get("from"), str) else None
    from_id = msg.get("from_id") if isinstance(msg.get("from_id"), str) else None

    telegram_id: Optional[int] = None
    if from_id:
        m = re.match(r"user(\d+)$", from_id)
        if m:
            try:
                telegram_id = int(m.group(1))
            except Exception:
                telegram_id = None

    # Prefer Telegram export stable identifier.
    # In standard Telegram exports there's usually no @username in the JSON,
    # but there is from_id like "user118497177". Use it as username so you can
    # later search/replace it to real usernames if you have a mapping.
    username = None
    if from_id and from_id.strip():
        username = from_id.strip().lstrip("@")
    else:
        # Some exports (or other data formats) might provide a username field.
        for key in ("username", "from_username", "user", "handle"):
            v = msg.get(key)
            if isinstance(v, str) and v.strip():
                username = v.strip().lstrip("@")
                break

    if not username and telegram_id is not None:
        username = f"user{telegram_id}"

    first_name = None
    last_name = None
    if full_name:
        s = " ".join(full_name.strip().split())
        if s:
            parts = s.split(" ")
            if len(parts) == 1:
                first_name = parts[0]
            else:
                first_name = parts[0]
                last_name = " ".join(parts[1:])

    return username, telegram_id, first_name, last_name


def _iter_json_files(input_dir: Path) -> Iterator[Path]:
    for p in sorted(input_dir.rglob("*.json")):
        if p.is_file():
            yield p


def _iter_chat_messages_from_telegram_export(
    path: Path,
    *,
    want_chat_name: Optional[str],
    want_chat_id: Optional[int],
) -> Iterator[Tuple[Optional[str], Optional[int], Dict[str, Any]]]:
    """
    Yield (chat_name, chat_id, message_obj) for matching chats in a Telegram export JSON.
    Streaming and tolerant to truncation.
    """
    decoder = json.JSONDecoder()
    with path.open("r", encoding="utf-8", errors="replace") as f:
        buf = ""
        eof = False

        def refill() -> None:
            nonlocal buf, eof
            if eof:
                return
            chunk = f.read(READ_CHUNK)
            if not chunk:
                eof = True
                return
            buf += chunk

        # Prime buffer
        refill()

        while True:
            if CHAT_MESSAGES_MARKER not in buf and not eof:
                refill()
                continue

            idx = buf.find(CHAT_MESSAGES_MARKER)
            if idx < 0:
                break

            prelude = buf[:idx]
            prelude_tail = prelude[-PRELUDE_TAIL_MAX:]
            chat_name, chat_id = _parse_chat_header(prelude_tail)

            # Move buffer to right after the '['
            buf = buf[idx + len(CHAT_MESSAGES_MARKER) :]

            match = True
            if want_chat_id is not None:
                match = (chat_id == want_chat_id)
            if want_chat_name is not None:
                match = match and (chat_name == want_chat_name)

            # Parse messages array: { ... }, { ... }, ... ]
            while True:
                if not buf and not eof:
                    refill()
                    continue
                if not buf and eof:
                    return

                i = _skip_ws_commas(buf, 0)
                if i >= len(buf):
                    buf = ""
                    continue

                ch = buf[i]
                if ch == "]":
                    # End of this chat's messages array
                    buf = buf[i + 1 :]
                    break

                if ch != "{":
                    # Try to resync to next object start or end bracket.
                    next_obj = buf.find("{", i + 1)
                    next_end = buf.find("]", i + 1)
                    if next_end != -1 and (next_obj == -1 or next_end < next_obj):
                        buf = buf[next_end + 1 :]
                        break
                    if next_obj == -1:
                        buf = ""
                        continue
                    buf = buf[next_obj:]
                    continue

                # We have an object start at i.
                while True:
                    try:
                        obj, j = decoder.raw_decode(buf, i)
                        buf = buf[j:]
                        if match and isinstance(obj, dict):
                            yield (chat_name, chat_id, obj)
                        break
                    except json.JSONDecodeError as e:
                        # Need more data (likely at buffer end).
                        if not eof and e.pos >= len(buf) - 1:
                            refill()
                            continue
                        # Malformed object (or truncated mid-object). Try to resync.
                        if eof:
                            return
                        next_obj = buf.find("{", i + 1)
                        if next_obj == -1:
                            buf = ""
                            break
                        buf = buf[next_obj:]
                        i = 0
                        break


def _jsonl_write(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def _jsonl_iter(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


def _yaml_scalar(s: Any) -> str:
    if s is None:
        return "null"
    if isinstance(s, bool):
        return "true" if s else "false"
    if isinstance(s, int):
        return str(s)
    if not isinstance(s, str):
        s = str(s)
    # Keep it readable; quote only if needed.
    if s == "" or any(c in s for c in [":", "#", "\n", "\r", "\t", '"', "'"]) or s.strip() != s:
        return json.dumps(s, ensure_ascii=False)
    return s


def _write_users_yaml(path: Path, users: list[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for u in users:
            f.write("- username: ")
            f.write(_yaml_scalar(u.get("username")))
            f.write("\n")
            if u.get("telegram_id") is not None:
                f.write("  telegram_id: ")
                f.write(_yaml_scalar(u.get("telegram_id")))
                f.write("\n")
            f.write("  first_name: ")
            f.write(_yaml_scalar(u.get("first_name") or u.get("username") or ""))
            f.write("\n")
            if u.get("last_name") is not None:
                f.write("  last_name: ")
                f.write(_yaml_scalar(u.get("last_name")))
                f.write("\n")
            f.write("  intro: ")
            f.write(_yaml_scalar(bool(u.get("intro"))))
            f.write("\n\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, help="Directory with Telegram export JSON files")
    ap.add_argument("--chat-name", default=None, help="Exact chat/channel name to filter (e.g. 'Test dev')")
    ap.add_argument("--chat-id", default=None, type=int, help="Chat/channel numeric id to filter")
    ap.add_argument("--out-dir", default="out_intro", help="Output directory")
    ap.add_argument("--tag", default="#intro", help="Intro tag to search for (default: #intro)")
    ap.add_argument(
        "--count-only",
        action="store_true",
        help="Only count messages for the selected chat(s); do not write outputs.",
    )

    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    filtered_jsonl = out_dir / "filtered_messages.jsonl"
    users_yaml = out_dir / "users.yaml"

    want_name = args.chat_name
    want_id = args.chat_id
    tag = str(args.tag or "#intro")
    tag_l = tag.lower()

    if want_name is None and want_id is None:
        ap.error("Provide --chat-name and/or --chat-id")

    if args.count_only:
        total = 0
        by_type: Dict[str, int] = {}
        last_seen: Tuple[Optional[str], Optional[int]] = (None, None)
        for p in _iter_json_files(input_dir):
            for chat_name, chat_id, msg in _iter_chat_messages_from_telegram_export(
                p, want_chat_name=want_name, want_chat_id=want_id
            ):
                if not isinstance(msg, dict):
                    continue
                total += 1
                t = msg.get("type")
                if isinstance(t, str):
                    by_type[t] = by_type.get(t, 0) + 1
                last_seen = (chat_name, chat_id)

        chat_name, chat_id = last_seen
        print(f"chat_name={chat_name!r} chat_id={chat_id}")
        print(f"total_items_in_messages_array={total}")
        if by_type:
            # Print stable order.
            for k in sorted(by_type.keys()):
                print(f"type.{k}={by_type[k]}")
        return 0

    # Stage 1: extract and filter messages -> JSONL
    def rows() -> Iterator[Dict[str, Any]]:
        for p in _iter_json_files(input_dir):
            for chat_name, chat_id, msg in _iter_chat_messages_from_telegram_export(
                p, want_chat_name=want_name, want_chat_id=want_id
            ):
                yield {
                    "source_file": str(p),
                    "chat_name": chat_name,
                    "chat_id": chat_id,
                    "message": msg,
                }

    _jsonl_write(filtered_jsonl, rows())

    # Stage 2 + 3: build unique users + intro status
    users_by_key: Dict[str, Dict[str, Any]] = {}

    for row in _jsonl_iter(filtered_jsonl):
        msg = row.get("message")
        if not isinstance(msg, dict):
            continue
        if msg.get("type") != "message":
            continue
        username, telegram_id, first_name, last_name = _extract_user_fields(msg)
        if not username and telegram_id is None:
            continue

        key = username or f"tg:{telegram_id}"
        u = users_by_key.get(key)
        if u is None:
            u = {
                "username": username or "",
                "telegram_id": telegram_id,
                "first_name": first_name or (username or ""),
                "last_name": last_name,
                "intro": False,
            }
            users_by_key[key] = u
        else:
            # Fill in missing fields.
            if not u.get("first_name") and first_name:
                u["first_name"] = first_name
            if u.get("last_name") is None and last_name:
                u["last_name"] = last_name
            if u.get("telegram_id") is None and telegram_id is not None:
                u["telegram_id"] = telegram_id

        text = _extract_text(msg)
        if tag_l in (text or "").lower():
            u["intro"] = True

    users = list(users_by_key.values())
    users.sort(key=lambda x: (str(x.get("last_name") or ""), str(x.get("first_name") or ""), str(x.get("username") or "")))
    _write_users_yaml(users_yaml, users)

    print(f"Wrote {filtered_jsonl}")
    print(f"Wrote {users_yaml} (users={len(users)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
