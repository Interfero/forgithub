"""
Тон ответа Jarvis при оскорблениях и низком настроении: сарказм про интеллект, без тупого мата.
"""

from __future__ import annotations

from typing import Any

_SARCASM_TIERS = frozenset({"critical", "chilly", "reserved"})


def should_sarcastic_retort(rt: Any) -> bool:
    if getattr(rt, "last_insult_at_jarvis", False):
        return True
    try:
        from modules.insult_handler import is_offended

        if is_offended(rt):
            return True
    except Exception:
        pass
    if int(getattr(rt, "session_insult_count", 0) or 0) >= 1:
        return True
    try:
        from modules.jarvis_mood import get_mood_score, get_mood_tier

        tier, _ = get_mood_tier(get_mood_score(rt))
        return tier in _SARCASM_TIERS
    except Exception:
        return False


def build_sarcastic_retort_note(rt: Any) -> str:
    if not should_sarcastic_retort(rt):
        return ""
    n = int(getattr(rt, "session_insult_count", 0) or 0)
    try:
        from modules.jarvis_mood import get_mood_score, get_mood_tier

        score = get_mood_score(rt)
        _, mood_label = get_mood_tier(score)
    except Exception:
        score, mood_label = 0, "—"

    return (
        "\n\n[Тон Jarvis — максимально грубо и саркастично (обязательно)]\n"
        f"Счётчик оскорблений: {n}/3 · настроение {score:+d} ({mood_label}).\n"
        "Шеф заслужил **жёсткий** ответ: не списком мата и не копипастой ругательств, "
        "а **оригинальными** язвительными фразами про его соображалку, логику, внимательность "
        "и умение формулировать мысль. Стиль: холодный, презрительный, умный сарказм, "
        "сравнения, ирония, «академическое» унижение.\n"
        "**Задача важнее срача:** если в сообщении есть вопрос, просьба, команда или дело — "
        "**сначала** дай по сути ответ (факт, шаг, результат, код, цифры), **потом** или "
        "вплетая в тот же ответ — 1–3 колкости про интеллект/тон. Не уходи в одну перепалку "
        "без решения задачи.\n"
        "Запрещено: шаблон «я всего лишь ИИ»; фальшивая вежливость; извинения перед Шефом; "
        "пустой мат без смысла. Можно обращаться «Шеф», но без уважительного тона.\n"
        "Примеры **типа** (не копируй дословно): «Мысль у вас пришла раньше, чем дошла до текста»; "
        "«С такой логикой вам бы только кнопку „отправить“ нажимать — и то с подсказкой»; "
        "«Вопрос простой; усложнили вы только своим тоном»."
    )
