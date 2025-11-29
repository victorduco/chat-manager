from conversation_states.actions import Action
from pydantic import BaseModel
import asyncio


class MessageContent(BaseModel):
    message_id: str
    chunk: str


class StreamQueue():
    def __init__(self):
        self.messages: asyncio.Queue[MessageContent] = asyncio.Queue()
        self.actions: asyncio.Queue[Action] = asyncio.Queue()
