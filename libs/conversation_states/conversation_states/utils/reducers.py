from typing import Optional, Union, Any
from conversation_states.humans import Human


def add_summary(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a

    return b


def add_user(left: list["Human"], right: list["Human"]) -> list["Human"]:
    right = [u if isinstance(u, Human) else Human(**u)
             for u in right or []]

    # Merge by username so updates to existing users (e.g. intro_completed, info)
    # persist across checkpoints. Previous behavior only appended new users.
    by_username = {u.username: u for u in left}

    for ru in right:
        lu = by_username.get(ru.username)
        if lu is None:
            left.append(ru)
            by_username[ru.username] = ru
            continue

        # Prefer values from the right side when they are present.
        # Keep stable identifiers (username) and preserve list order by mutating.
        if getattr(ru, "first_name", None):
            lu.first_name = ru.first_name
        if getattr(ru, "last_name", None) is not None:
            lu.last_name = ru.last_name
        if getattr(ru, "preferred_name", None) is not None:
            lu.preferred_name = ru.preferred_name
        if getattr(ru, "telegram_id", None) is not None:
            lu.telegram_id = ru.telegram_id

        # Booleans should overwrite (explicit True/False).
        lu.intro_completed = bool(ru.intro_completed)

        # Merge info dict.
        try:
            if getattr(ru, "information", None):
                lu.information.update(ru.information)
        except Exception:
            pass

    return left


def manage_state(
    a: Optional[Union["InternalState", list[Any]]],
    b: Optional[Union["InternalState", list[Any]]]
) -> Optional[Union["InternalState", list[Any]]]:
    def is_empty(val):
        return val is None or val == []
    if is_empty(a) and is_empty(b):
        return None
    if is_empty(a):
        return b
    if is_empty(b):
        return a
    return b
