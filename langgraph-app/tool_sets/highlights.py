from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from urllib.parse import urlparse
from uuid import uuid4
import re

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from conversation_states.highlights import Highlight
from conversation_states.states import InternalState


ALLOWED_CATEGORIES = {"jobs", "resources", "services"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_link(link: str) -> str:
    raw = (link or "").strip()
    if not raw:
        return ""
    # Legacy/invalid internal refs (scheme with underscore) or already-mangled variants.
    if raw.startswith("tg_message://"):
        return raw.replace("tg_message://", "tgmsg://", 1)
    m = re.match(r"^https?://tg_message//chat/([^/]+)/message/(\d+)$", raw)
    if m:
        return f"tgmsg://chat/{m.group(1)}/message/{m.group(2)}"

    parsed = urlparse(raw)
    # Keep valid custom internal refs as-is.
    if parsed.scheme == "tgmsg":
        return raw

    # Avoid converting unknown/custom schemes into fake https links.
    if "://" in raw and parsed.scheme and parsed.scheme not in {"http", "https"}:
        return raw

    path = parsed.path.rstrip("/")
    if not path:
        path = "/"
    host = parsed.netloc.lower()
    scheme = parsed.scheme.lower() or "https"
    return f"{scheme}://{host}{path}"


def _normalize_category(category: str) -> str:
    c = (category or "").strip().lower()
    return c if c in ALLOWED_CATEGORIES else ""


def _normalize_tags(tags: Optional[list[str]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for t in tags or []:
        v = str(t or "").strip().lower()
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _message_to_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()
    return str(content or "").strip()


def _build_tg_link(*, chat_id: str | None, chat_username: str | None, message_id: int | None) -> Optional[str]:
    if message_id is None:
        return None

    if chat_username:
        u = str(chat_username).lstrip("@").strip()
        if u:
            return f"https://t.me/{u}/{message_id}"

    s = str(chat_id or "").strip()
    if s.startswith("-100") and len(s) > 4:
        internal_id = s[4:]
        if internal_id.isdigit():
            return f"https://t.me/c/{internal_id}/{message_id}"

    return None


def _internal_message_ref(*, chat_id: str | None, message_id: int | None) -> Optional[str]:
    if chat_id is None or message_id is None:
        return None
    return f"tgmsg://chat/{chat_id}/message/{message_id}"


def _resolve_current_message_context(state: InternalState) -> tuple[Optional[dict], Optional[str]]:
    """
    Resolve current message context.
    Returns (payload, error).
    payload has: message_text, fallback_link, author_username, author_telegram_id
    """
    current = getattr(state, "last_external_message", None)
    if current is None:
        return (None, "current message is missing")
    current_kwargs = getattr(current, "additional_kwargs", {}) or {}
    current_link = current_kwargs.get("tg_link")
    current_mid_raw = current_kwargs.get("tg_message_id")
    try:
        current_mid = int(current_mid_raw) if current_mid_raw is not None else None
    except (TypeError, ValueError):
        current_mid = None
    if not isinstance(current_link, str) or not current_link.strip():
        current_link = _build_tg_link(
            chat_id=str(current_kwargs.get("chat_id") or current_kwargs.get("tg_chat_id") or "").strip() or None,
            chat_username=str(current_kwargs.get("chat_username") or "").strip() or None,
            message_id=current_mid,
        )
    if (not isinstance(current_link, str) or not current_link.strip()) and current_mid is not None:
        current_link = _internal_message_ref(
            chat_id=str(current_kwargs.get("chat_id") or current_kwargs.get("tg_chat_id") or "").strip() or None,
            message_id=current_mid,
        )

    message_text = _message_to_text(getattr(current, "content", ""))
    raw_uid = current_kwargs.get("tg_user_id")
    try:
        author_tg_id = int(raw_uid) if raw_uid is not None else None
    except (TypeError, ValueError):
        author_tg_id = None
    author_username = str(getattr(current, "name", "") or "").strip()

    if not message_text:
        return (None, "failed to derive message text from current message")

    return ({
        "message_text": message_text,
        "fallback_link": _normalize_link(str(current_link or "")) if current_link else None,
        "author_username": author_username,
        "author_telegram_id": author_tg_id,
    }, None)


def _add_single_highlight_impl(
    *,
    state: InternalState,
    context: dict,
    payload: dict,
) -> dict:
    normalized_category = _normalize_category(str(payload.get("category") or ""))
    if not normalized_category:
        return {"ok": False, "reason": "category must be one of: jobs, resources, services"}

    description = str(payload.get("highlight_description") or payload.get("description") or "").strip()
    if not description:
        return {"ok": False, "reason": "highlight_description is required"}

    incoming_link = payload.get("highlight_link")
    if incoming_link is None:
        incoming_link = payload.get("message_link")
    normalized_link = _normalize_link(str(incoming_link or ""))
    if not normalized_link:
        normalized_link = str(context.get("fallback_link") or "").strip()
    if not normalized_link:
        normalized_link = None

    message_text = str(context.get("message_text") or "").strip()
    if not message_text:
        return {"ok": False, "reason": "failed to derive message_text from current message"}

    existing = list(getattr(state, "highlights", []) or [])
    if normalized_link:
        for h in existing:
            if _normalize_link(str(getattr(h, "highlight_link", "") or "")) == normalized_link and getattr(h, "deleted_at", None) is None:
                return {
                    "ok": True,
                    "deduplicated": True,
                    "highlight_id": h.id,
                    "highlight": h.model_dump(mode="json"),
                }

    sender = getattr(state, "last_sender", None)
    final_username = str(context.get("author_username") or "").strip().lstrip("@")
    if not final_username and sender is not None:
        final_username = str(getattr(sender, "username", "") or "").strip()
    if not final_username:
        final_username = "unknown"

    final_tg_id = context.get("author_telegram_id")
    if final_tg_id is None and sender is not None:
        final_tg_id = getattr(sender, "telegram_id", None)

    rec = Highlight(
        id=uuid4().hex,
        category=normalized_category,  # type: ignore[arg-type]
        tags=_normalize_tags(payload.get("tags")),
        highlight_link=normalized_link,
        highlight_description=description,
        message_text=message_text,
        author_username=final_username,
        author_telegram_id=final_tg_id,
        published_at=_utc_now(),
        expires_at=None,
    )
    if state.highlights is None:
        state.highlights = []
    state.highlights.append(rec)
    return {"ok": True, "deduplicated": False, "highlight_id": rec.id, "highlight": rec.model_dump(mode="json")}


def _add_highlights_impl(
    *,
    state: InternalState,
    highlights: Optional[list[dict]] = None,
) -> dict:
    context, err = _resolve_current_message_context(state)
    if not context:
        return {"ok": False, "reason": err or "failed to resolve current message context"}

    items = list(highlights or [])
    if not items:
        return {"ok": False, "reason": "highlights list is required and must be non-empty"}

    added: list[dict] = []
    failed: list[dict] = []
    for idx, payload in enumerate(items):
        if not isinstance(payload, dict):
            failed.append({"index": idx, "ok": False, "reason": "item must be an object"})
            continue
        result = _add_single_highlight_impl(state=state, context=context, payload=payload)
        if result.get("ok"):
            added.append({"index": idx, **result})
        else:
            failed.append({"index": idx, **result})

    return {
        "ok": len(added) > 0,
        "added_count": len(added),
        "failed_count": len(failed),
        "added": added,
        "failed": failed,
    }


def _delete_highlight_impl(
    *,
    state: InternalState,
    highlight_id: Optional[str] = None,
    highlight_link: Optional[str] = None,
    message_link: Optional[str] = None,
    hard_delete: bool = False,
) -> dict:
    target_id = (highlight_id or "").strip()
    target_link = _normalize_link(highlight_link or message_link or "")
    if not target_id and not target_link:
        return {"ok": False, "reason": "highlight_id or highlight_link is required"}

    items = list(getattr(state, "highlights", []) or [])
    matched: list[Highlight] = []
    for h in items:
        if target_id and h.id == target_id:
            matched.append(h)
            continue
        if target_link and _normalize_link(str(h.highlight_link or "")) == target_link:
            matched.append(h)

    if not matched:
        return {"ok": False, "reason": "highlight not found", "deleted_count": 0, "deleted_ids": []}

    deleted_ids = [h.id for h in matched]
    if hard_delete:
        state.highlights = [h for h in items if h.id not in set(deleted_ids)]
    else:
        ts = _utc_now()
        for h in matched:
            h.deleted_at = ts

    return {"ok": True, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}


def _search_highlights_impl(
    *,
    state: InternalState,
    author_username: Optional[str] = None,
    author_telegram_id: Optional[int] = None,
    days: Optional[int] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    now = _utc_now()
    normalized_author = (author_username or "").strip().lstrip("@").lower()
    normalized_category = _normalize_category(category or "") if category else ""
    normalized_tags = set(_normalize_tags(tags))
    days_int = int(days) if days is not None else None
    if days_int is not None and days_int < 0:
        days_int = 0

    rows: list[Highlight] = list(getattr(state, "highlights", []) or [])
    filtered: list[Highlight] = []
    for h in rows:
        if h.deleted_at is not None:
            continue
        if h.expires_at is not None and h.expires_at < now:
            continue
        if normalized_author and h.author_username.lower() != normalized_author:
            continue
        if author_telegram_id is not None and h.author_telegram_id != int(author_telegram_id):
            continue
        if normalized_category and h.category != normalized_category:
            continue
        if days_int is not None and h.published_at < (now - timedelta(days=days_int)):
            continue
        if normalized_tags and not normalized_tags.intersection(set(h.tags or [])):
            continue
        filtered.append(h)

    filtered.sort(key=lambda r: r.published_at, reverse=True)
    safe_offset = max(0, int(offset))
    safe_limit = min(max(1, int(limit)), 100)
    page = filtered[safe_offset:safe_offset + safe_limit]

    return {
        "ok": True,
        "total": len(filtered),
        "items": [r.model_dump(mode="json") for r in page],
    }


def _trending_highlights_impl(
    *,
    state: InternalState,
    days: int = 5,
    category: Optional[str] = None,
    limit: int = 10,
) -> dict:
    base = _search_highlights_impl(
        state=state,
        days=days,
        category=category,
        limit=100,
        offset=0,
    )
    if not base.get("ok"):
        return base

    now = _utc_now()
    enriched = []
    for item in base.get("items", []):
        try:
            published_at = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
        except Exception:
            published_at = now
        age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
        freshness = max(0.0, 1.0 - (age_hours / max(days * 24, 1)))
        score = round(freshness, 4)
        enriched.append({**item, "score": score})

    enriched.sort(key=lambda i: (i.get("score", 0.0), i.get("published_at", "")), reverse=True)
    safe_limit = min(max(1, int(limit)), 100)
    return {"ok": True, "total": len(enriched), "items": enriched[:safe_limit]}


@tool
def add_highlights(
    highlights: list[dict],
    state: Annotated[InternalState, InjectedState],
) -> dict:
    """
    Add one or more highlights from the current user message.

    Parameters:
    - highlights (required): Array of highlight objects.
      Every object may include:
      - category (required): Top-level category. Allowed values: jobs, resources, services.
      - highlight_description (required): Human-readable highlight summary.
      - highlight_link (optional): Source link as-is (do not normalize manually in LLM).
      - tags (optional): List of semantic tags inferred from message context.

    Tags examples:
    - article
    - ai-product
    - design
    - product-strategy
    - ux-research

    Auto-filled in background (do not pass from LLM):
    - message_text
    - author_username
    - author_telegram_id
    - published_at

    highlight_link fallback:
    - if not provided, tool tries Telegram metadata from current message
    - if unavailable, highlight is still saved with empty link
    """
    return _add_highlights_impl(
        state=state,
        highlights=highlights,
    )


@tool
def delete_highlight(
    state: Annotated[InternalState, InjectedState],
    highlight_id: Optional[str] = None,
    highlight_link: Optional[str] = None,
    hard_delete: bool = False,
) -> dict:
    """Delete highlight by id or highlight_link. Soft-delete by default."""
    return _delete_highlight_impl(
        state=state,
        highlight_id=highlight_id,
        highlight_link=highlight_link,
        hard_delete=hard_delete,
    )


@tool
def search_highlights(
    state: Annotated[InternalState, InjectedState],
    author_username: Optional[str] = None,
    author_telegram_id: Optional[int] = None,
    days: Optional[int] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """
    Search useful saved highlights by user, recent days, top-level category, and tags.

    Returns structured items including highlight_description, message_text, and highlight_link.
    """
    return _search_highlights_impl(
        state=state,
        author_username=author_username,
        author_telegram_id=author_telegram_id,
        days=days,
        category=category,
        tags=tags,
        limit=limit,
        offset=offset,
    )


@tool
def trending_highlights(
    state: Annotated[InternalState, InjectedState],
    days: int = 5,
    category: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """Return top recent highlights (useful links/materials) ranked by freshness."""
    return _trending_highlights_impl(
        state=state,
        days=days,
        category=category,
        limit=limit,
    )


__all__ = [
    "add_highlights",
    "delete_highlight",
    "search_highlights",
    "trending_highlights",
    "_add_highlights_impl",
    "_delete_highlight_impl",
    "_search_highlights_impl",
    "_trending_highlights_impl",
]
