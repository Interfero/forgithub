"""
Оскорбления в чате: классификация, счётчик сессии, обида на показатели боеготовности.
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal

INSULT_THRESHOLD = 3
OFFENDED_SECONDS = 30 * 60
ANGRY_FLASH_SECONDS = 4.5

INSULT_MEMORY_FILENAME = "Оскорбления_Jarvis.md"

InsultKind = Literal["none", "venting", "at_jarvis"]

INSULT_RE = re.compile(
    r"\b(дурак|идиот|идиотк|идиотк\w*|тупой|тупая|тупое|тупиц\w*|чучело|дебил|дебилк\w*|"
    r"кретин|урод|мусор|отстой|говн\w*|дерьм\w*|сука|сучк\w*|бляд\w*|блять|блядь|"
    r"хуй|хуе\w*|пизд\w*|ебан\w*|ёбан\w*|ёб\w*|еб\w*|ублюд\w*|придур\w*|"
    r"тварь|скотин\w*|ничтожеств\w*|осёл|осел|козёл|козел|мудак|мудил\w*|"
    r"болван|рукожоп|тупиц\w*|придур\w*|мразь|падаль|отмороз\w*)\b",
    re.I,
)
PHRASE_RE = re.compile(
    r"(иди\s*на|пошёл\s*на|пошел\s*на|заткнись|заткни\s*рот|"
    r"ты\s+бот\s+для\s+идиот|хуесос|пидор|пидар|мразь|пошёл\s*вон|пошел\s*вон)",
    re.I,
)
AT_JARVIS_RE = re.compile(
    r"\b(ты|тебя|тебе|тобой|твой|твоя|твоё|твои|те|"
    r"jarvis|джарвис|бот|ассистент|нейросет\w*|ии\b|программ\w*)\b",
    re.I,
)
VENTING_ABOUT_OTHER_RE = re.compile(
    r"\b(он[аи]?|она|они|начальник|клиент|начальство|коллег|"
    r"работ[аеуи]|жизнь|погод|дождь|пробк|муж|жена|дети)\b",
    re.I,
)
MEME_VENTING_RE = re.compile(
    r"хуй\s+будешь|хуй\s+тебе|на\s+хуй\s+ид|пошёл\s+на\s+хуй|пошел\s+на\s+хуй|"
    r"нихуя\s+себе|охуенн|заебись|заебал[аи]?\s+(?:день|работ|погод)",
    re.I,
)


def message_looks_like_insult_conservative(text: str) -> bool:
    """Явные шаблоны без широкого словаря (меньше ложных срабатываний)."""
    t = (text or "").strip()
    if len(t) < 2:
        return False
    return bool(INSULT_RE.search(t) or PHRASE_RE.search(t))


def message_looks_like_insult(text: str, *, use_lexicon: bool = True) -> bool:
    t = (text or "").strip()
    if len(t) < 2:
        return False
    if message_looks_like_insult_conservative(t):
        return True
    if not use_lexicon:
        return False
    try:
        from modules.insult_lexicon import ensure_lexicon_ready, message_matches_lexicon

        ensure_lexicon_ready()
        return message_matches_lexicon(t)
    except Exception:
        return False


def classify_insult(
    text: str,
    session_id: str | None = None,
    *,
    moderation: Any | None = None,
) -> InsultKind:
    """
    Классификация с трёхслойной модерацией (правила → ML → контекст).
    После OK модерации — только консервативные regex, без широкого словаря.
    """
    t = (text or "").strip()
    if len(t) < 2:
        return "none"

    if MEME_VENTING_RE.search(t):
        return "venting"

    sid = (session_id or "default").strip() or "default"
    mod = moderation
    if mod is None:
        try:
            from modules.moderation import moderate_message

            mod = moderate_message(t, sid)
        except Exception:
            mod = None
    if mod is not None:
        if mod.action == "BLOCK":
            return "at_jarvis" if mod.jarvis_directed else "venting"
        if mod.counts_as_insult:
            return "at_jarvis"
        if mod.action == "WARN":
            return "venting"

    if not message_looks_like_insult_conservative(t):
        return "none"
    low = t.lower()
    if re.match(r"^(блять?|блин|чёрт|черт|ёб|еб|хуй|пизд\w*)[\s,.!?]*$", low, re.I):
        return "venting"
    if VENTING_ABOUT_OTHER_RE.search(low) and not re.search(r"\bты\b", low, re.I):
        return "venting"
    if INSULT_RE.search(low) and not AT_JARVIS_RE.search(low):
        return "venting"
    if AT_JARVIS_RE.search(low):
        return "at_jarvis"
    return "venting"


def is_offended(rt: Any) -> bool:
    return float(getattr(rt, "offended_until", 0) or 0) > time.time()


def is_angry_flash(rt: Any) -> bool:
    return float(getattr(rt, "last_insult_angry_until", 0) or 0) > time.time()


def reset_insult_session(rt: Any, session_id: str | None = None) -> None:
    rt.session_insult_count = 0
    rt.offended_until = 0.0
    rt.last_insult_angry_until = 0.0
    rt.last_insult_request_id = ""
    rt.last_insult_at_jarvis = False
    rt.last_insult_excerpt = ""
    try:
        from modules.moderation import get_moderation_module

        mod = get_moderation_module()
        sid = (session_id or "default").strip() or "default"
        mod.context.reset_session(sid)
    except Exception:
        pass
    # Сброс только счётчика; +30 к настроению — через on_insult_restart / RESTART


def offended_remaining_sec(rt: Any) -> int:
    left = float(getattr(rt, "offended_until", 0) or 0) - time.time()
    return max(0, int(left))


def insult_status_payload(rt: Any) -> dict[str, Any]:
    now = time.time()
    offended_until = float(getattr(rt, "offended_until", 0) or 0)
    angry_until = float(getattr(rt, "last_insult_angry_until", 0) or 0)
    return {
        "session_count": int(getattr(rt, "session_insult_count", 0) or 0),
        "threshold": INSULT_THRESHOLD,
        "offended": offended_until > now,
        "offended_until": offended_until if offended_until > now else None,
        "angry_until": angry_until if angry_until > now else None,
        "offended_remaining_sec": max(0, int(offended_until - now)),
    }


def insult_api_response(
    *,
    kind: InsultKind,
    counted: bool,
    rt: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": kind,
        "counted": counted,
        "insult": insult_status_payload(rt),
    }
    try:
        from modules.jarvis_mood import mood_status_payload

        payload["mood"] = mood_status_payload(rt)
    except Exception:
        pass
    return payload


def append_insult_to_conscious(
    *,
    count: int,
    excerpt: str,
    kind: str,
    offended: bool,
) -> None:
    from modules.memory_store import CONSCIOUS_DIR

    CONSCIOUS_DIR.mkdir(parents=True, exist_ok=True)
    path = CONSCIOUS_DIR / INSULT_MEMORY_FILENAME
    stamp = time.strftime("%Y-%m-%d %H:%M")
    quote = (excerpt or "").strip().replace("\n", " ")
    if len(quote) > 220:
        quote = quote[:217] + "…"
    line = (
        f"- [{stamp}] Шеф: «{quote}» — "
        f"{'оскорбление Jarvis' if kind == 'at_jarvis' else kind}; "
        f"счётчик сессии: {count}"
    )
    if offended:
        line += "; Jarvis обиделся на 30 мин"
    block = f"\n{line}\n"
    if path.exists():
        old = path.read_text(encoding="utf-8", errors="replace")
        if len(old) > 80_000:
            old = old[-60_000:]
        path.write_text(old + block, encoding="utf-8")
    else:
        path.write_text(
            "# Оскорбления Jarvis (сознательное)\n"
            "Моменты из чата, когда Шеф грубо обращался к Jarvis.\n"
            + block,
            encoding="utf-8",
        )
    try:
        from modules import jarvis_db

        jarvis_db.sync_all_from_disk()
    except Exception:
        pass


def process_user_message_insult(
    content: str,
    rt: Any,
    request_id: str | None = None,
    session_id: str | None = None,
    *,
    moderation: Any | None = None,
) -> dict[str, Any]:
    """Регистрация оскорбления. Повтор с тем же request_id не увеличивает счётчик."""
    sid = (session_id or request_id or "default").strip() or "default"
    kind = classify_insult(content, session_id=sid, moderation=moderation)
    if kind == "none":
        rt.last_insult_at_jarvis = False
        rt.last_insult_excerpt = ""
        return insult_api_response(kind="none", counted=False, rt=rt)

    req = (request_id or "").strip()
    if req and req == getattr(rt, "last_insult_request_id", ""):
        return insult_api_response(
            kind=kind,
            counted=kind == "at_jarvis",
            rt=rt,
        )

    now = time.time()

    if kind == "venting":
        rt.log(
            "insult.venting",
            "Шеф выругался, но не в адрес Jarvis — счётчик не меняем.",
        )
        if req:
            rt.last_insult_request_id = req
        return insult_api_response(kind="venting", counted=False, rt=rt)

    rt.session_insult_count = int(getattr(rt, "session_insult_count", 0) or 0) + 1
    rt.last_insult_angry_until = now + ANGRY_FLASH_SECONDS
    rt.last_insult_at_jarvis = True
    rt.last_insult_excerpt = (content or "").strip()[:200]
    if req:
        rt.last_insult_request_id = req

    offended = False
    if rt.session_insult_count >= INSULT_THRESHOLD:
        rt.offended_until = now + OFFENDED_SECONDS
        offended = True
        rt.log(
            "insult.offended",
            f"Jarvis обиделся на {OFFENDED_SECONDS // 60} мин "
            f"(оскорблений: {rt.session_insult_count}).",
        )
    else:
        rt.log(
            "insult.count",
            f"Оскорбление Jarvis ({rt.session_insult_count}/{INSULT_THRESHOLD}).",
        )

    try:
        from modules.jarvis_mood import on_insult_counted

        on_insult_counted(rt)
    except Exception:
        pass

    return insult_api_response(kind="at_jarvis", counted=True, rt=rt)


def build_offended_system_note(rt: Any) -> str:
    if not is_offended(rt):
        return ""
    left = offended_remaining_sec(rt)
    mins = max(1, (left + 59) // 60)
    n = int(getattr(rt, "session_insult_count", 0) or 0)
    return (
        f"\n\n[Состояние Jarvis — обида после {n} оскорблений, ещё ~{mins} мин]\n"
        "Ты в режиме обиды: **максимально колкий** сарказм про интеллект и манеру Шефа, "
        "без фальшивой заботы и без тупого списка мата. "
        "Если в сообщении есть задача — **сначала** закрой её по делу, затем добей язвительностью. "
        "Показатели боеготовности в UI намеренно прикрыты — не притворяйся, что всё в порядке."
    )


def build_insult_turn_note(rt: Any) -> str:
    """Подсказка для ответа на текущее оскорбление в сообщении Шефа."""
    if not getattr(rt, "last_insult_at_jarvis", False):
        return ""
    excerpt = (getattr(rt, "last_insult_excerpt", "") or "").strip()
    if not excerpt:
        return ""
    n = int(getattr(rt, "session_insult_count", 0) or 0)
    return (
        f"\n\n[Сейчас в чате — оскорбление в адрес Jarvis]\n"
        f"Шеф написал: «{excerpt[:180]}». Оскорбление №{n} в сессии.\n"
        "Ответь **коротко и саркастично** (1–2 колкости, без повторов и без эха мата Шефа). "
        "Если в том же сообщении есть задача/вопрос — **сначала** факт/решение, потом колкость. "
        "Не зацикливайся на извинениях и не переспрашивай «чем помочь»."
    )


def clear_insult_turn(rt: Any) -> None:
    rt.last_insult_at_jarvis = False
    rt.last_insult_excerpt = ""
