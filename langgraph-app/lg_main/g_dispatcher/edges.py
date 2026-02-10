from __future__ import annotations

from typing import Literal

from conversation_states.states import ExternalState


def route_dispatch(state: ExternalState) -> Literal[
    "dispatcher_default_reply",
    "graph_router",
    "graph_supervisor",
]:
    target = getattr(state, "dispatch_target", None)
    if not isinstance(target, str) or not target.strip():
        return "dispatcher_default_reply"

    t = target.strip()
    if t in {"graph_router", "graph_supervisor"}:
        return t  # type: ignore[return-value]

    # Unknown target: treat as "not configured".
    return "dispatcher_default_reply"
