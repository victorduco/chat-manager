from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import StreamWriter
from tool_sets.user_profile import set_preferred_name, update_user_info, mark_intro_completed, send_user_reaction
from prompt_templates.prompt_builder import PromptBuilder
from langchain_core.messages import RemoveMessage, SystemMessage
from conversation_states.states import ExternalState, InternalState
from langchain_openai import ChatOpenAI
from pydantic import TypeAdapter
from testing_utils import create_test_user
import os
import logging
from dotenv import load_dotenv
load_dotenv()


llm = ChatOpenAI(model="gpt-4.1-2025-04-14")

profile_tools = [set_preferred_name, update_user_info, mark_intro_completed, send_user_reaction]


def prepare_internal(state: ExternalState) -> InternalState:
    # Add test user if list is empty (for manual testing)
    if not state.users:
        state.users.append(create_test_user())

    # Ensure the last human message has a .name attribute
    for i in reversed(range(len(state.messages))):
        msg = state.messages[i]
        if getattr(msg, "type", None) == "human":
            if not getattr(msg, "name", None):
                msg.name = state.users[0].username
            break

    int = InternalState.from_external(state)
    int.reasoning_messages = RemoveMessage(id=REMOVE_ALL_MESSAGES)

    return int


def instruction_builder(state: InternalState) -> InternalState:
    builder = PromptBuilder.from_state(state)
    if builder.sender:
        user_check_llm = llm.bind_tools(profile_tools)
        prompt = builder.build_response_instruction()
        prompt.name = "prompt_for_instruction_builder"
        instruction_dynamic = user_check_llm.invoke([prompt])
        final_instruction = builder.build_text_assistant_prompt(
            instruction_dynamic)
        final_instruction.name = "instruction_builder"
        state.reasoning_messages = [prompt] + [final_instruction]
    return state


def proceed_to_assistants(state:  InternalState) -> InternalState:
    # try:

    #     builder = PromptBuilder.from_state(state)
    #     user_info_prompt = builder.build_reply_instruction()
    # except Exception as e:
    #     raise

    return state


def text_assistant(state: InternalState) -> InternalState:
    prompt = state.reasoning_messages_api.last() + \
        state.external_messages_api.trim()
    response = llm.invoke(prompt)
    response.name = "text_assistant"
    state.reasoning_messages = [response]
    return state


def user_check(state: InternalState) -> InternalState:
    builder = PromptBuilder.from_state(state)
    if builder.sender:
        user_check_llm = llm.bind_tools(profile_tools)
        prompt = state.reasoning_messages_api.last(role="tool", name="user_check", count="all") + \
            [builder.build_user_info_prompt()]
        logging.debug(f"User check prompt: {prompt}")
        response = user_check_llm.invoke(prompt)
        response.name = "user_check"
        logging.debug(f"User check response: {response}")
        state.reasoning_messages = [response]
    return state


def action_assistant(state: InternalState) -> InternalState:
    pass


def intro_checker(state: InternalState, writer) -> InternalState:
    """Check if user message contains #intro hashtag and send reaction."""
    from conversation_states.actions import ActionSender

    sender = state.last_sender

    # If no sender, skip
    if not sender:
        return state

    # Check if CURRENT message has #intro
    current_message_content = getattr(state.last_external_message, 'content', '')
    has_intro_now = isinstance(current_message_content, str) and '#intro' in current_message_content.lower()

    # Get all messages from the current user
    user_messages = [
        msg for msg in state.external_messages
        if hasattr(msg, 'name') and msg.name == sender.username
    ]

    # Check if any previous message contains #intro hashtag
    has_intro_before = False
    for msg in user_messages[:-1]:  # Exclude current message
        content = getattr(msg, 'content', '')
        if isinstance(content, str) and '#intro' in content.lower():
            has_intro_before = True
            break

    # Mark intro as completed if found in current message
    if has_intro_now and not sender.intro_completed:
        sender.intro_completed = True
        logging.info(f"User {sender.username} completed intro with hashtag #intro in current message")

    # Send reaction based on intro status
    if writer:
        action_sender = ActionSender(writer)
        if has_intro_now:
            # User just completed intro NOW - send heart
            action_sender.send_reaction("❤")
            logging.info(f"Sent ❤ reaction to user {sender.username} - intro completed now")
        elif has_intro_before or sender.intro_completed:
            # User completed intro before - send thumbs up
            action_sender.send_reaction("👍")
            logging.info(f"Sent 👍 reaction to user {sender.username} - intro was completed before")
        else:
            # No intro - send thumbs down
            action_sender.send_reaction("👎")
            logging.info(f"Sent 👎 reaction to user {sender.username} - no intro")

    return state


def intro_responder(state: InternalState) -> InternalState:
    """Generate AI response only when user completes intro NOW."""
    sender = state.last_sender

    if not sender:
        return state

    # Check if CURRENT message has #intro
    current_message_content = getattr(state.last_external_message, 'content', '')
    has_intro_now = isinstance(current_message_content, str) and '#intro' in current_message_content.lower()

    # Only generate response if intro was completed in current message
    if has_intro_now:
        # User just completed intro NOW - welcome them
        system_prompt = SystemMessage(
            content="""Пользователь ТОЛЬКО ЧТО написал сообщение с хэштегом #intro, завершив знакомство.

ВАЖНО: Ответь ОЧЕНЬ КОРОТКО (1-2 предложения, максимум 10-15 слов).

Приветствуй пользователя тёплым коротким сообщением.
Примеры правильных ответов:
- "Рад познакомиться! 🎉"
- "Спасибо за знакомство! 😊"
- "Приятно познакомиться с тобой! ✨"

НЕ ПИШИ длинные сообщения. Будь максимально кратким и искренним.""",
            name="intro_responder_system"
        )

        # Get user's messages for context
        prompt = [system_prompt] + state.external_messages_api.trim()

        # Generate response
        response = llm.invoke(prompt)
        response.name = "intro_responder"
        state.reasoning_messages = [response]
        logging.info(f"Generated intro welcome response for user {sender.username}")
    else:
        # No intro in current message - create empty response
        # This will be filtered out in prepare_external
        response = SystemMessage(content="", name="intro_responder_skip")
        state.reasoning_messages = [response]
        logging.info(f"Skipped intro_responder - no intro in current message for user {sender.username}")

    return state


def prepare_external(state: InternalState) -> ExternalState:
    # Try to get message from intro_responder first
    assistant_messages = state.reasoning_messages_api.last(name="intro_responder")

    # Check if intro_responder was skipped (empty message)
    if assistant_messages and assistant_messages[0].content == "":
        # intro_responder skipped - don't send any message
        # Return empty external state (no message to send)
        ext = ExternalState(
            messages=[],
            users=list(state.users),
            summary=state.summary,
            last_reasoning=state.reasoning_messages
        )
        logging.info("Prepare external: skipped message (intro_responder returned empty)")
        return ext

    # If no intro_responder message, fallback to text_assistant
    if not assistant_messages:
        assistant_messages = state.reasoning_messages_api.last(name="text_assistant")

    [assistant_message] = assistant_messages
    ext = ExternalState.from_internal(state, assistant_message)
    return ext
