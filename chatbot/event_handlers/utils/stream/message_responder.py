from telegram.constants import ParseMode
from telegram import Message as TgMessage
import asyncio
from datetime import datetime
from typing import Literal
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
    text = re.sub(r'<(?!/?)(?!(?:' + '|'.join(allowed_tags) + r')\b)[^>]+>', '', text)
    text = re.sub(r'</(?!(?:' + '|'.join(allowed_tags) + r')\b)[^>]+>', '', text)

    return text


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

    def append(self, chunk: str):
        self.buffer.append(chunk)

    def buffered_text(self):
        return self.cur_txt + "".join(self.buffer)

    def should_flush(self) -> bool:
        time_passed = (datetime.now() - self.last_sent).total_seconds()
        return time_passed >= self.THRESHOLD or len(self.buffered_text()) >= self.MAX_LENGTH

    async def flush(self):
        text = self.buffered_text()
        if len(text) > self.MAX_LENGTH:
            return  # Could add truncation or splitting
        sanitized_text = sanitize_html(text)
        await self.ai_msg.edit_text(sanitized_text, parse_mode=self.PARSE_MODE)
        self.cur_txt = text
        self.buffer.clear()
        self.last_sent = datetime.now()

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
        sanitized_chunk = sanitize_html(first_chunk)
        ai_msg = await self.tg_message.reply_text(sanitized_chunk, parse_mode=Response.PARSE_MODE)
        self.responses[message_id] = Response(
            ai_msg, type=message_type, cur_txt=first_chunk)

    async def add(self, message_id: str, chunk: str):
        response = self.responses[message_id]
        response.append(chunk)
        # if response.should_flush():
        #     await response.flush()

    async def flush_all(self):
        for response in self.responses.values():
            if response.is_stale():
                await response.flush()
