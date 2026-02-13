from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import StreamWriter
from tool_sets.user_profile import set_preferred_name, update_user_info, mark_intro_completed, send_user_reaction
from prompt_templates.prompt_builder import PromptBuilder
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from conversation_states.states import ExternalState, InternalState
from langchain_openai import ChatOpenAI
from pydantic import TypeAdapter
from testing_utils import create_test_user
import os
import logging
import random
import json
import re
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


def _has_intro_hashtag(state: InternalState) -> bool:
    return "#intro" in _extract_message_text(state).lower()


def intro_checker(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Detect #intro and keep user intro status in sync without sending reply/reactions."""

    sender = state.last_sender
    sender_intro_locked = bool(getattr(sender, "intro_locked", False))

    # If no sender, skip
    if not sender:
        return state

    # Check if CURRENT message has #intro
    has_intro_now = _has_intro_hashtag(state)
    state.intro_hashtag_detected = bool(has_intro_now)
    state.intro_quality_passed = False

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

    if has_intro_before and not sender.intro_completed and not sender_intro_locked:
        # Keep state consistent: if we detect past #intro, consider intro completed.
        sender.intro_completed = True
        sender.messages_without_intro = 0  # Reset counter
        logging.info(f"User {sender.username} already had #intro in history; marking intro_completed=True")

    return state


def intro_quality_guard(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Validate #intro message quality before marking intro as completed."""
    text = _extract_message_text(state).strip()
    state.intro_quality_passed = False
    if "#intro" not in text.lower():
        state.reasoning_messages = [SystemMessage(content="", name="intro_quality_guard_skip")]
        return state

    prompt = SystemMessage(
        content=(
            "You validate Telegram introductions marked with #intro.\n"
            "Return strict JSON only with fields:\n"
            "{\"allow\": boolean, \"reason\": string}\n"
            "allow=true only if user shared a meaningful short self-introduction.\n"
            "A good intro contains at least 3-4 meaningful words about the person (role/background/interests/context).\n"
            "allow=false for empty tag-only messages, nonsense, trolling, mockery, or content with no useful self-info.\n"
            "Be strict but fair.\n"
        ),
        name="intro_quality_guard_system",
    )

    result = {"allow": False, "reason": "fallback_block"}
    try:
        raw = llm.invoke([prompt, HumanMessage(content=text)]).content
        parsed = json.loads(str(raw))
        if isinstance(parsed, dict):
            result = {
                "allow": bool(parsed.get("allow", False)),
                "reason": str(parsed.get("reason", "") or ""),
            }
    except Exception:
        result = {"allow": False, "reason": "parse_error_fallback_block"}

    state.intro_quality_passed = bool(result["allow"])
    logging.info(
        "intro_quality_guard: allow=%s reason=%s",
        result.get("allow"),
        result.get("reason"),
    )
    state.reasoning_messages = [SystemMessage(content="", name="intro_quality_guard_pass" if state.intro_quality_passed else "intro_quality_guard_block")]
    return state


def intro_quality_reprompt(state: InternalState) -> InternalState:
    """Politely ask user to provide a more useful self-introduction."""
    prompt = SystemMessage(
        content=(
            "User sent #intro but intro quality is insufficient.\n"
            "Write a short, polite Russian reply that asks the user to share a bit more about themselves.\n"
            "Tone: friendly, respectful, not formal, no sarcasm.\n"
            "Do not include examples, templates, bullet points, or rules list.\n"
            "Keep it concise: 1 short sentence.\n"
        ),
        name="intro_quality_reprompt_system",
    )
    response = llm.invoke([prompt, HumanMessage(content=_extract_message_text(state).strip())])
    response.name = "intro_quality_reprompt"
    state.reasoning_messages = [response]
    return state


def intro_responder(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Generate AI response when #intro passes quality check; update intro state."""
    from conversation_states.actions import Action, ActionSender

    sender = state.last_sender

    if not sender:
        return state

    has_intro_now = _has_intro_hashtag(state)
    intro_passed = bool(getattr(state, "intro_quality_passed", False))

    # Only generate response if intro was completed in current message and passed quality check.
    if has_intro_now and intro_passed:
        if not sender.intro_completed:
            sender.intro_completed = True
            sender.messages_without_intro = 0
            logging.info(f"User {sender.username} completed intro with hashtag #intro in current message")

        # Unrestrict user if they were previously restricted.
        if writer:
            action_sender = ActionSender(writer)
            user_id = sender.telegram_id
            last_message = state.external_messages_api.last()[0]
            chat_id = last_message.additional_kwargs.get("chat_id")
            if user_id is None:
                raw_uid = last_message.additional_kwargs.get("tg_user_id")
                try:
                    user_id = int(raw_uid) if raw_uid is not None else None
                except (TypeError, ValueError):
                    user_id = None
            if user_id is not None and chat_id:
                action_sender.send_action(Action(
                    type="unrestrict",
                    value=json.dumps({"user_id": int(user_id), "chat_id": int(chat_id)})
                ))
                logging.info(f"Sent unrestrict action for user {sender.username}")

        system_prompt = SystemMessage(
            content="""Пользователь ТОЛЬКО ЧТО написал сообщение с хэштегом #intro, завершив знакомство.

Ответь кратко и по-доброму на русском (1 короткое предложение).""",
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
        response = SystemMessage(content="", name="intro_responder_skip")
        state.reasoning_messages = [response]
        logging.info(f"Skipped intro_responder - no valid intro in current message for user {sender.username}")

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
                user_id = sender.telegram_id
                last_message = state.external_messages_api.last()[0]
                chat_id = last_message.additional_kwargs.get("chat_id")
                if user_id is None:
                    # Backward-compatible fallback for old checkpoints where
                    # sender.telegram_id might be missing.
                    raw_uid = last_message.additional_kwargs.get("tg_user_id")
                    try:
                        user_id = int(raw_uid) if raw_uid is not None else None
                    except (TypeError, ValueError):
                        user_id = None

                logging.info(f"User {sender.username} reached 10 messages. Attempting to restrict. telegram_id={user_id}")
                logging.info(f"Got chat_id from message: {chat_id}")
                if user_id is not None and chat_id:
                    logging.info(f"Sending restrict action for user_id={user_id}, chat_id={chat_id}")
                    action_sender.send_restrict(
                        user_id=int(user_id),
                        chat_id=int(chat_id)
                    )
                else:
                    if user_id is None:
                        logging.warning(f"No telegram_id for user {sender.username}")
                    if not chat_id:
                        logging.warning(f"No chat_id found in message for user {sender.username}")
        except Exception:
            pass

    # No text response from AI.
    response = SystemMessage(content="", name="no_intro_skip")
    state.reasoning_messages = [response]
    return state


def _extract_message_text(state: InternalState) -> str:
    raw_content = getattr(state.last_external_message, "content", "") or ""
    if isinstance(raw_content, str):
        return raw_content
    elif isinstance(raw_content, list):
        parts: list[str] = []
        for item in raw_content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                v = item.get("text")
                if isinstance(v, str):
                    parts.append(v)
        return "".join(parts)
    else:
        return str(raw_content)


def _mention_tokens() -> list[str]:
    raw = os.getenv(
        "BOT_MENTION_TOKENS",
        "victorai,@victorai,викор,victorducoai_bot,@victorducoai_bot,victorai_dev_bot,@victorai_dev_bot",
    ).strip()
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def _strip_tg_webapp_deeplinks(text: str) -> str:
    out = re.sub(
        r"(?:https?://)?t\.me/[a-z0-9_]+/app(?:\?[^\s]*)?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"@[a-z0-9_]+/app(?:\?[^\s]*)?",
        " ",
        out,
        flags=re.IGNORECASE,
    )
    return out


def _strict_is_mentioned(text: str, chat_id_raw: object) -> bool:
    t = _strip_tg_webapp_deeplinks(text.lower())
    is_private_chat = False
    try:
        is_private_chat = int(str(chat_id_raw)) > 0
    except (TypeError, ValueError):
        is_private_chat = False

    if is_private_chat:
        return True

    for tok in _mention_tokens():
        if not tok:
            continue
        if tok.startswith("@"):
            if tok in t:
                return True
            continue
        if re.search(rf"(?<!\\w){re.escape(tok)}(?!\\w)", t):
            return True
    return False


def mention_checker(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Script-only mention checker that routes into one of two LLM guard nodes."""
    text = _extract_message_text(state)
    last_kwargs = getattr(state.last_external_message, "additional_kwargs", {}) or {}
    chat_id_raw = last_kwargs.get("chat_id")
    mentioned = _strict_is_mentioned(text=text, chat_id_raw=chat_id_raw)
    text_wo_webapp = _strip_tg_webapp_deeplinks(text)
    has_link_in_text = bool(re.search(r"(https?://\S+|t\.me/\S+)", text_wo_webapp, flags=re.IGNORECASE))
    has_link_in_meta = bool(last_kwargs.get("highlight_link") or last_kwargs.get("message_link"))
    state.strict_mention_detected = bool(mentioned)
    state.run_unmentioned_relevance_guard = bool((not mentioned) and (has_link_in_text or has_link_in_meta))
    state.chat_manager_triggered = False
    try:
        setattr(state, "bot_mentioned", bool(mentioned))
    except Exception:
        pass
    state.reasoning_messages = [SystemMessage(content="", name="mention_checker")]
    return state


def mentioned_quality_guard(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """
    Mention exists:
    - allow normal requests to continue
    - block obvious trolling/scam/mockery with a short response
    """
    text = _strip_tg_webapp_deeplinks(_extract_message_text(state).strip())
    state.mentioned_guard_blocked = False
    state.mentioned_guard_emoji = ""
    if not text:
        state.chat_manager_triggered = False
        state.reasoning_messages = [SystemMessage(content="", name="mentioned_quality_guard_skip_empty")]
        return state

    prompt = SystemMessage(
        content=(
            "You classify bot-directed messages.\n"
            "Return strict JSON only with fields:\n"
            "{\"allow\": boolean, \"reason\": string}\n"
            "allow=true: normal realistic request/question to bot.\n"
            "allow=false: trolling/mockery/flame/scam/noise OR absurd/nonsensical/unrealistic request.\n"
            "Examples of allow=false: meaningless provocation, impossible asks, hostile garbage.\n"
            "Be strict: if uncertain, allow=false.\n"
        ),
        name="mentioned_quality_guard_system",
    )
    result = {"allow": False, "reason": "fallback_block"}
    try:
        raw = llm.invoke([prompt, HumanMessage(content=text)]).content
        parsed = json.loads(str(raw))
        if isinstance(parsed, dict):
            result = {
                "allow": bool(parsed.get("allow", True)),
                "reason": str(parsed.get("reason", "") or ""),
            }
    except Exception:
        result = {"allow": False, "reason": "parse_error_fallback_block"}

    if not result["allow"]:
        state.chat_manager_triggered = False
        state.mentioned_guard_blocked = True
        try:
            setattr(state, "bot_mentioned", False)
        except Exception:
            pass
        cheerful_emoji = random.choice(["😎", "🤝", "🎉", "👏", "🔥", "😁", "🤩", "👌"])
        state.mentioned_guard_emoji = cheerful_emoji
        logging.info(
            "mentioned_quality_guard block: allow=%s reason=%s emoji=%s writer_present=%s",
            result.get("allow"),
            result.get("reason"),
            cheerful_emoji,
            bool(writer),
        )
        state.reasoning_messages = [SystemMessage(content="", name="mentioned_quality_guard_block")]
        return state

    state.chat_manager_triggered = True
    try:
        setattr(state, "bot_mentioned", True)
    except Exception:
        pass
    state.reasoning_messages = [SystemMessage(content="", name="mentioned_quality_guard_pass")]
    return state


def mentioned_block_response(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """Emit a short emoji response for blocked mentioned requests."""
    emoji = str(getattr(state, "mentioned_guard_emoji", "") or "").strip() or "🤝"
    state.reasoning_messages = [AIMessage(content=emoji, name="mentioned_block_response")]
    return state


def unmentioned_relevance_guard(state: InternalState, writer: StreamWriter | None = None) -> InternalState:
    """
    No mention:
    - pass only valuable materials/resources
    - otherwise skip silently (no response)
    """
    text = _strip_tg_webapp_deeplinks(_extract_message_text(state).strip())
    if not text:
        state.chat_manager_triggered = False
        state.reasoning_messages = [SystemMessage(content="", name="unmentioned_relevance_guard_skip_empty")]
        return state

    prompt = SystemMessage(
        content=(
            "You classify whether a non-mentioned Telegram message should be handled by chat manager.\n"
            "Return strict JSON only with fields:\n"
            "{\"allow\": boolean, \"reason\": string}\n"
            "allow=true only if message likely contains useful material/resource value\n"
            "(article, productivity content, relevant channel, useful service/job/resource).\n"
            "allow=false for memes, jokes, profile links, casual chatter, unclear noise.\n"
            "Be strict: if uncertain, allow=false.\n"
        ),
        name="unmentioned_relevance_guard_system",
    )
    result = {"allow": False, "reason": "fallback_block"}
    try:
        raw = llm.invoke([prompt, HumanMessage(content=text)]).content
        parsed = json.loads(str(raw))
        if isinstance(parsed, dict):
            result = {
                "allow": bool(parsed.get("allow", False)),
                "reason": str(parsed.get("reason", "") or ""),
            }
    except Exception:
        result = {"allow": False, "reason": "parse_error_fallback_block"}

    if not result["allow"]:
        state.chat_manager_triggered = False
        try:
            setattr(state, "bot_mentioned", False)
        except Exception:
            pass
        state.reasoning_messages = [SystemMessage(content="", name="unmentioned_relevance_guard_skip")]
        return state

    state.chat_manager_triggered = True
    try:
        setattr(state, "bot_mentioned", False)
    except Exception:
        pass
    state.reasoning_messages = [SystemMessage(content="", name="unmentioned_relevance_guard_pass")]
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
