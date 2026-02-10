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
    """Check if user needs intro reminder and potentially modify response."""
    sender = state.last_sender

    # If intro is already completed, skip
    if not sender or sender.intro_completed:
        return state

    # Count meaningful messages from this user (excluding very short ones)
    user_messages = [
        msg for msg in state.external_messages
        if hasattr(msg, 'name') and msg.name == sender.username
        and len(getattr(msg, 'content', '')) > 10
    ]

    # If user has sent 2+ meaningful messages but hasn't written intro
    if len(user_messages) >= 2:
        # Get the current assistant response
        assistant_messages = state.reasoning_messages_api.last(name="text_assistant")
        if assistant_messages:
            current_response = assistant_messages[0]

            # Add gentle intro reminder
            intro_reminder = SystemMessage(
                content=f"""Add a gentle, friendly reminder to your response asking the user to share their introduction.

Current response: {current_response.content}

Append something like: "By the way, I'd love to know more about you! Could you share a bit about yourself - your interests, what you do, or anything you'd like me to know?"

Keep it natural and conversational. Don't make it sound forced."""
            )

            # Regenerate response with intro reminder
            prompt = [intro_reminder] + state.external_messages_api.trim()
            response = llm.invoke(prompt)
            response.name = "text_assistant"
            state.reasoning_messages = [response]

    return state


def prepare_external(state: InternalState) -> ExternalState:
    [assistant_message] = state.reasoning_messages_api.last(
        name="text_assistant")
    ext = ExternalState.from_internal(state, assistant_message)
    return ext
