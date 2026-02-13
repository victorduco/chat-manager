from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import StreamWriter
from langchain_core.messages import ToolMessage

from conversation_states.states import InternalState
from tool_sets.chat_memory import _get_unique_categories_impl
from tool_sets.chat_memory import _add_memory_record_impl, _list_memory_records_impl
from tool_sets.chat_memory import add_memory_record, list_memory_records
from tool_sets.highlights import (
    _add_highlights_impl,
    _delete_highlight_impl,
    _search_highlights_impl,
    _trending_highlights_impl,
    add_highlights,
    delete_highlight,
    search_highlights,
    trending_highlights,
)


llm = ChatOpenAI(model="gpt-4.1-2025-04-14")

CHAT_MANAGER_TOOLS = [
    add_memory_record,
    list_memory_records,
    add_highlights,
    delete_highlight,
    search_highlights,
    trending_highlights,
]


def load_categories(state: InternalState) -> InternalState:
    """Load current unique categories and stash them for the agent prompt."""
    state.chat_manager_categories = _get_unique_categories_impl(state=state)
    return state


def prime_turn(state: InternalState) -> InternalState:
    """
    Seed the chat-manager reasoning message history with the current user message
    exactly once. This lets ToolNode append tool outputs, and the agent can see them
    on the next iteration without re-sending the user message.
    """
    user_text = getattr(state.last_external_message, "content", "") or ""
    user_name = getattr(state.last_external_message, "name", None) or getattr(state.last_sender, "username", None)

    if not getattr(state, "reasoning_messages", None):
        state.reasoning_messages = []

    # Only add if this turn isn't already primed.
    last = state.reasoning_messages_api.last()
    if last:
        [m] = last
        if getattr(m, "type", None) == "human":
            # Already primed for this turn.
            return state

    state.reasoning_messages = list(state.reasoning_messages) + [
        HumanMessage(content=str(user_text), name=user_name),
    ]
    return state


def _categories_block(state: InternalState) -> str:
    cats = list(getattr(state, "chat_manager_categories", []) or [])
    if not cats:
        return "(none yet)"
    return "\n".join(f"- {c}" for c in cats)


def agent(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """
    LLM agent node:
    - decides whether to call tools
    - after tools are executed, formats a short response
    """
    system = SystemMessage(
        content=(
            "You are Chat Manager for a Telegram chat.\n"
            "Your job is to manage two thread-level stores:\n"
            "1) ideas log (memory records)\n"
            "2) highlights (useful links/materials relevant to the channel)\n\n"
            "Available tools:\n"
            "- add_memory_record(category, text)\n"
            "- list_memory_records()\n\n"
            "- add_highlights(highlights)\n"
            "- delete_highlight(highlight_id?, highlight_link?, hard_delete?)\n"
            "- search_highlights(author_username?, days?, category?, tags?, limit?, offset?)\n"
            "- trending_highlights(days?, category?, limit?)\n\n"
            "Highlights meaning:\n"
            "- Highlights are NOT generic 'selected messages'.\n"
            "- Highlights are useful resources and references: articles, videos, channels, tools, jobs, services.\n"
            "- If user shares a link/material and wants to save it for later, use add_highlights.\n"
            "- Category values: jobs, resources, services.\n"
            "- You must infer category and tags yourself from context.\n"
            "- You must infer a short description yourself from context.\n"
            "- For articles, usually choose category=resources and add semantic tags (e.g. article + topic words).\n"
            "- Avoid platform tags unless user explicitly asks for them.\n\n"
            "Categories guidance (use an existing category if it fits, or create a new short one):\n"
            f"{_categories_block(state)}\n\n"
            "Rules:\n"
            "- If the user shares a concrete idea/suggestion/task WITHOUT a resource link, call add_memory_record.\n"
            "- If the user asks to see ideas/records, call list_memory_records.\n"
            "- If the user shares or references a useful link/material (article/video/channel/etc), call add_highlights.\n"
            "- add_highlights accepts one or many highlights per call.\n"
            "- For each highlight item pass: category, highlight_description, tags? and optional highlight_link.\n"
            "- If highlight_link is available in user text/context, pass it as-is.\n"
            "- Never ask the user to re-send or reply to a message just to save a highlight.\n"
            "- For saving requests, call add_highlights immediately.\n"
            "- If the user asks to remove a highlight, call delete_highlight.\n"
            "- If the user asks to find highlights by user/days/category, call search_highlights.\n"
            "- If the user asks for best/recent top highlights, call trending_highlights.\n"
            "- Tool selection priority: for link/material saving requests prefer add_highlights over add_memory_record.\n"
            "- When user asks what you can do, describe highlights as 'полезные ссылки/материалы', not 'selected messages'.\n"
            "- Keep final answers short and casual.\n"
            "- After successful save to highlights, use a friendly concise tone and vary wording across replies.\n"
            "- Avoid formal bureaucratic phrasing in save confirmations.\n"
            "- Never invent tool results; rely on tool outputs.\n"
        ),
        name="chat_manager_system",
    )

    model = llm.bind_tools(CHAT_MANAGER_TOOLS)
    # Provide full reasoning history (human + prior AI/tool messages) so the model
    # can decide what to do next after tool outputs.
    history = list(getattr(state, "reasoning_messages", []) or [])
    resp = model.invoke([system] + history)
    resp.name = "chat_manager_agent"
    state.reasoning_messages = list(getattr(state, "reasoning_messages", []) or []) + [resp]
    return state


def run_tools(state: InternalState) -> InternalState:
    """
    Execute tool calls from the last AIMessage and append ToolMessages.

    We intentionally do NOT rely on ToolNode mutating the state via InjectedState,
    because those side effects are not guaranteed to persist. Instead we perform
    state updates explicitly here.
    """
    last = state.reasoning_messages_api.last()
    if not last:
        return state
    [msg] = last
    tool_calls = getattr(msg, "tool_calls", None) or []
    if not tool_calls:
        return state

    out_msgs: list[ToolMessage] = []
    for call in tool_calls:
        name = call.get("name")
        args = call.get("args") or {}
        call_id = call.get("id")
        if not isinstance(name, str) or not call_id:
            continue

        if name == "add_memory_record":
            category = str(args.get("category") or "")
            text = str(args.get("text") or "")
            rec_id = _add_memory_record_impl(state=state, category=category, text=text)
            out_msgs.append(ToolMessage(content=str(rec_id), name=name, tool_call_id=call_id))
            # keep categories list fresh for the next agent step
            state.chat_manager_categories = _get_unique_categories_impl(state=state)
            continue

        if name == "list_memory_records":
            rows = _list_memory_records_impl(state=state)
            # JSON so the agent can format a short list safely.
            out_msgs.append(
                ToolMessage(
                    content=json.dumps(rows, ensure_ascii=False),
                    name=name,
                    tool_call_id=call_id,
                )
            )
            continue

        if name == "add_highlights":
            result = _add_highlights_impl(
                state=state,
                highlights=args.get("highlights"),
            )
            out_msgs.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    name=name,
                    tool_call_id=call_id,
                )
            )
            continue

        if name == "delete_highlight":
            result = _delete_highlight_impl(
                state=state,
                highlight_id=args.get("highlight_id"),
                highlight_link=args.get("highlight_link") or args.get("message_link"),
                hard_delete=bool(args.get("hard_delete", False)),
            )
            out_msgs.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    name=name,
                    tool_call_id=call_id,
                )
            )
            continue

        if name == "search_highlights":
            result = _search_highlights_impl(
                state=state,
                author_username=args.get("author_username"),
                author_telegram_id=args.get("author_telegram_id"),
                days=args.get("days"),
                category=args.get("category"),
                tags=args.get("tags"),
                limit=args.get("limit", 20),
                offset=args.get("offset", 0),
            )
            out_msgs.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    name=name,
                    tool_call_id=call_id,
                )
            )
            continue

        if name == "trending_highlights":
            result = _trending_highlights_impl(
                state=state,
                days=args.get("days", 5),
                category=args.get("category"),
                limit=args.get("limit", 10),
            )
            out_msgs.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    name=name,
                    tool_call_id=call_id,
                )
            )
            continue

        out_msgs.append(ToolMessage(content=f"Unsupported tool: {name}", name=name, tool_call_id=call_id))

    state.reasoning_messages = list(getattr(state, "reasoning_messages", []) or []) + out_msgs
    return state
