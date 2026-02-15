from __future__ import annotations

import json
import random
import re
import logging
import base64
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import Field
from openai import OpenAI

from conversation_states.memory import MemoryRecord
from conversation_states.states import ExternalState
from conversation_states.actions import Action, ActionSender


class DailySummaryState(ExternalState):
    node1_selected: list[dict] = Field(default_factory=list)
    node2_payload: dict = Field(default_factory=dict)
    window_since_utc: str | None = None
    window_until_utc: str | None = None


llm = ChatOpenAI(model="gpt-4.1-2025-04-14", temperature=0.2)
# Final user-facing digest phrasing.
llm_style = ChatOpenAI(model="gpt-5-mini", temperature=0.7)
image_client = OpenAI()
log = logging.getLogger("daily_summary_graph")

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

DAILY_VOICE_PROBABILITY = 0.25


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


def _window_bounds(
    state: DailySummaryState,
    config: RunnableConfig | None,
    *,
    now_utc: datetime,
) -> tuple[datetime, datetime]:
    # Primary source: values passed in run input (stable across runtimes).
    since_utc = _parse_dt(getattr(state, "window_since_utc", None))
    until_utc = _parse_dt(getattr(state, "window_until_utc", None))
    if since_utc and until_utc:
        if since_utc >= until_utc:
            return until_utc - timedelta(hours=24), until_utc
        return since_utc, until_utc

    # Secondary source: configurable context.
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
        if not isinstance(m, HumanMessage):
            continue
        dt, link = _extract_tg_meta(m)
        if not dt or dt < since_utc or dt > until_utc:
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


def _collect_new_participants_count(
    state: ExternalState,
    *,
    since_utc: datetime,
    until_utc: datetime,
) -> int:
    before: set[str] = set()
    recent: set[str] = set()
    for m in (state.messages or []):
        if not isinstance(m, HumanMessage):
            continue
        dt, _ = _extract_tg_meta(m)
        if not dt:
            continue
        author = getattr(m, "name", None) or "unknown"
        if since_utc <= dt <= until_utc:
            recent.add(author)
        elif dt < since_utc:
            before.add(author)
    return len(recent - before)


def _collect_intro_messages_in_window(
    state: ExternalState,
    *,
    since_utc: datetime,
    until_utc: datetime,
    tz: ZoneInfo,
) -> list[dict]:
    msgs = _collect_messages_in_window(state, since_utc=since_utc, until_utc=until_utc, tz=tz)
    return [m for m in msgs if "#intro" in (m.get("text", "").lower())]


def _collect_records_in_window(
    state: ExternalState,
    *,
    since_utc: datetime,
    until_utc: datetime,
    tz: ZoneInfo,
) -> list[dict]:
    out: list[dict] = []
    recs: list[MemoryRecord] = list(getattr(state, "memory_records", []) or [])
    for r in recs:
        created = _parse_dt(getattr(r, "created_at", None))
        if not created or created < since_utc or created > until_utc:
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


def node1_select_top5(state: DailySummaryState, config: RunnableConfig | None = None) -> dict:
    tz_name = _get_tz_name(state)
    tz = _safe_zoneinfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    since_utc, until_utc = _window_bounds(state, config, now_utc=now_utc)
    recent = _collect_messages_in_window(state, since_utc=since_utc, until_utc=until_utc, tz=tz)

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
            f"Now UTC: {until_utc.isoformat(timespec='minutes')}\n"
            f"Window since UTC: {since_utc.isoformat(timespec='minutes')}\n"
            f"Window until UTC: {until_utc.isoformat(timespec='minutes')}\n"
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


def node2_aggregate(state: DailySummaryState, config: RunnableConfig | None = None) -> dict:
    tz_name = _get_tz_name(state)
    tz = _safe_zoneinfo(tz_name)
    now_utc = datetime.now(timezone.utc)
    since_utc, until_utc = _window_bounds(state, config, now_utc=now_utc)

    selected = list(getattr(state, "node1_selected", []) or [])
    intro_messages = _collect_intro_messages_in_window(state, since_utc=since_utc, until_utc=until_utc, tz=tz)
    records_24h = _collect_records_in_window(state, since_utc=since_utc, until_utc=until_utc, tz=tz)
    new_participants_count = _collect_new_participants_count(state, since_utc=since_utc, until_utc=until_utc)

    payload = {
        "window": {
            "timezone": tz_name,
            "since_utc": since_utc.isoformat(timespec="minutes"),
            "until_utc": until_utc.isoformat(timespec="minutes"),
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


def node3_compose_message(state: DailySummaryState) -> dict:
    if str(os.getenv("DAILY_RUNNER_DISABLE_SUMMARY", "")).strip().lower() in {"1", "true", "yes", "on"}:
        return {"messages": [AIMessage(content="__NO_UPDATES__", name="daily_runner")]}
    payload = dict(getattr(state, "node2_payload", {}) or {})
    if payload.get("no_updates") is True:
        return {"messages": [AIMessage(content="__NO_UPDATES__", name="daily_runner")]}

    tone = random.choice(TONE_VARIANTS)
    greeting = random.choice(GREETING_VARIANTS)
    closing = random.choice(CLOSING_VARIANTS)

    prompt = (
        "Ты пишешь дайджест за указанный период на русском.\n"
        "- Верни только ГОТОВЫЙ ФИНАЛЬНЫЙ ТЕКСТ сообщения\n"
        "- Формат Telegram: обычный текст + HTML-ссылки.\n"
        "- Если пункт ссылается на сообщение, используй HTML-ссылку из 1-2 слов внутри фразы. Пример: Новый участник <a href=\"https://t.me/c/1/2\">представился</a> в чате.\n\n"
        "<тон>\n"
        f"- {tone}\n"
        f"- Приветствие/вступление: {greeting}\n"
        f"- Пожелание/Прощание: {closing}\n"
        "</тон>\n\n"
        "<структура ответа>\n"
        "- Приветствие/вступление: обязательно укажи, что это сводка/дайджест за указанный период.\n"
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


def node4_generate_image(state: DailySummaryState, writer=None) -> dict:
    payload = dict(getattr(state, "node2_payload", {}) or {})
    if payload.get("no_updates") is True:
        return {}

    # Find the final digest text generated in node3.
    digest_text = ""
    for m in reversed(list(getattr(state, "messages", []) or [])):
        if isinstance(m, AIMessage) and (getattr(m, "name", "") == "daily_runner"):
            digest_text = str(getattr(m, "content", "") or "").strip()
            if digest_text:
                break
    if not digest_text:
        return {}

    prompt = (
        "Create an illustration based on the community news from the digest context below.\n"
        "The image must reflect the actual topics, mood, and activity of the community updates.\n"
        "No logos, no brand marks, no watermarks.\n"
        "Avoid text-heavy image; if text appears, keep it very short and readable.\n\n"
        "Style:\n"
        "Digital painting, polished illustration, soft cinematic lighting, warm golden hour glow, "
        "smooth painterly shading, soft shadows without harsh outlines, subtle highlight glow on light areas, airy atmosphere.\n\n"
        "Fixed Color Palette:\n"
        "- Warm golden #F6C36B\n"
        "- Soft peach #F2A07B\n"
        "- Light cream #F5E6D3\n"
        "- Warm beige #D8B89C\n"
        "- Muted sage green #8FAF9A\n"
        "- Soft olive green #6E8B6A\n"
        "- Dusty sky blue #A7C0D8\n"
        "- Warm brown #8B5E3C\n\n"
        "Overall image temperature: warm.\n"
        "No cold blue shadows.\n"
        "Moderate contrast, no blown highlights.\n\n"
        "Faces:\n"
        "Aesthetically cute faces, soft facial features, smooth clean skin (no rough texture), subtle natural blush, "
        "large expressive eyes, gentle light reflection in the eyes, natural proportions, slight glossy skin highlights but not plastic-looking.\n\n"
        "Lighting:\n"
        "Warm directional side lighting (like window light), soft diffusion, slight depth of field, "
        "background slightly softer than the main subject.\n\n"
        "Rendering:\n"
        "High detail, smooth brush strokes, clean rendering, soft color transitions, subtle highlights, "
        "semi-realistic digital art, no rough painterly texture.\n\n"
        "Overall Mood:\n"
        "Cozy, calm, creative atmosphere, balanced composition, clean framing, warm and inviting tone.\n\n"
        "Digest context:\n"
        f"{digest_text[:1600]}"
    )

    try:
        img = image_client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )
        b64 = (img.data[0].b64_json if img and img.data else None) or ""
        if not b64:
            return {}

        # Validate base64 early; if invalid do nothing.
        base64.b64decode(b64)
        if writer:
            sender = ActionSender(writer)
            sender.send_action(
                Action(
                    type="image",
                    value=json.dumps(
                        {
                            "b64_json": b64,
                            "mime_type": "image/png",
                        },
                        ensure_ascii=False,
                    ),
                )
            )
    except Exception:
        log.exception("node4_generate_image failed")
    return {}


def node5_generate_voice(state: DailySummaryState, writer=None) -> dict:
    payload = dict(getattr(state, "node2_payload", {}) or {})
    if payload.get("no_updates") is True:
        return {}

    # Reuse the final digest text generated in node3.
    digest_text = ""
    for m in reversed(list(getattr(state, "messages", []) or [])):
        if isinstance(m, AIMessage) and (getattr(m, "name", "") == "daily_runner"):
            digest_text = str(getattr(m, "content", "") or "").strip()
            if digest_text:
                break
    if not digest_text:
        return {}

    try:
        # Simple random gate: generate voice with fixed probability.
        prob = DAILY_VOICE_PROBABILITY
        roll = random.random()
        if roll >= prob:
            log.info("node5 voice skipped by probability gate roll=%.4f prob=%.4f", roll, prob)
            return {}

        voice_prompt = (
            "На основе дайджеста ниже напиши одну короткую вдохновляющую и поддерживающую фразу для участников сообщества.\n"
            "Требования:\n"
            "- 15-20 слов;\n"
            "- русский язык;\n"
            "- дружеский, неформальный, живой тон;\n"
            "- без пафоса, без громких лозунгов, без канцелярита;\n"
            "- звучит как сообщение от знакомого человека в чате;\n"
            "- без эмодзи, без хэштегов, без кавычек;\n"
            "- только финальный текст, без пояснений.\n\n"
            "Дайджест:\n"
            f"{digest_text[:1800]}"
        )
        voice_raw = llm_style.invoke([HumanMessage(content=voice_prompt)]).content
        voice_text = str(voice_raw or "").strip().replace("\n", " ")
        words = [w for w in voice_text.split() if w.strip()]
        if not (15 <= len(words) <= 20):
            voice_text = (
                "Спасибо за активность сегодня: двигаемся дальше, поддерживаем друг друга и превращаем идеи в сильные результаты вместе."
            )

        tts_model = os.getenv("OPENAI_TTS_MODEL", "tts-1")
        tts_voice = os.getenv("OPENAI_TTS_VOICE", "Ash").strip().lower()
        log.info("node5 voice_text=%r model=%s voice=%s prob=%.4f roll=%.4f", voice_text[:300], tts_model, tts_voice, prob, roll)
        speech = image_client.audio.speech.create(
            model=tts_model,
            voice=tts_voice,
            input=voice_text,
            response_format="opus",
        )

        audio_bytes = None
        if hasattr(speech, "read"):
            audio_bytes = speech.read()
        elif hasattr(speech, "content"):
            audio_bytes = speech.content
        elif isinstance(speech, (bytes, bytearray)):
            audio_bytes = bytes(speech)

        if not audio_bytes:
            return {}

        b64 = base64.b64encode(audio_bytes).decode("ascii")
        if writer:
            sender = ActionSender(writer)
            sender.send_action(
                Action(
                    type="voice",
                    value=json.dumps(
                        {
                            "b64": b64,
                            "mime_type": "audio/ogg",
                            "filename": "daily_digest.ogg",
                        },
                        ensure_ascii=False,
                    ),
                )
            )
    except Exception:
        log.exception("node5_generate_voice failed")
    return {}


builder = StateGraph(DailySummaryState)
builder.add_node("node1_select_top5", node1_select_top5)
builder.add_node("node2_aggregate", node2_aggregate)
builder.add_node("node3_compose_message", node3_compose_message)
builder.add_node("node4_generate_image", node4_generate_image)
builder.add_node("node5_generate_voice", node5_generate_voice)

builder.add_edge(START, "node1_select_top5")
builder.add_edge("node1_select_top5", "node2_aggregate")
builder.add_edge("node2_aggregate", "node3_compose_message")
builder.add_edge("node3_compose_message", "node4_generate_image")
builder.add_edge("node4_generate_image", "node5_generate_voice")
builder.add_edge("node5_generate_voice", END)

graph_daily_summary = builder.compile()
