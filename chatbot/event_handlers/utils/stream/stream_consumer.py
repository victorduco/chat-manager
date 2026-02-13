from .context_extractor import ContextExtractor
from telegram.constants import ParseMode
from event_handlers.utils.stream.stream_queue import StreamQueue
from .message_responder import MessageResponder, sanitize_html
import asyncio
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
