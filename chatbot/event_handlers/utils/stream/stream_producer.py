from server.config import LANGGRAPH_API_URL, DISPATCHER_ASSISTANT_ID
from typing import AsyncIterator, Union
from langgraph_sdk import get_client
from langgraph_sdk.client import LangGraphClient
import asyncio
from langchain_core.messages import HumanMessage
from telegram import Message as TgMessage
from conversation_states.actions import Action
from conversation_states.states import ExternalState
from pydantic import BaseModel
from .context_extractor import ContextExtractor
import traceback
import logging
from event_handlers.utils.stream.stream_queue import StreamQueue, MessageContent
from pydantic import TypeAdapter


class StreamProducer():
    client: LangGraphClient
    ctx: ContextExtractor
    queue: StreamQueue
    thread: object
    stream: object

    def __init__(self):
        pass

    @classmethod
    async def initialize(cls, ctx: ContextExtractor, queue: StreamQueue):
        self = cls()
        self.client = get_client(url=LANGGRAPH_API_URL)
        self.ctx = ctx
        self.queue = queue
        self.thread, self.stream = await cls.prep_stream(self.client, self.ctx)
        return self

    @staticmethod
    async def _get_dispatch_graph_id(client: LangGraphClient, thread_id: str) -> str | None:
        """Return per-thread dispatch target from LangGraph thread metadata."""
        try:
            t = await client.threads.get(thread_id)
            meta = (t or {}).get("metadata") or {}
            v = meta.get("dispatch_graph_id")
            if v is None:
                return None
            v = str(v).strip()
            return v if v else None
        except Exception:
            # Best-effort: if we can't read metadata, fall back to default behavior.
            return None

    @staticmethod
    async def prep_stream(client, ctx):
        thread = await client.threads.create(
            thread_id=ctx.thread_id,
            graph_id=ctx.get_graph_id(),
            if_exists="do_nothing"
        )
        dispatch_graph_id = await StreamProducer._get_dispatch_graph_id(client, thread["thread_id"])
        state = ExternalState()
        state.messages = [ctx.message]
        state.users = [ctx.user]

        assistant_id = ctx.get_graph_id()
        config = None
        if dispatch_graph_id and DISPATCHER_ASSISTANT_ID:
            assistant_id = DISPATCHER_ASSISTANT_ID
            config = {"configurable": {"dispatch_graph_id": dispatch_graph_id}}

        stream = client.runs.stream(
            thread_id=thread["thread_id"],
            assistant_id=assistant_id,
            input=state,
            stream_mode=["messages-tuple", "custom"],
            config=config,
        )
        return thread, stream

    async def run(self):
        # run stream
        try:
            async for chunk in self.stream:
                if chunk.event == "messages":
                    await self.queue_message(chunk.data)
                if chunk.event == "custom":
                    await self.queue_action(chunk.data)
        except Exception as e:
            logging.error("Stream processing failed", exc_info=True)

            if hasattr(e, "response"):
                logging.error(f"Status code: {e.response.status_code}")
                try:
                    response_json = await e.response.json()
                    logging.error(f"Response JSON: {response_json}")
                except:
                    raw_response = await e.response.aread()
                    logging.error(f"Raw response: {raw_response}")
        await asyncio.gather(self.queue.messages.put(None),
                             self.queue.actions.put(None))

    async def queue_message(self, data):
        queue_chunk = self.get_chunk_text(data)
        if queue_chunk:
            if queue_chunk != "":
                await self.queue.messages.put(queue_chunk)

    async def queue_action(self, data):
        action_data = data["actions"][0]
        action = Action(**action_data)
        await self.queue.actions.put(action)
        pass

    def get_chunk_text(self, data):
        try:
            content = data[0]["content"]
            node = data[1]["langgraph_node"]
            # todo check what id to use
            message_id = data[1]["run_id"]

        except (KeyError, IndexError, TypeError, AttributeError):
            return False

        # Skip metadata nodes
        if node in ["__start__", "__end__"]:
            return False

        queue_chunk = MessageContent(
            message_id=message_id, chunk=content)
        return queue_chunk
