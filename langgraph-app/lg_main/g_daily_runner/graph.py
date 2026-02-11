from __future__ import annotations

import json
import random
import re
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import Field

from conversation_states.memory import MemoryRecord
from conversation_states.states import ExternalState


class DailyRunnerState(ExternalState):
    node1_selected: list[dict] = Field(default_factory=list)
    node2_payload: dict = Field(default_factory=dict)


llm = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=0.2)
# Final user-facing digest phrasing.
llm_style = ChatOpenAI(model="gpt-5-mini", temperature=0.7)
log = logging.getLogger("daily_runner_graph")

_URL_RE = re.compile(r"https?://\S+")

TONE_VARIANTS = [
    "спокойный и аналитичный, без пафоса",
    "дружелюбный и деловой, коротко по сути",
    "бодрый, но профессиональный и аккуратный",
    "уверенный, структурный, с легким оптимизмом",
]

GREETING_VARIANTS = [
    "поддерживающее",
    "дружелюбное",
    "короткое и бодрое",
    "спокойное и уверенное",
]

CLOSING_VARIANTS = [
    "вдохновляющее",
    "теплое и ободряющее",
    "энергичное и позитивное",
    "спокойно мотивирующее",
]


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


def _extract_tg_meta(msg: HumanMessage) -> tuple[datetime | None, str | None]:
    ak = getattr(msg, "additional_kwargs", None) or {}
    if not isinstance(ak, dict):
        return None, None
    dt = _parse_dt(ak.get("tg_date"))
    link = ak.get("tg_link")
    if link is not None:
        link = str(link).strip() or None
    return dt, link


def _collect_messages_last_24h(state: ExternalState, *, now_utc: datetime, tz: ZoneInfo) -> list[dict]:
    since_utc = now_utc - timedelta(hours=24)
    out: list[dict] = []
    for m in (state.messages or []):
        if not isinstance(m, HumanMessage):
            continue
        dt, link = _extract_tg_meta(m)
        if not dt or dt < since_utc:
            continue
        author = getattr(m, "name", None) or "unknown"
        text = str(getattr(m, "content", "") or "").strip().replace("\n", " ")
        if len(text) > 350:
            text = text[:350].rstrip() + "…"
        out.append(
            {
                "at_local": dt.astimezone(tz).isoformat(timespec="minutes"),
                "at_utc": dt.astimezone(timezone.utc).isoformat(timespec="minutes"),
                "author": f"@{author}",
                "text": text,
                "link": link,
            }
        )
    out.sort(key=lambda x: x["at_utc"])
    return out


def _collect_new_participants_count(state: ExternalState, *, now_utc: datetime) -> int:
    since_utc = now_utc - timedelta(hours=24)
    before: set[str] = set()
    recent: set[str] = set()
    for m in (state.messages or []):
        if not isinstance(m, HumanMessage):
            continue
        dt, _ = _extract_tg_meta(m)
        if not dt:
            continue
        author = getattr(m, "name", None) or "unknown"
        if dt >= since_utc:
            recent.add(author)
        else:
            before.add(author)
    return len(recent - before)


def _collect_intro_messages_last_24h(state: ExternalState, *, now_utc: datetime, tz: ZoneInfo) -> list[dict]:
    msgs = _collect_messages_last_24h(state, now_utc=now_utc, tz=tz)
    return [m for m in msgs if "#intro" in (m.get("text", "").lower())]


def _collect_records_last_24h(state: ExternalState, *, now_utc: datetime, tz: ZoneInfo) -> list[dict]:
    since_utc = now_utc - timedelta(hours=24)
    out: list[dict] = []
    recs: list[MemoryRecord] = list(getattr(state, "memory_records", []) or [])
    for r in recs:
        created = _parse_dt(getattr(r, "created_at", None))
        if not created or created < since_utc:
            continue
        text = str(getattr(r, "text", "") or "").strip().replace("\n", " ")
        if len(text) > 350:
            text = text[:350].rstrip() + "…"
        category = str(getattr(r, "category", "") or "").strip() or "Без категории"
        from_user = getattr(r, "from_user", None)
        username = getattr(from_user, "username", None) if from_user else None
        out.append(
            {
                "at_local": created.astimezone(tz).isoformat(timespec="minutes"),
                "at_utc": created.astimezone(timezone.utc).isoformat(timespec="minutes"),
                "category": category,
                "text": text,
                "author": f"@{username}" if username else "@unknown",
            }
        )
    out.sort(key=lambda x: x["at_utc"])
    return out


def node1_select_top5(state: DailyRunnerState) -> dict:
    tz_name = _get_tz_name(state)
    tz = _safe_zoneinfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    recent = _collect_messages_last_24h(state, now_utc=now_utc, tz=tz)

    if not recent:
        return {"node1_selected": []}

    system = SystemMessage(
        content=(
            "Ты аналитик чата. Верни ТОЛЬКО валидный JSON.\n"
            "Нужно выбрать не более 5 сообщений из входного списка (список может быть пустым или иметь 1-4 пункта если нет 5 важных сообщений).\n"
            "Критерии включения:\n"
            "- интересные или полезные для большинства участников;\n"
            "- есть запрос, проблема, решение, полезная ссылка, идея, организационный апдейт;\n"
            "- потенциально важные сообщения, которые стоит знать всем.\n"
            "Критерии исключения:\n"
            "- флуд, small talk, мемы без пользы, личные перепалки;\n"
            "- узкоспециальные или локальные сообщения, неинтересные большинству.\n"
            "Формат JSON:\n"
            "{\n"
            '  "selected": [\n'
            "    {\n"
            '      "text": \"...\",\n'
            '      "author": \"@user\",\n'
            '      "link": \"https://... или null\",\n'
            '      "type": \"interesting|request|important\",\n'
            '      "why": \"короткая причина\"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Никакого текста вне JSON."
        )
    )
    user = HumanMessage(
        content=(
            f"Timezone: {tz_name}\n"
            f"Now UTC: {now_utc.isoformat(timespec='minutes')}\n"
            "Messages JSON:\n"
            + json.dumps(recent, ensure_ascii=False)
        )
    )
    log.info("node1 llm prompt system=%s", system.content)
    log.info("node1 llm prompt user=%s", user.content)

    raw = llm.invoke([system, user]).content
    data: dict = {}
    try:
        data = json.loads(raw) if isinstance(raw, str) else {}
    except Exception:
        data = {}

    selected = data.get("selected") if isinstance(data.get("selected"), list) else []
    clean: list[dict] = []
    for x in selected:
        if not isinstance(x, dict):
            continue
        text = str(x.get("text") or "").strip()
        author = str(x.get("author") or "").strip()
        if not text:
            continue
        item = {
            "text": text,
            "author": author or "@unknown",
            "link": (str(x.get("link")).strip() if x.get("link") else None),
            "type": str(x.get("type") or "important").strip(),
            "why": str(x.get("why") or "").strip(),
        }
        clean.append(item)
        if len(clean) >= 5:
            break

    # Fallback only if LLM returned nothing and we have messages
    if len(clean) == 0 and len(recent) > 0:
        # Take up to 3 most recent messages as fallback
        fallback = recent[-3:]
        clean = [
            {
                "text": m["text"],
                "author": m["author"],
                "link": m["link"],
                "type": "important",
                "why": "Фоллбек: последнее активное сообщение",
            }
            for m in fallback
        ]

    return {"node1_selected": clean[:5]}


def node2_aggregate(state: DailyRunnerState) -> dict:
    tz_name = _get_tz_name(state)
    tz = _safe_zoneinfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=24)

    selected = list(getattr(state, "node1_selected", []) or [])
    intro_messages = _collect_intro_messages_last_24h(state, now_utc=now_utc, tz=tz)
    records_24h = _collect_records_last_24h(state, now_utc=now_utc, tz=tz)
    new_participants_count = _collect_new_participants_count(state, now_utc=now_utc)

    payload = {
        "window": {
            "timezone": tz_name,
            "since_utc": since_utc.isoformat(timespec="minutes"),
            "until_utc": now_utc.isoformat(timespec="minutes"),
        },
        "selected_messages": selected,
        "new_participants_count": new_participants_count,
        "intro_messages": intro_messages,
        "new_records": records_24h,
    }
    payload["no_updates"] = (
        (len(selected) == 0)
        and (new_participants_count == 0)
        and (len(intro_messages) == 0)
        and (len(records_24h) == 0)
    )
    return {"node2_payload": payload}


def node3_compose_message(state: DailyRunnerState) -> dict:
    payload = dict(getattr(state, "node2_payload", {}) or {})
    if payload.get("no_updates") is True:
        return {"messages": [AIMessage(content="__NO_UPDATES__", name="daily_runner")]}

    tone = random.choice(TONE_VARIANTS)
    greeting = random.choice(GREETING_VARIANTS)
    closing = random.choice(CLOSING_VARIANTS)

    prompt = (
        "Ты пишешь ежедневный дайджест за последние 24 часа на русском.\n"
        "- Верни только ГОТОВЫЙ ФИНАЛЬНЫЙ ТЕКСТ сообщения\n"
        "- Формат Telegram: обычный текст + HTML-ссылки.\n"
        "- Если пункт ссылается на сообщение, используй HTML-ссылку из 1-2 слов внутри фразы. Пример: Новый участник <a href=\"https://t.me/c/1/2\">представился</a> в чате.\n\n"
        "<тон>\n"
        f"- {tone}\n"
        f"- Приветствие/вступление: {greeting}\n"
        f"- Пожелание/Прощание: {closing}\n"
        "</тон>\n\n"
        "<структура ответа>\n"
        "- Приветствие/вступление: обязательно укажи, что это сводка/дайджест за последние сутки/24 часа.\n"
        "- Пустая строка\n"
        "- Самые важные 2-3 пункта списком, каждый <= 15 слов.\n"
        "- [Опционально, только если есть еще другие важные события] Пустая строка\n"
        "- [Опционально, только если есть еще другие важные события] Краткий саммари блок с другими важными вещами что выше не упомянуто <= 20 слов.\n"
        "- Пустая строка\n"
        "- Пожелание/прощание\n"
        "</структура ответа>\n\n"
        "<данные>\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n"
        "</данные>"
    )
    user = HumanMessage(content=prompt)
    log.info("node3 style_variants tone=%s greeting=%s closing=%s", tone, greeting, closing)
    log.info("node3 llm prompt=%s", prompt)

    raw = llm_style.invoke([user]).content
    text = str(raw or "").strip()
    return {"messages": [AIMessage(content=text, name="daily_runner")]}


builder = StateGraph(DailyRunnerState)
builder.add_node("node1_select_top5", node1_select_top5)
builder.add_node("node2_aggregate", node2_aggregate)
builder.add_node("node3_compose_message", node3_compose_message)

builder.add_edge(START, "node1_select_top5")
builder.add_edge("node1_select_top5", "node2_aggregate")
builder.add_edge("node2_aggregate", "node3_compose_message")
builder.add_edge("node3_compose_message", END)

graph_daily_runner = builder.compile()
