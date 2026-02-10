from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langchain_core.messages import SystemMessage

from conversation_states.states import ExternalState, InternalState
from .internal_graph import graph_chat_manager_internal


def prepare_internal(state: ExternalState) -> InternalState:
    # Reuse existing conversion logic.
    return InternalState.from_external(state)


def prepare_external(state: InternalState) -> ExternalState:
    # Return the last assistant message if any, otherwise send nothing.
    last = state.reasoning_messages_api.last()
    if not last:
        return ExternalState(
            messages=[],
            users=list(state.users),
            summary=state.summary,
            last_reasoning=state.reasoning_messages,
            memory_records=list(getattr(state, "memory_records", []) or []),
        )

    [msg] = last
    # If agent produced empty output, treat it as no-op.
    if getattr(msg, "content", "") == "":
        return ExternalState(
            messages=[],
            users=list(state.users),
            summary=state.summary,
            last_reasoning=state.reasoning_messages,
            memory_records=list(getattr(state, "memory_records", []) or []),
        )

    return ExternalState.from_internal(state, msg)


builder = StateGraph(InternalState, input=ExternalState, output=ExternalState)
builder.add_node("prepare_internal", prepare_internal)
builder.add_node("chat_manager", graph_chat_manager_internal)
builder.add_node("prepare_external", prepare_external)

builder.add_edge(START, "prepare_internal")
builder.add_edge("prepare_internal", "chat_manager")
builder.add_edge("chat_manager", "prepare_external")
builder.add_edge("prepare_external", END)

graph_chat_manager = builder.compile()

