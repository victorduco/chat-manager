from __future__ import annotations

from typing import Literal

from conversation_states.states import InternalState


def should_use_tools(state: InternalState) -> Literal["tools", "__end__"]:
    last = state.reasoning_messages_api.last()
    if not last:
        return "__end__"
    [msg] = last
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        return "tools"
    return "__end__"

