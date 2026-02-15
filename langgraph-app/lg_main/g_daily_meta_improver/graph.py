from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field, ValidationError

from conversation_states.improvements import Improvement
from conversation_states.states import ExternalState
from conversation_states.actions import Action, ActionSender


class DailyMetaImproverState(ExternalState):
    thread_meta: dict = Field(default_factory=dict)
    thread_info_entries_input: list[str] = Field(default_factory=list)
    thread_info_entries_reviewed: list[str] = Field(default_factory=list)
    window_since_utc: str | None = None
    window_until_utc: str | None = None


llm = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=0.2)
log = logging.getLogger("daily_meta_improver_graph")
META_IMPROVER_REPORTER = "meta-improver---auto"
_INC_RE = re.compile(r"^INC(\d{5})$")


def _safe_zoneinfo(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _get_tz_name(state: ExternalState) -> str:
    for u in (state.users or []):
        info = getattr(u, "information", None) or {}
        if not isinstance(info, dict):
            continue
        tz = info.get("timezone")
        if isinstance(tz, str) and tz.strip():
            return tz.strip()
    return "UTC"


def _parse_dt(val: object) -> datetime | None:
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str) and val.strip():
        try:
            dt = datetime.fromisoformat(val.strip())
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _extract_tg_meta(msg: BaseMessage) -> tuple[datetime | None, str | None]:
    ak = getattr(msg, "additional_kwargs", None) or {}
    if not isinstance(ak, dict):
        return None, None
    dt = _parse_dt(ak.get("tg_date"))
    link = ak.get("tg_link")
    if link is not None:
        link = str(link).strip() or None
    return dt, link


def _window_bounds(
    state: DailyMetaImproverState,
    config: RunnableConfig | None,
    *,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    since_utc = _parse_dt(getattr(state, "window_since_utc", None))
    until_utc = _parse_dt(getattr(state, "window_until_utc", None))
    if since_utc and until_utc:
        if since_utc >= until_utc:
            return until_utc - timedelta(hours=24), until_utc
        return since_utc, until_utc

    cfg = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    if not isinstance(cfg, dict):
        cfg = {}
    since_utc = _parse_dt(cfg.get("daily_window_since_utc"))
    until_utc = _parse_dt(cfg.get("daily_window_until_utc")) or now_utc
    if since_utc is None:
        since_utc = until_utc - timedelta(hours=24)
    if since_utc >= until_utc:
        since_utc = until_utc - timedelta(hours=24)
    return since_utc, until_utc


def _collect_messages_in_window(
    state: ExternalState,
    *,
    since_utc: datetime,
    until_utc: datetime,
    tz: ZoneInfo,
) -> list[dict]:
    out: list[dict] = []
    for m in (state.messages or []):
        if not isinstance(m, (HumanMessage, AIMessage)):
            continue
        dt, link = _extract_tg_meta(m)
        if not dt or dt < since_utc or dt > until_utc:
            continue
        if isinstance(m, AIMessage):
            role = "assistant"
            author = getattr(m, "name", None) or "assistant"
        else:
            role = "user"
            author = f"@{(getattr(m, 'name', None) or 'unknown')}"
        text = str(getattr(m, "content", "") or "").strip().replace("\n", " ")
        if len(text) > 350:
            text = text[:350].rstrip() + "…"
        out.append(
            {
                "at_local": dt.astimezone(tz).isoformat(timespec="minutes"),
                "at_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes"),
                "role": role,
                "author": author,
                "text": text,
                "link": link,
            }
        )
    out.sort(key=lambda x: x["at_utc"])
    return out


def _clean_thread_info_entries(raw: object, *, max_items: int = 40) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        text = str(x or "").strip()
        if not text:
            continue
        words = [w for w in text.split() if w.strip()]
        text = " ".join(words[:15]).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _normalize_reporter_name(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text.lstrip("@")


class ImprovementLLMItem(BaseModel):
    task_number: str | None = None
    category: Literal["bug", "feature"]
    description: str
    status: Literal["open", "closed", "wont_do"]
    resolution: str | None = None
    closed_at: datetime | None = None
    reporter: str | None = None


class ImprovementLLMResponse(BaseModel):
    improvements: list[ImprovementLLMItem] = Field(default_factory=list)


def _to_iso_or_none(value: object) -> str | None:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str):
        dt = _parse_dt(value)
        if dt is not None:
            return dt.isoformat()
    return None


def _current_improvements(state: DailyMetaImproverState) -> list[dict]:
    out: list[dict] = []
    for item in list(getattr(state, "improvements", []) or []):
        if isinstance(item, Improvement):
            i = item
        elif isinstance(item, dict):
            try:
                i = Improvement(**item)
            except Exception:
                continue
        else:
            continue
        out.append(
            {
                "task_number": i.task_number,
                "category": i.category,
                "description": i.description,
                "reporter": i.reporter,
                "status": i.status,
                "resolution": i.resolution,
                "closed_at": _to_iso_or_none(i.closed_at),
                "created_at": _to_iso_or_none(i.created_at),
            }
        )
    return out


def _current_improvement_identity_map(state: DailyMetaImproverState) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for item in list(getattr(state, "improvements", []) or []):
        if isinstance(item, Improvement):
            i = item
        elif isinstance(item, dict):
            try:
                i = Improvement(**item)
            except Exception:
                continue
        else:
            continue
        task = str(i.task_number or "").strip().upper()
        if not _INC_RE.match(task):
            continue
        out[task] = {
            "id": i.id,
            "task_number": task,
            "created_at": _to_iso_or_none(i.created_at),
            "reporter": i.reporter,
        }
    return out


def _next_inc_number(current: list[dict]) -> str:
    max_n = 0
    for item in current:
        t = str(item.get("task_number") or "").strip().upper()
        m = _INC_RE.match(t)
        if not m:
            continue
        try:
            max_n = max(max_n, int(m.group(1)))
        except Exception:
            continue
    return f"INC{max_n + 1:05d}"


def _normalize_improvements_for_state(
    items: list[ImprovementLLMItem],
    current: list[dict],
    identity_by_task: dict[str, dict],
) -> list[dict]:
    now = datetime.now(timezone.utc)
    existing_by_task: dict[str, dict] = {}
    for i in current:
        task = str(i.get("task_number") or "").strip().upper()
        if task:
            existing_by_task[task] = i

    out: list[dict] = []
    for x in items:
        description = str(x.description or "").strip()
        if not description:
            continue
        existing = None
        x_task = str(x.task_number or "").strip().upper()
        if x_task and x_task in existing_by_task:
            existing = existing_by_task[x_task]
        identity = identity_by_task.get(x_task) if x_task else None

        category = str(x.category).strip().lower()
        status = str(x.status).strip().lower()
        resolution = str(x.resolution or "").strip() or None
        closed_at = _to_iso_or_none(x.closed_at)
        if status in {"closed", "wont_do"} and not closed_at:
            closed_at = now.isoformat()
        if status == "open":
            closed_at = None

        created_at = (
            (identity.get("created_at") if identity else None)
            or (_to_iso_or_none(existing.get("created_at")) if existing else None)
            or now.isoformat()
        )
        task_number = (
            str((identity.get("task_number") if identity else None) or "").strip().upper()
            or (str(existing.get("task_number") or "").strip().upper() if existing else "")
            or str(x.task_number or "").strip().upper()
        )
        if not _INC_RE.match(task_number):
            task_number = _next_inc_number(current + out)

        reporter = (
            _normalize_reporter_name(x.reporter)
            or (_normalize_reporter_name(identity.get("reporter")) if identity else None)
            or (_normalize_reporter_name(existing.get("reporter")) if existing else None)
            or META_IMPROVER_REPORTER
        )
        out.append(
            {
                "id": (str(identity.get("id")) if identity else None) or uuid4().hex,
                "task_number": task_number,
                "category": category,
                "description": description,
                "reporter": reporter,
                "status": status,
                "resolution": resolution,
                "closed_at": closed_at,
                "created_at": created_at,
            }
        )
    return out


def node_review_thread_info(state: DailyMetaImproverState, config: RunnableConfig | None = None, writer=None) -> dict:
    tz_name = _get_tz_name(state)
    tz = _safe_zoneinfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    since_utc, until_utc = _window_bounds(state, config, now_utc=now_utc)
    recent = _collect_messages_in_window(state, since_utc=since_utc, until_utc=until_utc, tz=tz)

    meta = getattr(state, "thread_meta", None)
    if not isinstance(meta, dict):
        meta = {}

    current_entries = _clean_thread_info_entries(
        getattr(state, "thread_info_entries_input", None)
        or meta.get("thread_info")
        or []
    )

    pinned = meta.get("pinned_message")
    if not isinstance(pinned, dict):
        pinned = {}

    other_meta: dict = {}
    for k, v in meta.items():
        if not isinstance(k, str):
            continue
        if k in {"chat_title", "chat_username", "chat_description", "pinned_message", "thread_info"}:
            continue
        if k.startswith("daily_runner_"):
            continue
        if v in (None, "", [], {}):
            continue
        if isinstance(v, str) and len(v) > 500:
            other_meta[k] = v[:500].rstrip() + "…"
            continue
        if isinstance(v, (str, int, float, bool, list, dict)):
            other_meta[k] = v

    meta_scope = {
        "chat_title": str(meta.get("chat_title") or "").strip(),
        "chat_username": str(meta.get("chat_username") or "").strip(),
        "chat_description": str(meta.get("chat_description") or "").strip(),
        "pinned_message": {
            "message_id": str(pinned.get("message_id") or "").strip(),
            "text": str(pinned.get("text") or "").strip(),
        },
        "thread_info_existing": current_entries,
        "other_relevant_metadata": other_meta,
    }

    if (
        len(recent) == 0
        and not meta_scope["chat_title"]
        and not meta_scope["chat_description"]
        and not meta_scope["pinned_message"]["text"]
    ):
        return {"thread_info_entries_reviewed": current_entries}

    system = SystemMessage(
        content=(
            "Ты модератор знаний о чате. Верни ТОЛЬКО валидный JSON.\n"
            "Нужно проверить текущие thread info entries и обновить их только при необходимости.\n"
            "Сохраняй полезные актуальные записи, добавляй недостающие, удаляй устаревшие/дубли.\n"
            "Требования к entries:\n"
            "- каждая запись это отдельный statement, максимум 15 слов;\n"
            "- без воды, без повторов;\n"
            "- покрыть: о чем чат, проф. направленность, правила (1 правило = 1 запись),\n"
            "  важные вещи, за которыми участникам стоит следить.\n"
            "Формат JSON:\n"
            "{\n"
            '  "entries": ["...", "..."]\n'
            "}\n"
            "Никакого текста вне JSON."
        )
    )
    user = HumanMessage(
        content=(
            f"Timezone: {tz_name}\n"
            f"Window since UTC: {since_utc.isoformat(timespec='minutes')}\n"
            f"Window until UTC: {until_utc.isoformat(timespec='minutes')}\n"
            "Thread metadata JSON:\n"
            f"{json.dumps(meta_scope, ensure_ascii=False)}\n"
            "Messages in window JSON:\n"
            f"{json.dumps(recent, ensure_ascii=False)}"
        )
    )
    log.info("node_review llm prompt system=%s", system.content)
    log.info("node_review llm prompt user=%s", user.content)

    raw = llm.invoke([system, user]).content
    data: dict = {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        data = {}

    reviewed = _clean_thread_info_entries(data.get("entries"))
    if not reviewed:
        reviewed = current_entries

    if writer and reviewed != current_entries:
        sender = ActionSender(writer)
        sender.send_action(
            Action(
                type="system-notification",
                value=json.dumps(
                    {"kind": "thread_info_entries", "entries": reviewed},
                    ensure_ascii=False,
                ),
            )
        )
    return {"thread_info_entries_reviewed": reviewed}


def node_review_improvements(state: DailyMetaImproverState, config: RunnableConfig | None = None) -> dict:
    tz_name = _get_tz_name(state)
    tz = _safe_zoneinfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    since_utc, until_utc = _window_bounds(state, config, now_utc=now_utc)
    recent = _collect_messages_in_window(state, since_utc=since_utc, until_utc=until_utc, tz=tz)
    reviewed_entries = _clean_thread_info_entries(getattr(state, "thread_info_entries_reviewed", []) or [])
    current = _current_improvements(state)
    identity_by_task = _current_improvement_identity_map(state)
    schema_json = json.dumps(ImprovementLLMResponse.model_json_schema(), ensure_ascii=False)

    system = SystemMessage(
        content=(
            "Ты продуктовый менеджер и QA чат-агента. Верни ТОЛЬКО валидный JSON.\n"
            "Задача: по сообщениям, thread info и текущим improvements собрать обновления по improvements.\n"
            "Найди баги, проблемы UX, недостающие фичи, слабые места. Учитывай только реальный контекст.\n"
            "Анализируй сообщения пользователей И ответы бота (assistant).\n"
            "Если по контексту ожидалась реакция/ответ бота, но ее нет или она не по делу, "
            "добавляй improvement (обычно bug) с кратким контекстом.\n"
            "Если запись уже существует, верни ее с тем же task_number и новыми полями при необходимости.\n"
            "Если есть дубликаты, ОБЯЗАТЕЛЬНО пометь дубликат как status=wont_do и укажи в resolution, что это дубликат.\n"
            "Считай дубликатом и случай, когда bug и feature описывают одну проблему разными словами "
            "(например: 'бот спамит' и 'бот не должен спамить'). "
            "Оставляй одну каноническую запись, вторую помечай как status=wont_do с причиной duplicate.\n"
            "Для дубликатов оставляй одного из существующих авторов/reporter.\n"
            "Новые записи добавляй с reporter=meta-improver---auto, если нет явного автора.\n"
            "Если что-то делать не нужно (треш/нереалистично/вне scope), пометь status=wont_do и дай причину в resolution.\n"
            "Статусы только на английском: open, closed, wont_do.\n"
            "Следуй JSON Schema ниже:\n"
            f"{schema_json}\n"
            "Никакого текста вне JSON."
        )
    )
    user = HumanMessage(
        content=(
            f"Timezone: {tz_name}\n"
            f"Window since UTC: {since_utc.isoformat(timespec='minutes')}\n"
            f"Window until UTC: {until_utc.isoformat(timespec='minutes')}\n"
            "Thread info entries JSON:\n"
            f"{json.dumps(reviewed_entries, ensure_ascii=False)}\n"
            "Messages in window JSON:\n"
            f"{json.dumps(recent, ensure_ascii=False)}\n"
            "Current improvements JSON:\n"
            f"{json.dumps(current, ensure_ascii=False)}"
        )
    )
    log.info("node_improvements llm prompt system=%s", system.content)
    log.info("node_improvements llm prompt user=%s", user.content)

    raw = llm.invoke([system, user]).content
    data: object = {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        data = {}
    try:
        parsed = ImprovementLLMResponse.model_validate(data)
    except ValidationError:
        log.warning("node_review_improvements: LLM response schema validation failed")
        return {}
    normalized = _normalize_improvements_for_state(
        parsed.improvements,
        current=current,
        identity_by_task=identity_by_task,
    )
    if not normalized:
        return {}
    return {"improvements": normalized}


builder = StateGraph(DailyMetaImproverState)
builder.add_node("node_review_thread_info", node_review_thread_info)
builder.add_node("node_review_improvements", node_review_improvements)

builder.add_edge(START, "node_review_thread_info")
builder.add_edge("node_review_thread_info", "node_review_improvements")
builder.add_edge("node_review_improvements", END)

graph_daily_meta_improver = builder.compile()
