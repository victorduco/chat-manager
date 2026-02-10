from __future__ import annotations

import logging
from typing import Any

from conversation_states.states import ExternalState
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage

from lg_main.g_command_router.graph import graph_router
from lg_main.g_supervisor.graph import graph_supervisor
from lg_main.g_chat_manager.graph import graph_chat_manager


_ALLOWED = {
    "graph_router": graph_router,
    "graph_supervisor": graph_supervisor,
    "graph_chat_manager": graph_chat_manager,
}


def _get_dispatch_graph_id(config: RunnableConfig | None) -> str | None:
    if not config:
        return None
    cfg = config.get("configurable") or {}
    # The assistant can set a default in its config, and callers can override per-run.
    # NOTE: do NOT look at generic keys like `graph_id` here; the LangGraph runtime
    # injects them and they'd incorrectly be treated as a dispatch target.
    for k in ("dispatch_graph_id", "target_graph_id"):
        v = cfg.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def dispatch(state: ExternalState, config: RunnableConfig) -> ExternalState:
    """
    Dispatcher graph:
    - If target graph id is specified (assistant/run configurable), invoke that graph.
    - If not specified, do nothing (no assistant message, no state changes beyond user input).
    """
    target = _get_dispatch_graph_id(config)
    if not target:
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
        )

    g = _ALLOWED.get(target)
    if g is None:
        logging.warning("Dispatcher: unknown dispatch_graph_id=%r; no-op", target)
        return ExternalState(
            messages=[],
            users=list(state.users),
            summary=state.summary,
            last_reasoning=state.last_reasoning,
        )

    # Delegate to the chosen graph. Preserve config so the same thread/checkpointer is used.
    return g.invoke(state, config=config)
