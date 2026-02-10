from typing import Literal
from conversation_states.states import InternalState
from langchain_openai import ChatOpenAI


def route_after_intro_checker(state: InternalState) -> Literal["intro_responder", "chat_manager"]:
    current_message_content = getattr(state.last_external_message, "content", "")
    has_intro_now = isinstance(current_message_content, str) and "#intro" in current_message_content.lower()
    return "intro_responder" if has_intro_now else "chat_manager"


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
