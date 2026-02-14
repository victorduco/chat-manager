from .context_extractor import ContextExtractor
from telegram.constants import ParseMode
from event_handlers.utils.stream.stream_queue import StreamQueue
from .message_responder import MessageResponder, sanitize_html
from .state_backfill import backfill_assistant_tg_message_id
import asyncio
import io
import base64
from typing import Any
from contextlib import suppress
from conversation_states.actions import Reaction, Action
from telegram import Message as TgMessage
import json
import logging


class StreamConsumer():
    queue: StreamQueue
    message_responder: MessageResponder
    tg_message: TgMessage
    thread_id: str
    chat_id: str
    chat_username: str | None

    @classmethod
    async def initialize(cls, ctx: ContextExtractor, queue: StreamQueue):
        self = cls()
        self.queue = queue
        self.tg_message = ctx.tg_message
        self.thread_id = str(ctx.thread_id)
        self.chat_id = str(ctx.chat_id)
        self.chat_username = getattr(ctx.tg_message.chat, "username", None)
        self.message_responder = MessageResponder(ctx.tg_message)
        return self

    def _build_tg_message_link(self, message_id: int) -> str | None:
        if self.chat_username:
            u = str(self.chat_username).lstrip("@").strip()
            if u:
                return f"https://t.me/{u}/{message_id}"
        s = str(self.chat_id).strip()
        if s.startswith("-100") and len(s) > 4:
            internal_id = s[4:]
            if internal_id.isdigit():
                return f"https://t.me/c/{internal_id}/{message_id}"
        return None

    async def run_messages_main(self):
        q = self.queue.messages
        while True:
            item = await q.get()
            q.task_done()
            if item is None:
                break

            if not self.message_responder.exists(item.message_id):
                if item.chunk.strip():
                    await self.message_responder.initialize(
                        message_id=item.message_id,
                        first_chunk=item.chunk,
                        # message_type=item.message_type
                    )
                else:
                    continue
            else:
                await self.message_responder.add(item.message_id, item.chunk)

    async def periodic_message_flush(self, interval=0.3):
        while True:
            await asyncio.sleep(interval)
            await self.message_responder.flush_all()

    async def run_messages(self):
        periodic_task = asyncio.create_task(self.periodic_message_flush())
        await self.run_messages_main()
        periodic_task.cancel()
        with suppress(asyncio.CancelledError):
            await periodic_task

        # Ensure final buffered chunks are flushed and persist real Telegram ids
        # for assistant text messages in LangGraph state.
        await self.message_responder.flush_all_force()
        for sent in self.message_responder.sent_text_messages():
            try:
                await backfill_assistant_tg_message_id(
                    thread_id=self.thread_id,
                    chat_id=self.chat_id,
                    tg_message_id=int(sent["tg_message_id"]),
                    tg_date_iso=sent.get("tg_date"),
                    expected_text=str(sent.get("text") or ""),
                    tg_link=self._build_tg_message_link(int(sent["tg_message_id"])),
                )
            except Exception:
                logging.exception("Failed to backfill tg_message_id for assistant text message")

    async def run_actions(self):
        q = self.queue.actions
        while True:
            item = await q.get()
            q.task_done()
            if item is None:
                break
            logging.info("Consuming action: type=%s value=%r", item.type, item.value)
            match item.type:
                case "reaction":
                    await self.reaction_responder(item)
                case "image":
                    await self.image_responder(item)
                case "voice":
                    await self.voice_responder(item)
                case "system-message":
                    await self.system_message_responder(item)
                case "restrict":
                    await self.restrict_responder(item)
                case "unrestrict":
                    await self.unrestrict_responder(item)
                # case "image":
                #     await image_responder(item)

    async def reaction_responder(self, item: Reaction):
        try:
            await self.tg_message.set_reaction(item.value)
            logging.info(f"Set reaction ok: {item.value}")
        except Exception as e:
            logging.error(f"Failed to set reaction: {item.value} error={e}", exc_info=True)

    async def system_message_responder(self, item: Action):
        text = item.value.strip()
        if not text:
            return

        sanitized_text = sanitize_html(text)
        max_length = 4096
        chunks = [sanitized_text[i:i+max_length]
                  for i in range(0, len(sanitized_text), max_length)]

        for chunk in chunks:
            sent = await self.tg_message.reply_text(
                text=f"{chunk}",
                parse_mode=ParseMode.HTML)
            try:
                await backfill_assistant_tg_message_id(
                    thread_id=self.thread_id,
                    chat_id=self.chat_id,
                    tg_message_id=int(sent.message_id),
                    tg_date_iso=sent.date.isoformat() if getattr(sent, "date", None) else None,
                    expected_text=str(chunk),
                    tg_link=self._build_tg_message_link(int(sent.message_id)),
                )
            except Exception:
                logging.exception("Failed to backfill tg_message_id for system-message chunk")

    async def image_responder(self, item: Action):
        """Send image from action payload.

        Supported payloads:
        - JSON string: {"b64_json":"...", "caption":"..."} or {"url":"..."}
        - Plain string URL (http/https)
        """
        raw = str(item.value or "").strip()
        if not raw:
            return

        payload = None
        try:
            maybe = json.loads(raw)
            if isinstance(maybe, dict):
                payload = maybe
        except Exception:
            payload = None

        try:
            if payload is None:
                # Fallback: plain URL.
                if raw.startswith("http://") or raw.startswith("https://"):
                    await self.tg_message.reply_photo(photo=raw)
                return

            caption = str(payload.get("caption") or "").strip()
            photo_url = str(payload.get("url") or payload.get("image_url") or "").strip()
            b64 = str(payload.get("b64_json") or payload.get("b64") or payload.get("base64") or "").strip()

            if b64:
                image_bytes = base64.b64decode(b64)
                bio = io.BytesIO(image_bytes)
                bio.name = "daily.png"
                await self.tg_message.reply_photo(
                    photo=bio,
                    caption=caption or None,
                    parse_mode=ParseMode.HTML if caption else None,
                )
                return

            if photo_url.startswith("http://") or photo_url.startswith("https://"):
                await self.tg_message.reply_photo(
                    photo=photo_url,
                    caption=caption or None,
                    parse_mode=ParseMode.HTML if caption else None,
                )
                return
        except Exception as e:
            logging.error(f"Failed to send image action: {e}", exc_info=True)

    async def voice_responder(self, item: Action):
        """Send voice from action payload.

        Supported payloads:
        - JSON string: {"b64":"...", "mime_type":"audio/ogg", "filename":"voice.ogg", "caption":"..."}
        - JSON string: {"url":"..."} or {"file_id":"..."}
        - Plain string URL or Telegram file_id
        """
        raw = str(item.value or "").strip()
        if not raw:
            return

        payload = None
        try:
            maybe = json.loads(raw)
            if isinstance(maybe, dict):
                payload = maybe
        except Exception:
            payload = None

        try:
            if payload is None:
                # Fallback: plain URL or file_id.
                await self.tg_message.reply_voice(voice=raw)
                return

            caption = str(payload.get("caption") or "").strip()
            voice_url = str(payload.get("url") or payload.get("voice_url") or "").strip()
            file_id = str(payload.get("file_id") or "").strip()
            b64 = str(payload.get("b64_json") or payload.get("b64") or payload.get("base64") or "").strip()
            filename = str(payload.get("filename") or "").strip() or "voice.ogg"

            if b64:
                voice_bytes = base64.b64decode(b64)
                bio = io.BytesIO(voice_bytes)
                bio.name = filename
                await self.tg_message.reply_voice(
                    voice=bio,
                    caption=caption or None,
                    parse_mode=ParseMode.HTML if caption else None,
                )
                return

            if file_id:
                await self.tg_message.reply_voice(
                    voice=file_id,
                    caption=caption or None,
                    parse_mode=ParseMode.HTML if caption else None,
                )
                return

            if voice_url.startswith("http://") or voice_url.startswith("https://"):
                await self.tg_message.reply_voice(
                    voice=voice_url,
                    caption=caption or None,
                    parse_mode=ParseMode.HTML if caption else None,
                )
                return
        except Exception as e:
            logging.error(f"Failed to send voice action: {e}", exc_info=True)

    async def restrict_responder(self, item: Action):
        """Ban user from the chat."""
        try:
            action_data = json.loads(item.value)
            user_id = action_data["user_id"]
            chat_id = action_data["chat_id"]

            await self.tg_message.bot.ban_chat_member(
                chat_id=chat_id,
                user_id=user_id
            )

            logging.info(f"Banned user {user_id} in chat {chat_id}")
        except Exception as e:
            logging.error(f"Failed to ban user: {e}", exc_info=True)

    async def unrestrict_responder(self, item: Action):
        """Unban user, allowing them to join/send again."""
        try:
            action_data = json.loads(item.value)
            user_id = action_data["user_id"]
            chat_id = action_data["chat_id"]

            await self.tg_message.bot.unban_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                only_if_banned=False
            )

            logging.info(f"Unbanned user {user_id} in chat {chat_id}")
        except Exception as e:
            logging.error(f"Failed to unban user: {e}", exc_info=True)
