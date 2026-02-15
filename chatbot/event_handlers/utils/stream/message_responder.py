from telegram.constants import ParseMode
from telegram import Message as TgMessage
import asyncio
from datetime import datetime
from typing import Dict, Literal
import re
import html


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML for Telegram by removing or fixing problematic tags.
    Telegram supports only: <b>, <strong>, <i>, <em>, <u>, <ins>, <s>, <strike>, <del>,
    <span class="tg-spoiler">, <tg-spoiler>, <a href="">, <tg-emoji emoji-id="">, <code>, <pre>
    """
    if not text:
        return text

    # Remove unclosed or problematic blockquote tags
    text = re.sub(r'</?blockquote[^>]*>', '', text)

    # Remove any other unsupported HTML tags while keeping their content
    # Keep only Telegram-supported tags
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre', 'a', 'span']

    # Remove unsupported opening/closing tags but keep content
    text = re.sub(r'<(?!/?)(?!(?:' + '|'.join(allowed_tags) + r')\b)[^>]*>', '', text)
    text = re.sub(r'</(?!(?:' + '|'.join(allowed_tags) + r')\b)[^>]*>', '', text)

    # Protect allowed tags, escape all other raw HTML chars, then restore tags.
    # This prevents plain-text fragments like "> ^ <" from being parsed as HTML.
    protected_tags: list[str] = []

    def _protect_tag(match: re.Match[str]) -> str:
        protected_tags.append(match.group(0))
        return f"__TG_TAG_{len(protected_tags) - 1}__"

    allowed_tag_pattern = re.compile(r'</?(?:' + '|'.join(allowed_tags) + r')\b[^>]*>')
    text = allowed_tag_pattern.sub(_protect_tag, text)
    text = html.escape(text, quote=False)

    for idx, tag in enumerate(protected_tags):
        text = text.replace(f"__TG_TAG_{idx}__", tag)

    return text


def _split_text(text: str, max_len: int) -> list[str]:
    raw = str(text or "")
    if not raw:
        return [""]
    parts: list[str] = []
    cursor = raw
    while cursor:
        parts.append(cursor[:max_len])
        cursor = cursor[max_len:]
    return parts


# === Response: object for a single message_id ===
class Response:
    THRESHOLD = 0.4
    PARSE_MODE = ParseMode.HTML
    MAX_LENGTH = 4000

    def __init__(self, ai_msg: TgMessage, type: Literal["text", "long", "action-response"] = "text", cur_txt=""):
        self.ai_msg = ai_msg
        self.type = type
        self.cur_txt = cur_txt
        self.last_sent = datetime.now()
        self.buffer = []
        self.flushed_once = False

    def append(self, chunk: str):
        self.buffer.append(chunk)

    def buffered_text(self):
        return self.cur_txt + "".join(self.buffer)

    def should_flush(self) -> bool:
        time_passed = (datetime.now() - self.last_sent).total_seconds()
        return time_passed >= self.THRESHOLD or len(self.buffered_text()) >= self.MAX_LENGTH

    async def flush(self):
        text = self.buffered_text()
        parts = _split_text(text, self.MAX_LENGTH)
        sanitized_text = sanitize_html(parts[0])
        await self.ai_msg.edit_text(sanitized_text, parse_mode=self.PARSE_MODE)
        if len(parts) > 1:
            for part in parts[1:]:
                await self.ai_msg.reply_text(
                    sanitize_html(part),
                    parse_mode=self.PARSE_MODE,
                )
        self.cur_txt = text
        self.buffer.clear()
        self.last_sent = datetime.now()
        self.flushed_once = True

    def is_stale(self, timeout: float = 2.0) -> bool:
        if not self.buffer:
            return False
        return (datetime.now() - self.last_sent).total_seconds() >= timeout


# === MessageResponder: manager for all message_id ===
class MessageResponder:
    responses: dict[Response]
    tg_message: TgMessage

    def __init__(self, tg_message):
        self.responses: Dict[str, Response] = {}
        self.tg_message = tg_message

    def exists(self, message_id: str) -> bool:
        return message_id in self.responses

    async def initialize(self, message_id: str, first_chunk: str, message_type: str = "text"):
        first_parts = _split_text(first_chunk, Response.MAX_LENGTH)
        ai_msg = await self.tg_message.reply_text(
            sanitize_html(first_parts[0]),
            parse_mode=Response.PARSE_MODE,
        )
        self.responses[message_id] = Response(
            ai_msg, type=message_type, cur_txt=first_parts[0]
        )
        if len(first_parts) > 1:
            # Keep remaining content in the normal flush path.
            self.responses[message_id].append("".join(first_parts[1:]))

    async def add(self, message_id: str, chunk: str):
        response = self.responses[message_id]
        response.append(chunk)
        # if response.should_flush():
        #     await response.flush()

    async def flush_all(self):
        for response in self.responses.values():
            if response.is_stale():
                await response.flush()

    async def flush_all_force(self):
        for response in self.responses.values():
            if response.buffer:
                await response.flush()

    def sent_text_messages(self):
        out = []
        for run_id, response in self.responses.items():
            text = str(response.cur_txt or "")
            tg_message_id = getattr(response.ai_msg, "message_id", None)
            tg_date = getattr(response.ai_msg, "date", None)
            if not tg_message_id or not text:
                continue
            out.append({
                "run_id": run_id,
                "text": text,
                "tg_message_id": int(tg_message_id),
                "tg_date": tg_date.isoformat() if tg_date else None,
            })
        return out
