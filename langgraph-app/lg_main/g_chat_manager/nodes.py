from __future__ import annotations

import re
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter
from pydantic import BaseModel, Field

from conversation_states.states import InternalState
from conversation_states.actions import ActionSender
from tool_sets.chat_memory import (
    _add_memory_record_impl,
    _get_unique_categories_impl,
    _list_memory_records_impl,
)


llm = ChatOpenAI(model="gpt-4.1-2025-04-14")


class ChatManagerDecision(BaseModel):
    intent: Literal["add_record", "list_records", "list_categories", "unhelpful"] = Field(
        description="What to do with the user message."
    )
    category: Optional[str] = Field(default=None, description="Record category (for add_record).")
    text: Optional[str] = Field(default=None, description="Record text (for add_record).")


def _categories_block(state: InternalState) -> str:
    cats = _get_unique_categories_impl(state=state)
    if not cats:
        return "(пока нет)"
    return "\n".join(f"- {c}" for c in cats)


def _is_unhelpful_heuristic(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    # Tiny smalltalk / acknowledgements: treat as unhelpful for this graph.
    if len(t) <= 3:
        return True
    if re.fullmatch(r"(спс|спасибо|ок|okay|ok|привет|hi|hello|yo|thx|ty)\W*", t):
        return True
    # If they ask unrelated things (not memory management), prefer unhelpful.
    # The LLM router will still have the final say; this just short-circuits obvious noise.
    return False


def decide_intent(state: InternalState) -> InternalState:
    user_text = getattr(state.last_external_message, "content", "") or ""

    if _is_unhelpful_heuristic(user_text):
        state.chat_manager_decision = {"intent": "unhelpful"}  # ephemeral helper field
        return state

    sys = SystemMessage(
        content=(
            "Ты граф-агент Chat Manager. Твоя задача: управлять памятью идей.\n\n"
            "Доступные действия:\n"
            "1) add_record: добавить запись (категория + текст)\n"
            "2) list_records: показать все записи\n"
            "3) list_categories: показать уникальные категории\n\n"
            "ВАЖНО (защита от неполезных обращений):\n"
            "- Если сообщение не просит добавить/показать записи/категории и не содержит полезной идеи, выбери intent=unhelpful.\n"
            "- При unhelpful НЕ отвечай текстом.\n\n"
            "Уже существующие категории:\n"
            f"{_categories_block(state)}\n\n"
            "Верни ТОЛЬКО JSON по схеме:\n"
            '{"intent":"add_record|list_records|list_categories|unhelpful","category":null|string,"text":null|string}\n'
            "Правила для add_record:\n"
            "- category: коротко, 1-3 слова (например: Предложение, Баг, Вопрос, Идея)\n"
            "- text: кратко, без воды\n"
        ),
        name="chat_manager_router_system",
    )

    router = llm.with_structured_output(ChatManagerDecision)
    decision = router.invoke([sys, HumanMessage(content=user_text, name="chat_manager_router_user")])
    state.chat_manager_decision = decision.model_dump()
    return state


def add_record(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    d = getattr(state, "chat_manager_decision", {}) or {}
    category = (d.get("category") or "").strip() or "Предложение"
    text = (d.get("text") or "").strip()
    user_text = (getattr(state.last_external_message, "content", "") or "").strip()

    if not text:
        # Fallback: store the raw message as the idea text.
        text = user_text

    _add_memory_record_impl(state=state, category=category, text=text)

    if writer:
        ActionSender(writer).send_reaction("👍")

    msg = AIMessage(content="Записал идею. Спасибо! 🙏", name="chat_manager_add_record")
    state.reasoning_messages = [msg]
    return state


def list_records(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    rows = _list_memory_records_impl(state=state)

    if writer:
        ActionSender(writer).send_reaction("🙏")

    if not rows:
        msg = AIMessage(content="Идей пока нет.", name="chat_manager_list_records")
        state.reasoning_messages = [msg]
        return state

    # Keep it short: show up to 20 most recent.
    out = []
    for r in rows[:20]:
        cat = r.get("category") or "Без категории"
        text = r.get("text") or ""
        who = ((r.get("from_user") or {}).get("username") or "").strip()
        who = f"@{who}" if who else ""
        out.append(f"- [{cat}] {text} {who}".rstrip())

    suffix = "" if len(rows) <= 20 else f"\n(показано 20 из {len(rows)})"
    msg = AIMessage(content="Список идей:\n" + "\n".join(out) + suffix, name="chat_manager_list_records")
    state.reasoning_messages = [msg]
    return state


def list_categories(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    cats = _get_unique_categories_impl(state=state)

    if writer:
        ActionSender(writer).send_reaction("🙏")

    if not cats:
        msg = AIMessage(content="Категорий пока нет.", name="chat_manager_list_categories")
        state.reasoning_messages = [msg]
        return state

    msg = AIMessage(content="Категории:\n- " + "\n- ".join(cats), name="chat_manager_list_categories")
    state.reasoning_messages = [msg]
    return state


def unhelpful(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    if writer:
        ActionSender(writer).send_reaction("👎")
    # No text answer.
    state.reasoning_messages = [SystemMessage(content="", name="chat_manager_skip")]
    return state
