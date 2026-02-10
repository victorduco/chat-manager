from typing import Literal
from conversation_states.states import InternalState
from langchain_openai import ChatOpenAI


def route_after_intro_checker(state: InternalState) -> Literal["intro_responder", "no_intro", "mention_checker"]:
    current_message_content = getattr(state.last_external_message, "content", "")
    has_intro_now = isinstance(current_message_content, str) and "#intro" in current_message_content.lower()
    if has_intro_now:
        return "intro_responder"

    sender = getattr(state, "last_sender", None)
    intro_completed = bool(getattr(sender, "intro_completed", False)) if sender else False
    # If user has not completed intro and current message is not an intro, react and exit.
    if not intro_completed:
        return "no_intro"

    return "mention_checker"


def route_after_mention_checker(state: InternalState) -> Literal["chat_manager", "prepare_external"]:
    return "chat_manager" if bool(getattr(state, "bot_mentioned", False)) else "prepare_external"


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
