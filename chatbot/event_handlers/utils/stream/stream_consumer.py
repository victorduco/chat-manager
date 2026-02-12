from .context_extractor import ContextExtractor
from telegram.constants import ParseMode
from event_handlers.utils.stream.stream_queue import StreamQueue
from .message_responder import MessageResponder, sanitize_html
import asyncio
from typing import Any
from conversation_states.actions import Reaction, Action
from telegram import Message as TgMessage, ChatPermissions
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
                case "system-message":
                    await self.system_message_responder(item)
                case "restrict":
                    await self.restrict_responder(item)
                case "unrestrict":
                    await self.unrestrict_responder(item)
                # case "image":
                #     await image_responder(item)

    async def reaction_responder(self, item: Reaction):
        await self.tg_message.set_reaction(item.value)

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

    async def restrict_responder(self, item: Action):
        """Restrict user from sending messages in the chat."""
        try:
            # Parse restrict action value
            restrict_data = json.loads(item.value)
            user_id = restrict_data["user_id"]
            chat_id = restrict_data["chat_id"]

            # Restrict permissions: user cannot send messages
            permissions = ChatPermissions(
                can_send_messages=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            )

            # Apply restriction using Telegram bot API
            await self.tg_message.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions
            )

            logging.info(f"Restricted user {user_id} in chat {chat_id}")
        except Exception as e:
            logging.error(f"Failed to restrict user: {e}", exc_info=True)

    async def unrestrict_responder(self, item: Action):
        """Unrestrict user, allowing them to send messages again."""
        try:
            # Parse unrestrict action value
            restrict_data = json.loads(item.value)
            user_id = restrict_data["user_id"]
            chat_id = restrict_data["chat_id"]

            # Allow all permissions again
            permissions = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )

            # Remove restriction
            await self.tg_message.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                permissions=permissions
            )

            logging.info(f"Unrestricted user {user_id} in chat {chat_id}")
        except Exception as e:
            logging.error(f"Failed to unrestrict user: {e}", exc_info=True)
