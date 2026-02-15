from __future__ import annotations
from typing import List, Optional, Annotated
from pydantic import BaseModel, Field, model_validator
from pydantic.type_adapter import TypeAdapter
from langchain_core.messages import BaseMessage, RemoveMessage, AnyMessage, AIMessage
from langgraph.graph import add_messages
from .humans import Human
from .highlights import Highlight
from .improvements import Improvement
from .memory import MemoryRecord
from .messages import MessageAPI, count_tokens
from .utils.reducers import add_user, add_memory_records, add_highlights, add_improvements, manage_state


class InternalState(BaseModel):
    reasoning_messages: Annotated[List[AnyMessage], add_messages] = Field(
        default_factory=list)
    external_messages: List[AnyMessage] = Field(
        default_factory=list)
    last_external_message: AnyMessage
    users: Annotated[list[Human], add_user] = Field(default_factory=list)
    last_sender: Human
    summary: str = ""
    memory_records: Annotated[list[MemoryRecord], add_memory_records] = Field(default_factory=list)
    highlights: Annotated[list[Highlight], add_highlights] = Field(default_factory=list)
    improvements: Annotated[list[Improvement], add_improvements] = Field(default_factory=list)
    thread_info_entries: list[str] = Field(default_factory=list)
    # Ephemeral routing helper (not persisted to checkpoints).
    chat_manager_decision: Optional[dict] = Field(default=None, exclude=True)
    # Ephemeral trigger for supervisor routing (mention, link, etc.).
    chat_manager_triggered: bool = Field(default=False, exclude=True)
    # Ephemeral result from script-only mention checker.
    strict_mention_detected: bool = Field(default=False, exclude=True)
    # Ephemeral flag: run non-mentioned relevance LLM guard or skip directly.
    run_unmentioned_relevance_guard: bool = Field(default=False, exclude=True)
    # Ephemeral flag/data for mentioned guard blocked response.
    mentioned_guard_blocked: bool = Field(default=False, exclude=True)
    mentioned_guard_emoji: str = Field(default="", exclude=True)
    # Ephemeral flags for #intro quality validation flow.
    intro_hashtag_detected: bool = Field(default=False, exclude=True)
    intro_quality_passed: bool = Field(default=False, exclude=True)
    chat_manager_categories: list[str] = Field(default_factory=list, exclude=True)
    chat_manager_response_stats: dict = Field(default_factory=dict)

    @property
    def reasoning_messages_api(self) -> MessageAPI:
        return MessageAPI(self, "reasoning_messages")

    @property
    def external_messages_api(self) -> MessageAPI:
        return MessageAPI(self, "external_messages")

    @classmethod
    def from_external(cls, external: "ExternalState") -> "InternalState":
        [last_message] = external.messages_api.last()
        sender = external.messages_api.sender(external.users)

        return cls(
            reasoning_messages=[],
            summary=external.summary,
            users=list(external.users),
            external_messages=external.messages,
            last_external_message=last_message,
            last_sender=sender,
            memory_records=list(external.memory_records or []),
            highlights=list(external.highlights or []),
            improvements=list(external.improvements or []),
            thread_info_entries=list(getattr(external, "thread_info_entries", []) or []),
            chat_manager_response_stats=dict(getattr(external, "chat_manager_response_stats", {}) or {}),
        )

    @model_validator(mode="before")
    @classmethod
    def resolve_union(cls, values: dict) -> dict:
        for field in ["reasoning_messages", "external_messages"]:
            if field in values:
                values[field] = [
                    TypeAdapter(AnyMessage).validate_python(m)
                    for m in values[field]
                ]
        if "memory_records" in values and values["memory_records"] is not None:
            values["memory_records"] = [
                r if isinstance(r, MemoryRecord) else MemoryRecord(**r)
                for r in values["memory_records"]
            ]
        if "highlights" in values and values["highlights"] is not None:
            values["highlights"] = [
                h if isinstance(h, Highlight) else Highlight(**h)
                for h in values["highlights"]
            ]
        if "improvements" in values and values["improvements"] is not None:
            values["improvements"] = [
                i if isinstance(i, Improvement) else Improvement(**i)
                for i in values["improvements"]
            ]
        if "thread_info_entries" in values and values["thread_info_entries"] is not None:
            values["thread_info_entries"] = [
                str(x).strip()
                for x in values["thread_info_entries"]
                if str(x).strip()
            ]
        return values


class ExternalState(BaseModel):
    messages: Annotated[List[AnyMessage], add_messages] = Field(
        default_factory=list)
    users: Annotated[list[Human], add_user] = Field(
        default_factory=list)
    summary: str = ""
    last_reasoning: Annotated[Optional[list[AnyMessage]],
                              manage_state] = Field(default=None)
    memory_records: Annotated[list[MemoryRecord], add_memory_records] = Field(default_factory=list)
    highlights: Annotated[list[Highlight], add_highlights] = Field(default_factory=list)
    improvements: Annotated[list[Improvement], add_improvements] = Field(default_factory=list)
    thread_info_entries: list[str] = Field(default_factory=list)
    chat_manager_response_stats: dict = Field(default_factory=dict)
    # Ephemeral routing helper for graph_dispatcher (not persisted to checkpoints).
    dispatch_target: Optional[str] = Field(default=None, exclude=True)

    @property
    def last_reasoning_api(self) -> MessageAPI:
        return MessageAPI(self, "last_reasoning")

    @property
    def messages_api(self) -> MessageAPI:
        return MessageAPI(self, "messages")

    @classmethod
    def from_internal(cls, internal: "InternalState", assistant_message: "AIMessage") -> "ExternalState":
        return cls(
            messages=[assistant_message],
            users=list(internal.users),
            summary=internal.summary,
            last_reasoning=internal.reasoning_messages,
            memory_records=list(getattr(internal, "memory_records", []) or []),
            highlights=list(getattr(internal, "highlights", []) or []),
            improvements=list(getattr(internal, "improvements", []) or []),
            thread_info_entries=list(getattr(internal, "thread_info_entries", []) or []),
            chat_manager_response_stats=dict(getattr(internal, "chat_manager_response_stats", {}) or {}),
        )

    @model_validator(mode="before")
    @classmethod
    def resolve_union(cls, values: dict) -> dict:
        if "messages" in values:
            values["messages"] = [
                TypeAdapter(AnyMessage).validate_python(m)
                for m in values["messages"]
            ]
        if "memory_records" in values and values["memory_records"] is not None:
            values["memory_records"] = [
                r if isinstance(r, MemoryRecord) else MemoryRecord(**r)
                for r in values["memory_records"]
            ]
        if "highlights" in values and values["highlights"] is not None:
            values["highlights"] = [
                h if isinstance(h, Highlight) else Highlight(**h)
                for h in values["highlights"]
            ]
        if "improvements" in values and values["improvements"] is not None:
            values["improvements"] = [
                i if isinstance(i, Improvement) else Improvement(**i)
                for i in values["improvements"]
            ]
        if "thread_info_entries" in values and values["thread_info_entries"] is not None:
            values["thread_info_entries"] = [
                str(x).strip()
                for x in values["thread_info_entries"]
                if str(x).strip()
            ]
        return values

    def clear_state(self):
        removed = [RemoveMessage(id=m.id)
                   for m in self.messages if hasattr(m, "id") and m.id]
        self.messages = removed
        self.summary = ""
        self.users = []
        self.last_reasoning = []
        self.memory_records = []
        self.highlights = []
        self.improvements = []
        self.thread_info_entries = []
        self.chat_manager_response_stats = {}
        return

    def summarize_overall_state(self) -> str:
        # 1. Users
        user_lines = []
        for u in self.users:
            name_line = f"{u.first_name} {u.last_name} ({u.username})"
            user_lines.append(
                f"- {name_line}\n"
                f"  - preferred_name: {u.preferred_name or 'not provided'}\n"
                f"  - info: {u.information or 'not provided'}"
            )
        if user_lines:
            users_block = "👤 Users:\n" + "\n".join(user_lines)
        else:
            users_block = "👤 Users: none"

        # 2. Messages (with formatting function)
        messages_block = self.messages_api.as_pretty()

        # 3. Summary
        if self.summary:
            summary_text = self.summary.strip()
            summary_tokens = count_tokens(summary_text)
        else:
            summary_text = "(No summary provided)"
            summary_tokens = 0
            summary_block = f"📝 Summary ({summary_tokens} tokens):\n{summary_text}"

        return f"{users_block}\n\n{messages_block}\n\n{summary_block}"

    def show_last_reasoning(self) -> str:
        if not self.last_reasoning:
            return "No messages available."
        api = self.last_reasoning_api
        return api.as_pretty(truncate=1500)
