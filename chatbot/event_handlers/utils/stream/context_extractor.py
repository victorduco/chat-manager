from pydantic import BaseModel
from telegram.ext import ContextTypes
from telegram import Message as TgMessage
from telegram import Update, User, Chat
from typing import Literal, Optional, Any
from langchain_core.messages import HumanMessage
import uuid
from conversation_states.humans import Human
from datetime import datetime, timezone


class ContextExtractor(BaseModel):
    message: HumanMessage
    tg_message: Any
    user: Human
    content_type: Literal["text", "command"]
    chat_id: str
    thread_id: str

    @classmethod
    def from_update(cls, update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: Literal["text", "command"]):
        # Handle different update types (message, edited_message, channel_post, etc.)
        tg_message = update.message or update.edited_message or update.channel_post or update.edited_channel_post
        if not tg_message:
            raise ValueError("Update does not contain a message")

        user_data = tg_message.from_user
        chat_id = str(tg_message.chat.id)
        chat_username = getattr(tg_message.chat, "username", None)
        thread_id = cls.chat_to_thread(chat_id)
        username = user_data.username or f"user{user_data.id}"
        message_id = getattr(tg_message, "message_id", None)
        tg_date = getattr(tg_message, "date", None)
        if isinstance(tg_date, datetime) and tg_date.tzinfo is None:
            tg_date = tg_date.replace(tzinfo=timezone.utc)
        reply_to_message = getattr(tg_message, "reply_to_message", None)
        reply_to_message_id = getattr(reply_to_message, "message_id", None)
        reply_to_user = getattr(reply_to_message, "from_user", None)
        reply_to_username = getattr(reply_to_user, "username", None) if reply_to_user else None
        reply_to_user_id = getattr(reply_to_user, "id", None) if reply_to_user else None
        reply_to_text = getattr(reply_to_message, "text", None)

        msg_link = cls._build_tg_message_link(
            chat_id=chat_id,
            chat_username=chat_username,
            message_id=message_id,
        )
        reply_link = cls._build_tg_message_link(
            chat_id=chat_id,
            chat_username=chat_username,
            message_id=reply_to_message_id,
        )
        ctx_class = cls(
            chat_id=chat_id,
            thread_id=thread_id,
            tg_message=tg_message,
            message=HumanMessage(
                content=str(tg_message.text),
                type="human",
                name=username,
                additional_kwargs={
                    "chat_id": chat_id,
                    "tg_chat_id": chat_id,
                    "tg_user_id": str(user_data.id),
                    "tg_message_id": message_id,
                    "tg_date": tg_date.isoformat() if isinstance(tg_date, datetime) else None,
                    "tg_link": msg_link,
                    "tg_reply_to_message_id": reply_to_message_id,
                    "tg_reply_to_link": reply_link,
                    "tg_reply_to_username": reply_to_username,
                    "tg_reply_to_user_id": str(reply_to_user_id) if reply_to_user_id is not None else None,
                    "tg_reply_to_text": str(reply_to_text) if reply_to_text is not None else None,
                },
            ),
            user=Human(
                username=username,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                telegram_id=user_data.id,
            ),
            content_type=content_type,
        )

        return ctx_class

    def get_user_name(self):
        return str(self.user.first_name + self.user.last_name)

    @staticmethod
    def chat_to_thread(chat_id) -> str:
        NAME_SPACE: str = "12345678-1234-5678-1234-567812345678"
        namespace = uuid.UUID(NAME_SPACE)
        return str(uuid.uuid5(namespace, chat_id))

    def get_graph_id(self):
        if self.content_type == "command":
            return "graph_router"
        else:
            return "graph_supervisor"

    @staticmethod
    def _build_tg_message_link(*, chat_id: str, chat_username: Optional[str], message_id: Optional[int]) -> Optional[str]:
        """Best-effort link to a Telegram message.

        - Public chats: https://t.me/<username>/<message_id>
        - Private supergroups: https://t.me/c/<internal_id>/<message_id> where internal_id is chat_id without "-100"
        """
        if not message_id:
            return None

        if chat_username:
            u = str(chat_username).lstrip("@").strip()
            if u:
                return f"https://t.me/{u}/{message_id}"

        # Supergroup/chat id: -1001234567890 -> internal_id: 1234567890
        s = str(chat_id).strip()
        if s.startswith("-100") and len(s) > 4:
            internal_id = s[4:]
            if internal_id.isdigit():
                return f"https://t.me/c/{internal_id}/{message_id}"

        return None
