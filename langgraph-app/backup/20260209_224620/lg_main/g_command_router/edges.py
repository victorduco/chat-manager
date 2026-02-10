from typing import Literal
from conversation_states.states import ExternalState


def route_command(state: ExternalState) -> Literal["clear_context_prep", "show_context_prep", "show_thinking_prep", "wrong_command"]:

    command = state.messages[-1].content
    COMMANDS = {
        "/clear_context": "clear_context_prep",
        "/show_context": "show_context_prep",
        "/show_thinking": "show_thinking_prep",
    }

    for prefix, value in COMMANDS.items():
        if command.startswith(prefix):
            return value
    return "wrong_command"
