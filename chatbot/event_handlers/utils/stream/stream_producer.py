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
from datetime import datetime, timezone


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
    async def _get_thread_metadata(client: LangGraphClient, thread_id: str) -> dict:
        """Return thread metadata dict (best effort)."""
        try:
            t = await client.threads.get(thread_id)
            meta = (t or {}).get("metadata") or {}
            return meta if isinstance(meta, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _thread_target_graph_id_from_metadata(meta: dict) -> str | None:
        for key in ("dispatch_graph_id", "target_graph_id", "graph_id"):
            v = meta.get(key)
            if v is None:
                continue
            v = str(v).strip()
            if v:
                return v
        return None

    @staticmethod
    def _require_intro_from_metadata(meta: dict) -> bool:
        # Default-on for backward compatibility.
        raw = meta.get("require_intro", True)
        if isinstance(raw, bool):
            return raw
        v = str(raw).strip().lower()
        if v in {"false", "0", "no", "off"}:
            return False
        if v in {"true", "1", "yes", "on"}:
            return True
        return True

    @staticmethod
    def _normalize_thread_info_entries(value: object, *, max_items: int = 40) -> list[str]:
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            text = " ".join(str(item or "").split()).strip()
            if not text:
                continue
            out.append(text)
            if len(out) >= max_items:
                break
        return out

    @staticmethod
    def _thread_info_entries_from_metadata(meta: dict) -> list[str]:
        entries = StreamProducer._normalize_thread_info_entries(meta.get("thread_info"))
        chat_description = " ".join(str(meta.get("chat_description") or "").split()).strip()
        if chat_description:
            entries.append(f"Chat description: {chat_description}")
        pinned = meta.get("pinned_message")
        if isinstance(pinned, dict):
            pinned_text = " ".join(str(pinned.get("text") or "").split()).strip()
            if pinned_text:
                entries.append(f"Pinned message: {pinned_text}")
        # Preserve order while deduplicating.
        deduped: list[str] = []
        seen: set[str] = set()
        for text in entries:
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(text)
        return deduped[:40]

    @staticmethod
    def _serialize_pinned_message(msg: TgMessage | None) -> dict | None:
        if msg is None:
            return None
        dt = getattr(msg, "date", None)
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        user = getattr(msg, "from_user", None)
        return {
            "message_id": getattr(msg, "message_id", None),
            "date": dt.isoformat() if isinstance(dt, datetime) else None,
            "text": getattr(msg, "text", None) or getattr(msg, "caption", None),
            "from_username": getattr(user, "username", None) if user else None,
            "from_user_id": str(getattr(user, "id", "")) if user else None,
        }

    @staticmethod
    async def _tg_chat_metadata(ctx: ContextExtractor) -> dict:
        """Best-effort extraction of chat metadata from update + Bot.get_chat."""
        out: dict = {"chat_id": str(ctx.chat_id)}
        chat = getattr(ctx.tg_message, "chat", None)
        if chat is not None:
            chat_title = getattr(chat, "title", None)
            chat_username = getattr(chat, "username", None)
            if chat_title:
                out["chat_title"] = str(chat_title)
            if chat_username:
                out["chat_username"] = str(chat_username).lstrip("@")

        # Enrich with full chat payload when possible (description, pinned message, canonical title).
        try:
            bot = ctx.tg_message.get_bot()
            full_chat = await bot.get_chat(chat_id=int(str(ctx.chat_id)))
            title = getattr(full_chat, "title", None) or getattr(full_chat, "username", None)
            if title:
                out["chat_title"] = str(title)
            username = getattr(full_chat, "username", None)
            if username:
                out["chat_username"] = str(username).lstrip("@")
            description = getattr(full_chat, "description", None)
            if description:
                out["chat_description"] = str(description)
            pinned = StreamProducer._serialize_pinned_message(getattr(full_chat, "pinned_message", None))
            if pinned:
                out["pinned_message"] = pinned
        except Exception:
            logging.debug("Failed to enrich thread metadata via get_chat", exc_info=True)

        return out

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

        # Best-effort: store Telegram chat metadata on the LangGraph thread so cron jobs can
        # message the right chat later and admin panel can show chat info.
        try:
            metadata_update = await StreamProducer._tg_chat_metadata(ctx)
            await StreamProducer._merge_thread_metadata_http(
                thread_id=thread["thread_id"],
                partial=metadata_update,
            )
        except Exception:
            logging.debug("Failed to persist Telegram chat metadata to thread metadata", exc_info=True)

        # Ensure default thread-level intro requirement exists for new/old threads,
        # but never overwrite an explicit false value.
        meta = await StreamProducer._get_thread_metadata(client, thread["thread_id"])
        defaults: dict = {}
        if "require_intro" not in meta:
            defaults["require_intro"] = True
        if not isinstance(meta.get("thread_info"), list):
            defaults["thread_info"] = []
        if defaults:
            try:
                await StreamProducer._merge_thread_metadata_http(
                    thread_id=thread["thread_id"],
                    partial=defaults,
                )
                meta = {**meta, **defaults}
            except Exception:
                logging.debug("Failed to persist thread metadata defaults", exc_info=True)

        dispatch_graph_id = StreamProducer._thread_target_graph_id_from_metadata(meta)
        require_intro = StreamProducer._require_intro_from_metadata(meta)
        state = ExternalState()
        state.thread_info_entries = StreamProducer._thread_info_entries_from_metadata(meta)
        msg_kwargs = dict(getattr(ctx.message, "additional_kwargs", {}) or {})
        msg_kwargs["require_intro"] = require_intro
        ctx.message.additional_kwargs = msg_kwargs
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
            stream_subgraphs=True,
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
                logging.info("Stream chunk event=%s", chunk.event)
                event_name = str(chunk.event or "").split("|", 1)[0]
                if event_name == "messages":
                    await self.queue_message(chunk.data)
                if event_name == "custom":
                    logging.info("Received custom stream chunk: %r", chunk.data)
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
        actions_raw = None
        if isinstance(data, dict):
            if isinstance(data.get("actions"), list):
                actions_raw = data.get("actions")
            elif isinstance(data.get("action"), dict):
                actions_raw = [data.get("action")]
        elif isinstance(data, list):
            actions_raw = data

        if not actions_raw:
            logging.warning("Ignoring malformed custom action payload: %r", data)
            return

        for raw in actions_raw:
            if not isinstance(raw, dict):
                logging.warning("Ignoring malformed action item: %r", raw)
                continue
            try:
                action = Action(**raw)
                await self.queue.actions.put(action)
                logging.info("Queued action: type=%s value=%r", action.type, action.value)
            except Exception:
                logging.exception("Failed to parse action item: %r", raw)

    def get_chunk_text(self, data):
        try:
            content = data[0]["content"]
            msg_type = data[0].get("type")
            msg_name = data[0].get("name")
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
            "agent",
            "doer",
            "intro_checker",
            "intro_quality_guard",
            "mention_checker",
            "strict_mention_checker",
            "mentioned_quality_guard",
            "mentioned_block_response",
            "unmentioned_relevance_guard",
        }
        node_str = str(node or "")
        # Subgraphs can emit composite node ids (for example with ":" separators).
        # Block if any segment matches known internal nodes.
        node_parts = {p for p in node_str.replace("/", ":").split(":") if p}
        if node_str in blocked_nodes or any(part in blocked_nodes for part in node_parts):
            return False

        # In responder nodes we can receive intermediate model chunks (for example
        # planner JSON) that should never be shown to Telegram users. Only pass
        # explicitly named final user-facing responder messages.
        if "responder" in node_parts:
            allowed_responder_names = {
                "chat_manager_responder",
                "intro_responder",
            }
            if msg_name not in allowed_responder_names:
                return False

        # Extra safety: filter internal Chat Manager "doer" message by message name,
        # even if node metadata points to parent graph node.
        blocked_message_names = {
            "chat_manager_doer",
        }
        if isinstance(msg_name, str) and msg_name in blocked_message_names:
            return False

        queue_chunk = MessageContent(
            message_id=message_id, chunk=content)
        return queue_chunk
