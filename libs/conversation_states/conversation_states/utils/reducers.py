from typing import Optional, Union, Any
from conversation_states.humans import Human
from conversation_states.highlights import Highlight
from conversation_states.improvements import Improvement
from conversation_states.memory import MemoryRecord


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
        if getattr(ru, "intro_message", None) is not None:
            ru_intro_message = str(ru.intro_message).strip()
            lu.intro_message = ru_intro_message or None

        # Preserve admin-set intro status across merges.
        # Most "normal" user updates don't know intro status and would default to False,
        # which would otherwise revert a manual "done" back to "pending".
        if getattr(ru, "intro_locked", False):
            lu.intro_locked = True

        if getattr(lu, "intro_locked", False):
            # Only allow changes from another locked update.
            if getattr(ru, "intro_locked", False):
                lu.intro_completed = bool(ru.intro_completed)
        else:
            # Booleans overwrite when not locked.
            lu.intro_completed = bool(ru.intro_completed)

        # Merge info dict.
        try:
            if getattr(ru, "information", None):
                lu.information.update(ru.information)
        except Exception:
            pass

    return left


def add_memory_records(left: list["MemoryRecord"], right: list["MemoryRecord"]) -> list["MemoryRecord"]:
    # Normalize dict payloads from checkpoints.
    right = [r if isinstance(r, MemoryRecord) else MemoryRecord(**r) for r in right or []]

    by_id = {getattr(r, "id", None): r for r in left or [] if getattr(r, "id", None)}
    for rr in right:
        rid = getattr(rr, "id", None)
        if not rid:
            # Skip malformed records (should not happen, but don't crash reducers).
            continue
        if rid in by_id:
            # If duplicated, prefer the newer snapshot.
            existing = by_id[rid]
            existing.created_at = rr.created_at
            existing.category = rr.category
            existing.text = rr.text
            existing.from_user = rr.from_user
        else:
            left.append(rr)
            by_id[rid] = rr
    return left


def add_highlights(left: list["Highlight"], right: list["Highlight"]) -> list["Highlight"]:
    right = [h if isinstance(h, Highlight) else Highlight(**h) for h in right or []]

    by_id = {getattr(h, "id", None): h for h in left or [] if getattr(h, "id", None)}
    by_link = {
        str(getattr(h, "highlight_link", "")).strip(): h
        for h in left or []
        if isinstance(getattr(h, "highlight_link", None), str) and str(getattr(h, "highlight_link", "")).strip()
    }

    for rh in right:
        rh_link = str(rh.highlight_link or "").strip()
        target = by_id.get(rh.id) or (by_link.get(rh_link) if rh_link else None)
        if target is None:
            left.append(rh)
            by_id[rh.id] = rh
            if rh_link:
                by_link[rh_link] = rh
            continue

        target.category = rh.category
        target.tags = list(rh.tags or [])
        target.highlight_link = rh.highlight_link
        target.highlight_description = rh.highlight_description
        target.message_text = rh.message_text
        target.author_username = rh.author_username
        target.author_telegram_id = rh.author_telegram_id
        target.published_at = rh.published_at
        target.expires_at = rh.expires_at
        target.deleted_at = rh.deleted_at

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
