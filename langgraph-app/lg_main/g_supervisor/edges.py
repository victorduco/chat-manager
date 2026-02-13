from typing import Literal
from conversation_states.states import InternalState
from langchain_openai import ChatOpenAI


def route_after_intro_checker(state: InternalState) -> Literal["intro_quality_guard", "no_intro", "mention_checker"]:
    if bool(getattr(state, "intro_hashtag_detected", False)):
        return "intro_quality_guard"

    sender = getattr(state, "last_sender", None)
    intro_completed = bool(getattr(sender, "intro_completed", False)) if sender else False
    # If user has not completed intro and current message is not an intro, react and exit.
    if not intro_completed:
        return "no_intro"

    return "mention_checker"


def route_after_intro_quality_guard(state: InternalState) -> Literal["intro_responder", "intro_quality_reprompt"]:
    if bool(getattr(state, "intro_quality_passed", False)):
        return "intro_responder"
    return "intro_quality_reprompt"


def route_after_mention_checker(state: InternalState) -> Literal["mentioned_quality_guard", "unmentioned_relevance_guard", "prepare_external"]:
    if bool(getattr(state, "strict_mention_detected", False)):
        return "mentioned_quality_guard"
    if bool(getattr(state, "run_unmentioned_relevance_guard", False)):
        return "unmentioned_relevance_guard"
    return "prepare_external"


def route_after_mentioned_quality_guard(state: InternalState) -> Literal["chat_manager", "mentioned_block_response", "prepare_external"]:
    if bool(getattr(state, "mentioned_guard_blocked", False)):
        return "mentioned_block_response"
    triggered = bool(getattr(state, "chat_manager_triggered", False))
    return "chat_manager" if triggered else "prepare_external"


def route_after_unmentioned_relevance_guard(state: InternalState) -> Literal["chat_manager", "prepare_external"]:
    triggered = bool(getattr(state, "chat_manager_triggered", False))
    # Backward compatibility for old checkpoints/field name.
    if not triggered:
        triggered = bool(getattr(state, "bot_mentioned", False))
    return "chat_manager" if triggered else "prepare_external"


def should_use_profile_tools(state: InternalState) -> Literal["profile_tools", "prepare_external"]:
    [ai_message] = state.reasoning_messages_api.last()
    
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        print("go to tools")
        return "profile_tools"
    else:
        print("go to prep external")
        return "prepare_external"


def route_actions(state: InternalState) -> Literal["text_assistant", "action_assistant"]:
    return "text_assistant"


def should_summarize(state: InternalState) -> Literal["prepare_external", "__end__"]:
    messages = state.messages
    num_tokens = ChatOpenAI().get_num_tokens_from_messages(messages)

    if num_tokens > 500:
        return "prepare_external"
    else:
        return '__end__'
