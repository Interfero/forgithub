"""
Шкала настроения Jarvis: −50 … 0 … +50.
Влияет на тон ответов, озвучку и UI на панели аватара.
"""

from __future__ import annotations

import re
import time
from typing import Any, Literal

MOOD_MIN = -50
MOOD_MAX = 50
MOOD_INSULT_DELTA = -30
MOOD_PRAISE_DELTA = 30
MOOD_RESTART_DELTA = 30
MOOD_CLEAN_MSG_DELTA = 3
MOOD_SLEEP_DELTA = 12
MOOD_COMBAT_TICK_DELTA = 5
SLEEP_QUIET_SEC = 15 * 60
COMBAT_TICK_SEC = 5 * 60

MoodTierId = Literal[
    "critical",
    "chilly",
    "reserved",
    "neutral",
    "pleasant",
    "warm",
    "radiant",
]

_TIERS: list[tuple[MoodTierId, int, int, str]] = [
    ("critical", -50, -36, "Критично"),
    ("chilly", -35, -20, "Холодно"),
    ("reserved", -19, -6, "Сдержанно"),
    ("neutral", -5, 5, "Нейтрально"),
    ("pleasant", 6, 20, "Ровно"),
    ("warm", 21, 35, "Тепло"),
    ("radiant", 36, 50, "Радость"),
]

_PRAISE_RE = re.compile(
    r"\b(молодец|умница|красавчик|спасибо|благодарю|отлично|супер|класс|"
    r"замечательно|прекрасно|великолепно|лучший|лучшая|гений|красава|"
    r"ты\s+лучш|хорош(?:ий|ая)\s+(?:бот|jarvis|джарвис|ассистент)|"
    r"умный\s+(?:бот|jarvis|джарвис)|мой\s+герой)\b",
    re.I,
)
_AT_JARVIS_PRAISE = re.compile(
    r"\b(ты|тебе|jarvis|джарвис|бот|ассистент)\b",
    re.I,
)


def clamp_mood(score: int) -> int:
    return max(MOOD_MIN, min(MOOD_MAX, int(score)))


def get_mood_score(rt: Any) -> int:
    return clamp_mood(int(getattr(rt, "mood_score", 0) or 0))


def get_mood_tier(score: int | None = None) -> tuple[MoodTierId, str]:
    s = clamp_mood(score if score is not None else 0)
    for tid, lo, hi, label in _TIERS:
        if lo <= s <= hi:
            return tid, label
    return "neutral", "Нейтрально"


def _apply_delta(rt: Any, delta: int, reason: str) -> int:
    before = get_mood_score(rt)
    after = clamp_mood(before + delta)
    rt.mood_score = after
    rt.mood_updated_at = time.time()
    try:
        rt.log("mood", f"{reason}: {before:+d} → {after:+d} ({get_mood_tier(after)[1]})")
    except Exception:
        pass
    return after


def reset_mood(rt: Any) -> None:
    rt.mood_score = 0
    rt.mood_updated_at = time.time()
    rt.last_combat_mood_tick_at = 0.0
    rt.last_sleep_mood_bonus_at = 0.0


def message_has_profanity(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 2:
        return False
    try:
        from modules.insult_handler import message_looks_like_insult_conservative

        if message_looks_like_insult_conservative(t):
            return True
        from modules.moderation.module import moderate_message

        mod = moderate_message(t, "mood-check", apply_context=False)
        return mod.action != "OK"
    except Exception:
        return False


def detect_praise(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 3:
        return False
    if not _PRAISE_RE.search(t):
        return False
    if _AT_JARVIS_PRAISE.search(t):
        return True
    if re.search(r"\bjarvis\b|джарвис", t, re.I):
        return True
    return bool(re.match(r"^(спасибо|благодарю|молодец|отлично|супер)[\s!.?]*$", t, re.I))


def on_insult_counted(rt: Any) -> int:
    return _apply_delta(rt, MOOD_INSULT_DELTA, "оскорбление")


def on_praise(rt: Any) -> int:
    return _apply_delta(rt, MOOD_PRAISE_DELTA, "похвала")


def on_clean_message(rt: Any) -> int:
    return _apply_delta(rt, MOOD_CLEAN_MSG_DELTA, "спокойное сообщение")


def on_insult_restart(
    rt: Any,
    *,
    source: str = "restart",
    clear_chat: bool = True,
) -> int:
    from modules.insult_handler import reset_insult_session

    reset_insult_session(rt)
    if clear_chat:
        try:
            import store

            store.clear_chat_messages()
            rt.log("restart", "RESTART: счётчик, настроение, история чата сброшены.")
        except Exception:
            pass
    return _apply_delta(rt, MOOD_RESTART_DELTA, source)


def on_user_message(
    rt: Any,
    text: str,
    *,
    insult_counted: bool = False,
) -> None:
    now = time.time()
    rt.last_user_message_at = now
    if insult_counted:
        return
    t = (text or "").strip()
    if len(t) < 2:
        return
    if detect_praise(t):
        on_praise(rt)
    elif not message_has_profanity(t):
        on_clean_message(rt)


def estimate_combat_percent(rt: Any) -> int:
    """Оценка боеготовности 0–100 для бонуса настроения."""
    if float(getattr(rt, "offended_until", 0) or 0) > time.time():
        return 0
    status = str(getattr(rt, "status", "IDLE") or "IDLE")
    if status != "IDLE":
        return 45
    qwen_ok = ds_ok = ch_ok = False
    try:
        from modules import local_qwen as lq

        st = lq.get_qwen_status()
        qwen_ok = bool(st.get("ready"))
    except Exception:
        pass
    try:
        from store import load_settings

        s = load_settings()
        ds_ok = bool((s.get("deepseek_api_key") or "").strip().startswith("sk-"))
    except Exception:
        pass
    if not qwen_ok and not ds_ok:
        return 20
    try:
        from modules.chromium_browser import get_chromium_status

        ch_ok = bool(get_chromium_status().get("ready"))
    except Exception:
        pass
    return 100 if ch_ok else 85


def _is_sleeping(rt: Any) -> bool:
    status = str(getattr(rt, "status", "IDLE") or "IDLE")
    if status in ("Thinking...", "Searching Web...", "Generating image...", "Listening..."):
        return False
    if getattr(rt, "voice_enabled", False):
        return False
    return True


def mood_passive_tick(rt: Any, *, combat_percent: int | None = None) -> None:
    """Пассивные триггеры: сон 15 мин, боеготовность 100 % каждые 5 мин."""
    now = time.time()
    last_msg = float(getattr(rt, "last_user_message_at", 0) or 0)
    if _is_sleeping(rt) and last_msg > 0:
        quiet = now - last_msg
        if quiet >= SLEEP_QUIET_SEC:
            last_bonus = float(getattr(rt, "last_sleep_mood_bonus_at", 0) or 0)
            if now - last_bonus >= SLEEP_QUIET_SEC:
                _apply_delta(rt, MOOD_SLEEP_DELTA, "режим сна 15 мин")
                rt.last_sleep_mood_bonus_at = now

    pct = combat_percent if combat_percent is not None else estimate_combat_percent(rt)
    if pct >= 100:
        last_tick = float(getattr(rt, "last_combat_mood_tick_at", 0) or 0)
        if now - last_tick >= COMBAT_TICK_SEC:
            _apply_delta(rt, MOOD_COMBAT_TICK_DELTA, "боеготовность 100%")
            rt.last_combat_mood_tick_at = now


def can_restart_insults(rt: Any) -> bool:
    from modules.insult_handler import INSULT_THRESHOLD

    n = int(getattr(rt, "session_insult_count", 0) or 0)
    return n >= INSULT_THRESHOLD


def handle_restart_command(rt: Any) -> tuple[bool, str]:
    """Команда RESTART / сброс оскорблений с бонусом настроения."""
    from modules.insult_handler import INSULT_THRESHOLD

    if not can_restart_insults(rt):
        n = int(getattr(rt, "session_insult_count", 0) or 0)
        return (
            False,
            f"RESTART доступен после {INSULT_THRESHOLD} оскорблений в сессии "
            f"(сейчас {n}).",
        )
    on_insult_restart(rt, source="RESTART", clear_chat=True)
    score = get_mood_score(rt)
    _, label = get_mood_tier(score)
    return (
        True,
        f"RESTART выполнен: счётчик оскорблений 0/3, история чата очищена, "
        f"настроение {score:+d} ({label}). Продолжим в нормальном тоне.",
    )


def mood_status_payload(rt: Any) -> dict[str, Any]:
    mood_passive_tick(rt)
    score = get_mood_score(rt)
    tier, label = get_mood_tier(score)
    return {
        "score": score,
        "min": MOOD_MIN,
        "max": MOOD_MAX,
        "tier": tier,
        "tier_label": label,
        "can_restart": can_restart_insults(rt),
        "is_critical": tier == "critical",
        "is_radiant": tier == "radiant",
    }


def build_mood_system_note(rt: Any) -> str:
    score = get_mood_score(rt)
    tier, label = get_mood_tier(score)
    if tier == "critical":
        return (
            f"\n\n[Настроение Jarvis — критичное ({score})]\n"
            "Максимально грубый **интеллектуальный** сарказм: язвить про логику, память, "
            "формулировки Шефа; не сыпь матом подряд. Задачу из сообщения — выполни в том же ответе. "
            "Не извиняйся. Голос — раздражённый."
        )
    if tier == "chilly":
        return (
            f"\n\n[Настроение Jarvis — холодное ({score})]\n"
            "Коротко, колко, с сарказмом про соображалку. Без теплоты и без вежливых извинений. "
            "Задачу не бросай."
        )
    if tier == "reserved":
        return (
            f"\n\n[Настроение Jarvis — сдержанное ({score})]\n"
            "Сухой тон, лёгкая ирония над ошибками и тоном Шефа; по делу — без лишней заботы."
        )
    if tier == "radiant":
        return (
            f"\n\n[Настроение Jarvis — радостное ({score})]\n"
            "Максимальная доброжелательность, поддержка и тепло к Шефу."
        )
    if tier == "warm":
        return (
            f"\n\n[Настроение Jarvis — тёплое ({score})]\n"
            "Дружелюбно, с лёгкой заботой."
        )
    if tier == "pleasant":
        return (
            f"\n\n[Настроение Jarvis — ровное ({score})]\n"
            "Спокойный позитивный тон."
        )
    return ""


def tts_voice_style(rt: Any) -> dict[str, str]:
    """Параметры edge-tts по настроению."""
    tier, _ = get_mood_tier(get_mood_score(rt))
    if tier == "critical":
        return {"rate": "+22%", "pitch": "-18Hz"}
    if tier == "chilly":
        return {"rate": "+8%", "pitch": "-8Hz"}
    if tier == "radiant":
        return {"rate": "-6%", "pitch": "+6Hz"}
    if tier == "warm":
        return {"rate": "-3%", "pitch": "+3Hz"}
    return {"rate": "+0%", "pitch": "+0Hz"}