from .context_extractor import ContextExtractor
from telegram.constants import ParseMode
from event_handlers.utils.stream.stream_queue import StreamQueue
from .message_responder import MessageResponder, sanitize_html
import asyncio
import io
import base64
from typing import Any
from conversation_states.actions import Reaction, Action
from telegram import Message as TgMessage
import json
import logging


class StreamConsumer():
    queue: StreamQueue
    message_responder: MessageResponder
    tg_message: TgMessage

    @classmethod
    async def initialize(cls, ctx: ContextExtractor, queue: StreamQueue):
        self = cls()
        self.queue = queue
        self.tg_message = ctx.tg_message
        self.message_responder = MessageResponder(ctx.tg_message)
        return self

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
        await asyncio.gather(
            self.run_messages_main(),
            self.periodic_message_flush()
        )

    async def run_actions(self):
        q = self.queue.actions
        while True:
            item = await q.get()
            q.task_done()
            if item is None:
                break
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
            await self.tg_message.reply_text(
                text=f"{chunk}",
                parse_mode=ParseMode.HTML)

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
