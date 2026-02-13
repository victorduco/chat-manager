from server.config import LANGGRAPH_API_URL
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
import httpx


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
    async def _get_thread_target_graph_id(client: LangGraphClient, thread_id: str) -> str | None:
        """Return per-thread target graph id from LangGraph thread metadata."""
        try:
            t = await client.threads.get(thread_id)
            meta = (t or {}).get("metadata") or {}
            for key in ("dispatch_graph_id", "target_graph_id", "graph_id"):
                v = meta.get(key)
                if v is None:
                    continue
                v = str(v).strip()
                if v:
                    return v
            return None
        except Exception:
            # Best-effort: if we can't read metadata, fall back to default behavior.
            return None

    @staticmethod
    async def prep_stream(client, ctx):
        # New threads default to the dispatcher graph so they are safe-by-default
        # until per-thread routing (metadata.dispatch_graph_id) is configured.
        requested_graph_id = "graph_router" if ctx.content_type == "command" else "graph_dispatcher"

        thread = await client.threads.create(
            thread_id=ctx.thread_id,
            graph_id=requested_graph_id,
            if_exists="do_nothing",
        )

        # Best-effort: store Telegram chat id and title on the LangGraph thread so cron jobs can
        # message the right chat later and admin panel can show chat info.
        try:
            chat_title = getattr(ctx.tg_message.chat, "title", None) or getattr(ctx.tg_message.chat, "username", None)
            metadata_update = {"chat_id": str(ctx.chat_id)}
            if chat_title:
                metadata_update["chat_title"] = str(chat_title)
            await StreamProducer._merge_thread_metadata_http(
                thread_id=thread["thread_id"],
                partial=metadata_update,
            )
        except Exception:
            logging.debug("Failed to persist chat_id/chat_title to thread metadata", exc_info=True)

        dispatch_graph_id = await StreamProducer._get_thread_target_graph_id(client, thread["thread_id"])
        state = ExternalState()
        state.messages = [ctx.message]
        state.users = [ctx.user]

        # If per-thread routing is configured, run that graph directly.
        # This preserves StreamWriter/custom events (reactions, actions) inside the target graph.
        assistant_id = dispatch_graph_id or (thread.get("graph_id") or requested_graph_id)
        config = None

        stream = client.runs.stream(
            thread_id=thread["thread_id"],
            assistant_id=assistant_id,
            input=state,
            stream_mode=["messages-tuple", "custom"],
            config=config,
        )
        return thread, stream

    @staticmethod
    async def _merge_thread_metadata_http(thread_id: str, partial: dict) -> None:
        """Merge metadata onto a thread via raw HTTP (SDK surface differs by version)."""
        base = (LANGGRAPH_API_URL or "").rstrip("/")
        if not base:
            raise RuntimeError("LANGGRAPH_API_URL is not set")

        timeout = httpx.Timeout(10.0)
        async with httpx.AsyncClient(timeout=timeout) as http:
            t = (await http.get(f"{base}/threads/{thread_id}")).json()
            current = (t or {}).get("metadata") or {}
            if not isinstance(current, dict):
                current = {}
            next_meta = {**current, **(partial or {})}
            r = await http.patch(f"{base}/threads/{thread_id}", json={"metadata": next_meta})
            r.raise_for_status()

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
            msg_type = data[0].get("type")
            node = data[1]["langgraph_node"]
            # todo check what id to use
            message_id = data[1]["run_id"]

        except (KeyError, IndexError, TypeError, AttributeError):
            return False

        # Only forward assistant text. Tool/human/system messages are internal and
        # can contain tool ids / intermediate state.
        #
        # LangGraph streaming often emits assistant output as AIMessageChunk objects
        # (type: "AIMessageChunk") rather than a final aggregated AIMessage ("ai").
        # If we filter strictly on "ai" we drop all streamed text, making the bot
        # appear silent even though the graph produced a response.
        if msg_type not in ("ai", "AIMessage", "AIMessageChunk"):
            return False

        # Skip metadata nodes
        if node in ["__start__", "__end__"]:
            return False

        # Do not stream intermediate control/guard LLM outputs to Telegram users.
        # These nodes are internal classifiers and can emit raw JSON.
        blocked_nodes = {
            "prepare_internal",
            "prepare_external",
            "intro_checker",
            "intro_quality_guard",
            "mention_checker",
            "strict_mention_checker",
            "mentioned_quality_guard",
            "unmentioned_relevance_guard",
        }
        if node in blocked_nodes:
            return False

        queue_chunk = MessageContent(
            message_id=message_id, chunk=content)
        return queue_chunk
