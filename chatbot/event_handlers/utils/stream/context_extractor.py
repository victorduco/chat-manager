from pydantic import BaseModel
from datetime import datetime
from telegram.ext import ContextTypes
from telegram import Message as TgMessage
from telegram import Update, User, Chat
from typing import Literal, Optional, Any
from langchain_core.messages import HumanMessage
import uuid
from conversation_states.humans import Human


class ContextExtractor(BaseModel):
    message: HumanMessage
    tg_message: Any
    user: Human
    content_type: Literal["text", "command"]
    chat_id: str
    thread_id: str

    @classmethod
    def from_update(cls, update: Update, context: ContextTypes.DEFAULT_TYPE, content_type: Literal["text", "command"]):
        user_data = update.message.from_user
        chat_id = str(update.message.chat.id)
        tg_message = update.message
        thread_id = cls.chat_to_thread(chat_id)
        ctx_class = cls(
            chat_id=chat_id,
            thread_id=thread_id,
            tg_message=tg_message,
            message=HumanMessage(
                content=str(update.message.text),
                type="human",
                name=user_data.username
            ),
            user=Human(
                username=user_data.username,
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
