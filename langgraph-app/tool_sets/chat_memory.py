from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from conversation_states.memory import MemoryFrom, MemoryRecord
from conversation_states.states import InternalState


def _normalize_category(category: str) -> str:
    c = (category or "").strip()
    return c or "Без категории"


def _add_memory_record_impl(
    *,
    state: InternalState,
    category: str,
    text: str,
    from_username: Optional[str] = None,
) -> str:
    sender = getattr(state, "last_sender", None)
    created_by = MemoryFrom()
    if sender:
        created_by = MemoryFrom(
            username=sender.username,
            telegram_id=getattr(sender, "telegram_id", None),
            first_name=getattr(sender, "first_name", None),
            last_name=getattr(sender, "last_name", None),
            preferred_name=getattr(sender, "preferred_name", None),
        )
    if from_username:
        created_by.username = from_username.lstrip("@").strip() or created_by.username

    rec = MemoryRecord(
        id=uuid4().hex,
        created_at=datetime.now(timezone.utc),
        category=_normalize_category(category),
        text=(text or "").strip(),
        from_user=created_by,
    )

    if state.memory_records is None:
        state.memory_records = []
    state.memory_records.append(rec)
    return rec.id


def _list_memory_records_impl(*, state: InternalState) -> list[dict]:
    items = list(getattr(state, "memory_records", []) or [])
    items.sort(key=lambda r: r.created_at, reverse=True)
    return [r.model_dump(mode="json") for r in items]


def _get_unique_categories_impl(*, state: InternalState) -> list[str]:
    cats = []
    seen = set()
    for r in (getattr(state, "memory_records", []) or []):
        c = (getattr(r, "category", None) or "").strip()
        if not c:
            continue
        if c in seen:
            continue
        seen.add(c)
        cats.append(c)
    cats.sort(key=lambda s: s.lower())
    return cats


@tool
def add_memory_record(
    category: str,
    text: str,
    state: Annotated[InternalState, InjectedState],
    from_username: Optional[str] = None,
) -> str:
    """
    Add a new idea/task/note to the thread-level ideas log.

    Use this for abstract notes without a specific resource link.
    If the user is saving a useful link/material (article/video/channel/tool/job/service),
    use add_highlights instead.

    Args:
    - category: str (e.g., "Предложение")
    - text: str (e.g., "Добавить в чат топики")
    - from_username: optional override; by default uses the message sender.

    Returns:
    - record id (str)
    """
    return _add_memory_record_impl(
        state=state,
        category=category,
        text=text,
        from_username=from_username,
    )


@tool
def list_memory_records(
    state: Annotated[InternalState, InjectedState],
) -> list[dict]:
    """Return all idea records (most recent first)."""
    return _list_memory_records_impl(state=state)


@tool
def get_unique_categories(
    state: Annotated[InternalState, InjectedState],
) -> list[str]:
    """Return all unique categories currently stored in memory records."""
    return _get_unique_categories_impl(state=state)


__all__ = [
    "add_memory_record",
    "list_memory_records",
    "get_unique_categories",
    "_add_memory_record_impl",
    "_list_memory_records_impl",
    "_get_unique_categories_impl",
]
