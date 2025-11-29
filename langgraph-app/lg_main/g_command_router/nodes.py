from conversation_states.states import ExternalState
from conversation_states.actions import ActionSender, Action
from langgraph.types import StreamWriter
from datetime import datetime


def router(state: ExternalState) -> ExternalState:
    return state


def clear_context_prep(state: ExternalState) -> ExternalState:
    state.clear_state()
    return state


def clear_context(state: ExternalState, writer: StreamWriter) -> ExternalState:
    sender = ActionSender(writer)
    sender.send_reaction("👍")
    return state


def show_context_prep(state: ExternalState) -> ExternalState:
    state.messages_api.remove_last()
    return state


def show_context(state: ExternalState, writer: StreamWriter) -> ExternalState:
    sender = ActionSender(writer)
    summary_text = state.summarize_overall_state()
    action = Action(type="system-message", value=summary_text)
    sender.send_action(action)
    return state


def show_thinking_prep(state: ExternalState) -> ExternalState:
    state.messages_api.remove_last()
    return state


def show_thinking(state: ExternalState, writer: StreamWriter) -> ExternalState:
    sender = ActionSender(writer)
    reasoning_text = state.show_last_reasoning()
    action = Action(type="system-message", value=reasoning_text)
    sender.send_action(action)
    return state
