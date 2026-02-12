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
import random
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


def intro_checker(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Check if user message contains #intro hashtag and send reaction."""
    from conversation_states.actions import ActionSender

    sender = state.last_sender
    sender_intro_locked = bool(getattr(sender, "intro_locked", False))

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
    # If admin explicitly set intro status (intro_locked), do not infer completion
    # from old messages. That keeps "pending" meaningful even if the user had
    # posted #intro long ago.
    if not sender_intro_locked:
        for msg in user_messages[:-1]:  # Exclude current message
            content = getattr(msg, 'content', '')
            if isinstance(content, str) and '#intro' in content.lower():
                has_intro_before = True
                break

    # Mark intro as completed if found in current message
    if has_intro_now and not sender.intro_completed:
        sender.intro_completed = True
        sender.messages_without_intro = 0  # Reset counter when intro is completed
        logging.info(f"User {sender.username} completed intro with hashtag #intro in current message")
    elif has_intro_before and not sender.intro_completed and not sender_intro_locked:
        # Keep state consistent: if we detect past #intro, consider intro completed.
        sender.intro_completed = True
        sender.messages_without_intro = 0  # Reset counter
        logging.info(f"User {sender.username} already had #intro in history; marking intro_completed=True")

    # Send reaction based on intro status
    if writer:
        action_sender = ActionSender(writer)
        if has_intro_now:
            # User just completed intro NOW - send heart
            action_sender.send_reaction("❤")
            logging.info(f"Sent ❤ reaction to user {sender.username} - intro completed now")

            # Unrestrict user if they were restricted
            if sender.telegram_id:
                chat_id = state.external_messages_api.last()[0].additional_kwargs.get("chat_id")
                if chat_id:
                    import json
                    action_sender.send_action(Action(
                        type="unrestrict",
                        value=json.dumps({"user_id": sender.telegram_id, "chat_id": int(chat_id)})
                    ))
                    logging.info(f"Sent unrestrict action for user {sender.username}")
        else:
            # Non-intro messages are handled by other graphs (e.g. chat_manager).
            logging.info(f"No intro reaction sent to user {sender.username}")

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


def no_intro(state: InternalState, writer=None) -> InternalState:
    """If intro not completed and current message isn't an intro, react with thinking emoji and exit."""
    from conversation_states.actions import ActionSender, Action

    sender = state.last_sender
    if not sender:
        response = SystemMessage(content="", name="no_intro_skip")
        state.reasoning_messages = [response]
        return state

    # Increment message counter
    sender.messages_without_intro += 1
    count = sender.messages_without_intro

    if writer:
        action_sender = ActionSender(writer)
        try:
            # Thinking emoji reaction
            action_sender.send_reaction("🤔")
        except Exception:
            pass

        # Send warning messages at specific thresholds
        try:
            if count == 3:
                action_sender.send_action(Action(
                    type="system-message",
                    value="Согласно правилам клуба, участникам необходимо представиться. Расскажите о себе для нашего комьюнити в сообщении с тегом #intro.\n\nОтправлено 3 из 10 сообщений. После 10 сообщений возможность отправки сообщений будет ограничена."
                ))
            elif count == 7:
                action_sender.send_action(Action(
                    type="system-message",
                    value="Отправлено 7 из 10 сообщений. Пожалуйста, расскажите о себе с тегом #intro."
                ))
            elif count >= 10:
                action_sender.send_action(Action(
                    type="system-message",
                    value="Достигнут лимит сообщений без представления. Отправка сообщений ограничена. Напишите #intro для снятия ограничений."
                ))
                # Restrict user from sending messages
                if sender.telegram_id:
                    chat_id = state.external_messages_api.last()[0].additional_kwargs.get("chat_id")
                    if chat_id:
                        action_sender.send_restrict(
                            user_id=sender.telegram_id,
                            chat_id=int(chat_id)
                        )
        except Exception:
            pass

    # No text response from AI.
    response = SystemMessage(content="", name="no_intro_skip")
    state.reasoning_messages = [response]
    return state


def mention_checker(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Set state.bot_mentioned based on whether the bot was explicitly addressed."""
    import os
    import re

    text = getattr(state.last_external_message, "content", "") or ""
    t = text.lower()

    # Configurable mention tokens.
    # Example: BOT_MENTION_TOKENS="victorai,викор,@victorai,@victorducoai_bot"
    # Default includes both the historical project name and the current Telegram bot username.
    raw = os.getenv(
        "BOT_MENTION_TOKENS",
        "victorai,@victorai,викор,victorducoai_bot,@victorducoai_bot",
    ).strip()
    tokens = [x.strip().lower() for x in raw.split(",") if x.strip()]

    mentioned = False
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("@"):
            if tok in t:
                mentioned = True
                break
        else:
            # Word-ish match to reduce false positives.
            if re.search(rf"(?<!\\w){re.escape(tok)}(?!\\w)", t):
                mentioned = True
                break

    state.bot_mentioned = bool(mentioned)

    # No output; routing happens via conditional edges.
    response = SystemMessage(content="", name="mention_checker")
    state.reasoning_messages = [response]
    return state


def prepare_external(state: InternalState) -> ExternalState:
    # Try to get message from intro_responder first
    assistant_messages = state.reasoning_messages_api.last(name="intro_responder")

    # Otherwise (or when intro_responder skipped), fallback to the latest reasoning message.
    if not assistant_messages:
        assistant_messages = state.reasoning_messages_api.last()

    # If last message is an explicit "skip", don't send anything.
    if assistant_messages and (getattr(assistant_messages[0], "content", None) == ""):
        ext = ExternalState(
            messages=[],
            users=list(state.users),
            summary=state.summary,
            last_reasoning=state.reasoning_messages,
            memory_records=list(getattr(state, "memory_records", []) or []),
        )
        logging.info("Prepare external: skipped message (empty content)")
        return ext

    if not assistant_messages:
        # Nothing to send; avoid crashing the run.
        logging.warning("Prepare external: no assistant message found; returning empty messages")
        return ExternalState(
            messages=[],
            users=list(state.users),
            summary=state.summary,
            last_reasoning=state.reasoning_messages,
            memory_records=list(getattr(state, "memory_records", []) or []),
        )

    [assistant_message] = assistant_messages
    ext = ExternalState.from_internal(state, assistant_message)
    return ext
