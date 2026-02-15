from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Annotated, Optional, Any
from uuid import uuid4

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from conversation_states.improvements import Improvement
from conversation_states.states import InternalState


ALLOWED_CATEGORIES = {"bug", "feature"}
ALLOWED_STATUSES = {"open", "closed", "wont_do", "all"}
_INC_RE = re.compile(r"^INC(\d{5})$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_category(category: str | None) -> str:
    value = str(category or "").strip().lower()
    if value in ALLOWED_CATEGORIES:
        return value
    return ""


def _normalize_status(status: str | None) -> str:
    value = str(status or "open").strip().lower()
    if value in ALLOWED_STATUSES:
        return value
    return ""


def _normalize_reporter(reporter: str | None) -> str | None:
    value = str(reporter or "").strip().lstrip("@")
    if not value:
        return None
    return value


def _default_reporter_from_state(state: InternalState) -> str | None:
    sender = getattr(state, "last_sender", None)
    if sender is None:
        return None
    username = str(getattr(sender, "username", "") or "").strip().lstrip("@")
    if username:
        return username
    first_name = str(getattr(sender, "first_name", "") or "").strip()
    return first_name or None


def _next_inc_number(state: InternalState) -> str:
    max_n = 0
    for item in list(getattr(state, "improvements", []) or []):
        task = str(getattr(item, "task_number", "") or "").strip().upper()
        m = _INC_RE.match(task)
        if not m:
            continue
        try:
            max_n = max(max_n, int(m.group(1)))
        except Exception:
            continue
    return f"INC{max_n + 1:05d}"


def _public_improvement(item: Improvement) -> dict:
    # Never expose internal UUID to LLM-facing tool outputs.
    return item.model_dump(mode="json", exclude={"id"})


def _add_improvement_one(
    *,
    state: InternalState,
    description: str,
    category: str,
    reporter: Optional[str] = None,
) -> dict:
    normalized_category = _normalize_category(category)
    if not normalized_category:
        return {"ok": False, "reason": "category must be one of: bug, feature"}

    final_description = str(description or "").strip()
    if not final_description:
        return {"ok": False, "reason": "description is required"}

    final_reporter = _normalize_reporter(reporter) or _default_reporter_from_state(state)

    rec = Improvement(
        id=uuid4().hex,
        task_number=_next_inc_number(state),
        category=normalized_category,  # type: ignore[arg-type]
        description=final_description,
        reporter=final_reporter,
        status="open",
        created_at=_utc_now(),
    )
    if state.improvements is None:
        state.improvements = []
    state.improvements.append(rec)
    return {"ok": True, "task_number": rec.task_number, "improvement": _public_improvement(rec)}


def _normalize_batch_item(item: Any) -> dict | None:
    if not isinstance(item, dict):
        return None
    return {
        "description": item.get("description"),
        "category": item.get("category"),
        "reporter": item.get("reporter"),
    }


def _add_improvement_impl(
    *,
    state: InternalState,
    improvements: list[dict],
) -> dict:
    items: list[dict] = []

    if isinstance(improvements, list) and len(improvements) > 0:
        for raw in improvements:
            normalized = _normalize_batch_item(raw)
            if normalized is not None:
                items.append(normalized)

    if not items:
        return {
            "ok": False,
            "reason": "improvements[] is required and must be non-empty",
        }

    added: list[dict] = []
    errors: list[dict] = []
    for idx, it in enumerate(items):
        result = _add_improvement_one(
            state=state,
            description=it.get("description"),
            category=it.get("category"),
            reporter=it.get("reporter"),
        )
        if result.get("ok") is True:
            added.append(
                {
                    "index": idx,
                    "task_number": result.get("task_number"),
                    "improvement": result.get("improvement"),
                }
            )
        else:
            errors.append(
                {
                    "index": idx,
                    "reason": str(result.get("reason") or "unknown_error"),
                    "input": {
                        "description": it.get("description"),
                        "category": it.get("category"),
                        "reporter": it.get("reporter"),
                    },
                }
            )

    out: dict[str, Any] = {
        "ok": len(errors) == 0 and len(added) > 0,
        "added_count": len(added),
        "error_count": len(errors),
        "added": added,
        "errors": errors,
    }
    return out


def _list_improvements_impl(
    *,
    state: InternalState,
    status: str = "open",
    days: int = 60,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    normalized_status = _normalize_status(status)
    if not normalized_status:
            return {"ok": False, "reason": "status must be one of: open, closed, wont_do, all"}

    normalized_category = ""
    if category is not None and str(category).strip().lower() not in {"", "all"}:
        normalized_category = _normalize_category(category)
        if not normalized_category:
            return {"ok": False, "reason": "category must be one of: bug, feature, all"}

    safe_days = max(0, int(days))
    cutoff = _utc_now() - timedelta(days=safe_days)

    rows = list(getattr(state, "improvements", []) or [])
    filtered: list[Improvement] = []
    for item in rows:
        if item.created_at < cutoff:
            continue
        if normalized_status != "all" and item.status != normalized_status:
            continue
        if normalized_category and item.category != normalized_category:
            continue
        filtered.append(item)

    filtered.sort(key=lambda i: i.created_at, reverse=True)
    safe_offset = max(0, int(offset))
    safe_limit = min(max(1, int(limit)), 500)
    page = filtered[safe_offset:safe_offset + safe_limit]

    return {"ok": True, "total": len(filtered), "items": [_public_improvement(i) for i in page]}


@tool
def add_improvement(
    state: Annotated[InternalState, InjectedState],
    improvements: list[dict],
) -> dict:
    """
    Add one or many bot improvement items in a single call.

    Required:
    - improvements: array of items
      item fields:
        - description (required)
        - category (required): bug or feature
        - reporter (optional)

    Auto-filled in background:
    - created_at
    - status=open
    """
    return _add_improvement_impl(
        state=state,
        improvements=improvements,
    )


@tool
def list_improvements(
    state: Annotated[InternalState, InjectedState],
    status: str = "open",
    days: int = 60,
    category: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    List improvement items by status/category for the last N days.

    Filters:
    - status: open, closed, wont_do, all (default: open)
    - days: recent window in days (default: 60)
    - category: bug, feature, all/None
    """
    return _list_improvements_impl(
        state=state,
        status=status,
        days=days,
        category=category,
        limit=limit,
        offset=offset,
    )


__all__ = [
    "add_improvement",
    "list_improvements",
    "_add_improvement_impl",
    "_list_improvements_impl",
]
