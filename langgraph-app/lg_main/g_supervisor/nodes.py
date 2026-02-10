from langgraph.graph.message import REMOVE_ALL_MESSAGES
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


def intro_checker(state: InternalState) -> InternalState:
    """Check if user message contains #intro hashtag."""
    sender = state.last_sender

    # If no sender, skip
    if not sender:
        return state

    # Get all messages from the current user
    user_messages = [
        msg for msg in state.external_messages
        if hasattr(msg, 'name') and msg.name == sender.username
    ]

    # Check if any message contains #intro hashtag
    for msg in user_messages:
        content = getattr(msg, 'content', '')
        if isinstance(content, str) and '#intro' in content.lower():
            # Mark intro as completed for this user
            if not sender.intro_completed:
                sender.intro_completed = True
                logging.info(f"User {sender.username} completed intro with hashtag #intro")
            break

    return state


def intro_responder(state: InternalState) -> InternalState:
    """Generate AI response based on intro status."""
    sender = state.last_sender

    if not sender:
        return state

    # Build prompt based on intro status
    if sender.intro_completed:
        # User has completed intro - praise them
        system_prompt = SystemMessage(
            content="""Пользователь написал сообщение с хэштегом #intro, что означает завершение знакомства.

Похвали пользователя за то, что он поделился информацией о себе.
Будь тёплым, дружелюбным и искренним.
Скажи что-то вроде: "Спасибо, что поделился! Рад познакомиться с тобой поближе 🎉"

Ответь коротко и естественно на его последнее сообщение.""",
            name="intro_responder_system"
        )
    else:
        # User hasn't completed intro yet - remind gently
        system_prompt = SystemMessage(
            content="""Пользователь ещё не завершил знакомство (не написал #intro).

Мягко напомни ему об этом в своём ответе.
Например: "Кстати, когда будешь готов завершить знакомство, просто напиши #intro в сообщении 😊"

Ответь на его сообщение естественно, добавив напоминание о #intro.""",
            name="intro_responder_system"
        )

    # Get user's messages for context
    prompt = [system_prompt] + state.external_messages_api.trim()

    # Generate response
    response = llm.invoke(prompt)
    response.name = "intro_responder"
    state.reasoning_messages = [response]

    return state


def prepare_external(state: InternalState) -> ExternalState:
    # Try to get message from intro_responder first, fallback to text_assistant
    assistant_messages = state.reasoning_messages_api.last(name="intro_responder")
    if not assistant_messages:
        assistant_messages = state.reasoning_messages_api.last(name="text_assistant")

    [assistant_message] = assistant_messages
    ext = ExternalState.from_internal(state, assistant_message)
    return ext
