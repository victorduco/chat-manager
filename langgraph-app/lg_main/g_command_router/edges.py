from typing import Literal
from conversation_states.states import ExternalState
from config import get_command_mapping


def route_command(state: ExternalState) -> Literal[
    "show_all_users_prep",
    "set_intro_status_prep",
    "clear_context_prep",
    "show_context_prep",
    "show_thinking_prep",
    "wrong_command",
]:
    """Route commands based on configuration."""
    command = state.messages[-1].content
    command_mapping = get_command_mapping()

    for prefix, node in command_mapping.items():
        if command.startswith(prefix):
            return node
    return "wrong_command"
