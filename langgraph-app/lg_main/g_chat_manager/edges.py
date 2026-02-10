from __future__ import annotations

from typing import Literal

from conversation_states.states import InternalState


def route_chat_manager(state: InternalState) -> Literal[
    "add_record",
    "list_records",
    "list_categories",
    "unhelpful",
]:
    decision = getattr(state, "chat_manager_decision", None)
    intent = None
    if isinstance(decision, dict):
        intent = decision.get("intent")

    if intent == "add_record":
        return "add_record"
    if intent == "list_records":
        return "list_records"
    if intent == "list_categories":
        return "list_categories"
    return "unhelpful"
