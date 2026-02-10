from conversation_states.states import ExternalState
from conversation_states.actions import ActionSender, Action
from langgraph.types import StreamWriter
from config import is_admin


ADMIN_PANEL_SENDER_NAME = "admin_panel"


def router(state: ExternalState) -> ExternalState:
    return state


def get_current_user(state: ExternalState):
    """Get current message sender."""
    if not state.users:
        return None
    last_message = state.messages[-1]
    sender_name = getattr(last_message, "name", None)
    if not sender_name:
        return None
    if sender_name == ADMIN_PANEL_SENDER_NAME:
        # Not a real user from `state.users`. Used by the admin panel.
        return None
    # Find user by username
    for user in state.users:
        if user.username == sender_name:
            return user
    return None


def show_all_users_prep(state: ExternalState) -> ExternalState:
    """Prepare to show all users - remove command message."""
    state.messages_api.remove_last()
    return state


def show_all_users(state: ExternalState, writer: StreamWriter) -> ExternalState:
    """Show all users from all groups with intro status (admin only)."""
    sender = ActionSender(writer)

    # Check permissions
    current_user = get_current_user(state)
    if current_user and current_user.telegram_id and is_admin(current_user.telegram_id):
        pass
    else:
        last_message = state.messages[-1] if state.messages else None
        sender_name = getattr(last_message, "name", None)
        if sender_name != ADMIN_PANEL_SENDER_NAME:
            message = "❌ Access denied. This command is only available to administrators."
            action = Action(type="system-message", value=message)
            sender.send_action(action)
            return state

    # Show users from current state
    if not state.users:
        message = "👥 No users found in current conversation."
    else:
        user_lines = []
        for user in state.users:
            intro_status = "✅" if user.intro_completed else "❌"
            name = f"{user.first_name} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "No username"
            user_lines.append(f"{intro_status} {name} ({username})")

        message = "👥 Users in current conversation:\n\n" + "\n".join(user_lines)
        message += "\n\n✅ = Intro completed\n❌ = No intro"

    action = Action(type="system-message", value=message)
    sender.send_action(action)
    return state


def set_intro_status_prep(state: ExternalState) -> ExternalState:
    # Keep the command message until the action node parses it.
    return state


def _parse_intro_bool(token: str) -> bool | None:
    t = (token or "").strip().lower()
    if t in {"done", "completed", "complete", "true", "1", "yes", "y", "on"}:
        return True
    if t in {"pending", "not_done", "notdone", "false", "0", "no", "n", "off"}:
        return False
    return None


def _parse_set_intro_command(text: str) -> tuple[str, bool] | None:
    # Expected: /set_intro_status <@username|telegram:ID|ID|all> <done|pending>
    if not isinstance(text, str):
        return None
    parts = text.strip().split()
    if len(parts) < 3:
        return None
    if parts[0] != "/set_intro_status":
        return None
    target = parts[1].strip()
    if target.startswith("@"):
        target = target[1:]
    status = _parse_intro_bool(parts[2])
    if status is None:
        return None
    return (target, status)


def set_intro_status(state: ExternalState, writer: StreamWriter) -> ExternalState:
    """Admin command: update users[*].intro_completed and persist via checkpoint."""
    sender = ActionSender(writer)

    # Permissions: allow if caller is a known admin user OR the admin panel.
    last_message = state.messages[-1] if state.messages else None
    sender_name = getattr(last_message, "name", None)
    current_user = get_current_user(state)

    allowed = False
    if sender_name == ADMIN_PANEL_SENDER_NAME:
        allowed = True
    elif current_user and current_user.telegram_id and is_admin(current_user.telegram_id):
        allowed = True

    if not allowed:
        message = "❌ Access denied. This command is only available to administrators."
        sender.send_action(Action(type="system-message", value=message))
        return state

    command_text = getattr(last_message, "content", "") if last_message else ""
    parsed = _parse_set_intro_command(command_text)
    if not parsed:
        message = "❌ Invalid command. Usage: /set_intro_status <@username|telegram:ID|ID|all> <done|pending>"
        sender.send_action(Action(type="system-message", value=message))
        return state

    target, status = parsed
    if not state.users:
        sender.send_action(Action(type="system-message", value="❌ No users in this thread."))
        return state

    updated = 0
    if target.lower() == "all":
        for u in state.users:
            u.intro_completed = status
            updated += 1
    else:
        # Support telegram:ID or raw ID.
        telegram_id = None
        t = target.lower()
        if t.startswith("telegram:"):
            try:
                telegram_id = int(t.split("telegram:", 1)[1])
            except Exception:
                telegram_id = None
        elif t.isdigit():
            try:
                telegram_id = int(t)
            except Exception:
                telegram_id = None

        for u in state.users:
            if telegram_id is not None and u.telegram_id == telegram_id:
                u.intro_completed = status
                updated += 1
            elif telegram_id is None and u.username == target:
                u.intro_completed = status
                updated += 1

    if updated == 0:
        sender.send_action(Action(type="system-message", value=f"❌ User not found: {target}"))
        return state

    # Remove the admin command message so it doesn't clutter thread history.
    try:
        state.messages_api.remove_last()
    except Exception:
        pass

    sender.send_action(
        Action(
            type="system-message",
            value=f"✅ Updated intro status for {updated} user(s) to {'done' if status else 'pending'}.",
        )
    )
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
