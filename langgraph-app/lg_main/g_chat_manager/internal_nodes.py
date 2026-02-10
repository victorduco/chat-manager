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


llm = ChatOpenAI(model="gpt-4.1-2025-04-14")

CHAT_MANAGER_TOOLS = [add_memory_record, list_memory_records]


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
            "Your job is to manage a thread-level idea log (memory records).\n\n"
            "Available tools:\n"
            "- add_memory_record(category, text)\n"
            "- list_memory_records()\n\n"
            "Categories guidance (use an existing category if it fits, or create a new short one):\n"
            f"{_categories_block(state)}\n\n"
            "Rules:\n"
            "- If the user shares a concrete idea/suggestion/task, call add_memory_record.\n"
            "- If the user asks to see ideas/records, call list_memory_records.\n"
            "- Keep final answers short.\n"
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

        out_msgs.append(ToolMessage(content=f"Unsupported tool: {name}", name=name, tool_call_id=call_id))

    state.reasoning_messages = list(getattr(state, "reasoning_messages", []) or []) + out_msgs
    return state
