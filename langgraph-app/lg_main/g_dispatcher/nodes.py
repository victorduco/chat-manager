from __future__ import annotations

from conversation_states.states import ExternalState
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig


def _get_dispatch_graph_id(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    cfg = config.get("configurable") or {}
    # NOTE: only explicit dispatch keys; do not use generic runtime-injected keys.
    for k in ("dispatch_graph_id", "target_graph_id"):
        v = cfg.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def dispatcher_router(state: ExternalState, config: RunnableConfig) -> ExternalState:
    # Store routing decision in ephemeral field so edges can read it.
    state.dispatch_target = _get_dispatch_graph_id(config)
    return state


def dispatcher_default_reply(state: ExternalState) -> ExternalState:
    # No routing info: respond without calling any LLM/tools.
    return ExternalState(
        messages=[
            AIMessage(
                content="Routing is not configured for this thread.",
                name="dispatcher_default_no_routing",
            )
        ],
        users=list(state.users),
        summary=state.summary,
        last_reasoning=state.last_reasoning,
        memory_records=list(getattr(state, "memory_records", []) or []),
        highlights=list(getattr(state, "highlights", []) or []),
        improvements=list(getattr(state, "improvements", []) or []),
        chat_manager_response_stats=dict(getattr(state, "chat_manager_response_stats", {}) or {}),
    )
