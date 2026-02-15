from typing import Optional, Union, Any
from conversation_states.humans import Human
from conversation_states.improvements import Improvement


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
    # persist across checkpoints.
    by_username = {u.username: u for u in left}

    for ru in right:
        lu = by_username.get(ru.username)
        if lu is None:
            left.append(ru)
            by_username[ru.username] = ru
            continue

        if getattr(ru, "first_name", None):
            lu.first_name = ru.first_name
        if getattr(ru, "last_name", None) is not None:
            lu.last_name = ru.last_name
        if getattr(ru, "preferred_name", None) is not None:
            lu.preferred_name = ru.preferred_name
        if getattr(ru, "telegram_id", None) is not None:
            lu.telegram_id = ru.telegram_id
        if getattr(ru, "intro_message", None) is not None:
            ru_intro_message = str(ru.intro_message).strip()
            lu.intro_message = ru_intro_message or None

        # Preserve admin-set intro status across merges.
        if getattr(ru, "intro_locked", False):
            lu.intro_locked = True

        if getattr(lu, "intro_locked", False):
            if getattr(ru, "intro_locked", False):
                lu.intro_completed = bool(ru.intro_completed)
        else:
            lu.intro_completed = bool(ru.intro_completed)

        try:
            if getattr(ru, "information", None):
                lu.information.update(ru.information)
        except Exception:
            pass

    return left


def add_improvements(left: list["Improvement"], right: list["Improvement"]) -> list["Improvement"]:
    right = [i if isinstance(i, Improvement) else Improvement(**i) for i in right or []]

    by_id = {getattr(i, "id", None): i for i in left or [] if getattr(i, "id", None)}
    for ri in right:
        target = by_id.get(ri.id)
        if target is None:
            left.append(ri)
            by_id[ri.id] = ri
            continue

        target.category = ri.category
        target.description = ri.description
        target.reporter = ri.reporter
        target.status = ri.status
        target.task_number = ri.task_number
        target.resolution = ri.resolution
        target.closed_at = ri.closed_at
        target.created_at = ri.created_at
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
