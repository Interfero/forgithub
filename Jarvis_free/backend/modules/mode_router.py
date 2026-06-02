"""
Автовыбор режима Jarvis по содержанию запроса пользователя.
Режим не показывается в UI — роутер включает нужные компоненты тихо.
"""

from __future__ import annotations

import re

from modules.agent import MODE_LABELS, AgentMode, get_mode, get_runtime, set_mode

_DEVELOPER_SIGNALS: tuple[str, ...] = (
    "код",
    "python",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "fastapi",
    "django",
    "sql",
    "postgres",
    "mysql",
    "mongodb",
    "git ",
    "github",
    "docker",
    "kubernetes",
    "devops",
    "api ",
    "endpoint",
    "рефактор",
    "отлад",
    "дебаг",
    "debug",
    "bug",
    "stack trace",
    "traceback",
    "коммит",
    "pull request",
    "merge request",
    "npm ",
    "pip ",
    "cargo ",
    "rust ",
    "golang",
    "java ",
    "kotlin",
    "swift ",
    "архитектур",
    "микросервис",
    "frontend",
    "backend",
    "fullstack",
    "разработ",
    "программ",
    "function ",
    "class ",
    "компонент",
    "хук ",
    "useeffect",
    "usestate",
    "webpack",
    "vite",
    "eslint",
    "юнит-тест",
    "unit test",
    "интеграционн",
    "regex",
    "regexp",
    "алгоритм",
    "структур данных",
    "leetcode",
    "ci/cd",
    "deploy",
    "деплой",
)

_ACCOUNTANT_SIGNALS: tuple[str, ...] = (
    "налог",
    "ндс",
    "усн",
    "осно",
    "патент",
    "бухгалт",
    "бухучёт",
    "бухучет",
    "выписк",
    "контрагент",
    "инн",
    "огрн",
    "кпп",
    "бик",
    "р/с",
    "расчётн",
    "расчетн",
    "1c_to_kl",
    "1с",
    "договор",
    "счёт",
    "счет",
    "счет-фактур",
    "счёт-фактур",
    "invoice",
    "акт сверки",
    "декларац",
    "гк рф",
    "нк рф",
    "ук рф",
    "гражданск",
    "кодекс",
    "юрид",
    "юрист",
    "правов",
    "судеб",
    "исков",
    "претенз",
    "ликвидац",
    "ип ",
    "ооо",
    "ао ",
    "учредит",
    "устав",
    "трудов",
    "тк рф",
    "штраф",
    "пеня",
    "банковск",
    "реквизит",
    "консультант",
    "гарант",
)

_MARKETER_SIGNALS: tuple[str, ...] = (
    "маркетинг",
    "копирайт",
    "креатив",
    "баннер",
    "логотип",
    "бренд",
    "утп",
    "слоган",
    "лендинг",
    "landing",
    "таргет",
    "конверси",
    "лид ",
    "лиды",
    "воронк",
    "a/b",
    "ab-тест",
    "соцсет",
    "instagram",
    "telegram-канал",
    "пост для",
    "текст для авито",
    "объявлен",
    "создай объявление",
    "напиши объявление",
    "описание для авито",
    "заголовок для авито",
    "карточк товар",
    "карточку товар",
    "дизайн",
    "палитр",
    "мoodboard",
    "инфограф",
    "иллюстрац",
    "визуал",
    "нейминг",
    "позиционир",
    "smm",
    "seo-текст",
    "контент-план",
)

_CODE_BLOCK_RE = re.compile(
    r"```|"
    r"\b(def |class |function |import |from |const |let |var |async |await |"
    r"interface |type |enum |struct |impl |package |#include)\b",
    re.I,
)


def _score_signals(text: str, signals: tuple[str, ...]) -> int:
    low = (text or "").lower()
    return sum(1 for s in signals if s in low)


def classify_task_mode(user_text: str) -> AgentMode:
    """Определить целевой режим по тексту запроса (эвристики + паттерны кода)."""
    from modules.media_generation import wants_media_generation

    text = (user_text or "").strip()
    if not text:
        return AgentMode.STANDARD

    if wants_media_generation(text):
        return AgentMode.MARKETER

    try:
        from modules.listing_generation import wants_listing_generation

        if wants_listing_generation(text):
            return AgentMode.MARKETER
    except Exception:
        pass

    dev_score = _score_signals(text, _DEVELOPER_SIGNALS)
    acc_score = _score_signals(text, _ACCOUNTANT_SIGNALS)
    mkt_score = _score_signals(text, _MARKETER_SIGNALS)

    if _CODE_BLOCK_RE.search(text):
        dev_score += 4

    scores = {
        AgentMode.DEVELOPER: dev_score,
        AgentMode.ACCOUNTANT: acc_score,
        AgentMode.MARKETER: mkt_score,
    }
    best_mode, best_score = max(scores.items(), key=lambda x: x[1])
    if best_score <= 0:
        return AgentMode.STANDARD

    # При равном счёте — приоритет: бухгалтерия > разработка > маркетинг
    tied = [m for m, s in scores.items() if s == best_score]
    if len(tied) > 1:
        for preferred in (
            AgentMode.ACCOUNTANT,
            AgentMode.DEVELOPER,
            AgentMode.MARKETER,
        ):
            if preferred in tied:
                return preferred
    return best_mode


def _mode_keys_ready(mode: AgentMode) -> bool:
    import store
    from modules import nano_banana as nano_banana_module

    s = store.load_settings()
    deepseek = (s.get("deepseek_key") or "").strip()
    pplx = (s.get("perplexity_key") or "").strip()
    nb = (s.get("nanobanana_key") or "").strip()

    def _ok(prefix: str, key: str, min_len: int) -> bool:
        k = (key or "").strip()
        return k.startswith(prefix) and len(k) >= min_len and "•" not in k

    if mode == AgentMode.MARKETER:
        from modules.media_generation import has_media_provider

        return has_media_provider("image") or _ok("sk-", deepseek, 20)
    if mode == AgentMode.ACCOUNTANT:
        return _ok("sk-", deepseek, 20)
    if mode == AgentMode.DEVELOPER:
        return _ok("pplx-", pplx, 12) or _ok("sk-", deepseek, 20)
    return True


def resolve_mode_with_fallback(mode: AgentMode, user_text: str = "") -> AgentMode:
    """Если для режима нет ключей — стандартный чат (Qwen + инструменты)."""
    if mode == AgentMode.STANDARD or _mode_keys_ready(mode):
        return mode
    try:
        from modules.listing_generation import wants_listing_generation

        if mode == AgentMode.MARKETER and wants_listing_generation(user_text):
            return AgentMode.MARKETER
    except Exception:
        pass
    return AgentMode.STANDARD


def ensure_mode_for_query(user_text: str) -> AgentMode:
    """
    Проанализировать запрос и тихо переключить режим на backend.
    Пользователь не видит переключатель — только результат с нужными инструментами.
    """
    desired = classify_task_mode(user_text)
    resolved = resolve_mode_with_fallback(desired, user_text)
    current = get_mode()
    if resolved != current:
        set_mode(resolved)
        rt = get_runtime()
        label = MODE_LABELS.get(resolved, resolved.value)
        if resolved == desired:
            note = "auto"
        else:
            wanted = MODE_LABELS.get(desired, desired.value)
            note = f"auto (запрошен «{wanted}», ключей нет → стандартный)"
        rt.log("router", f"Режим **{label}** ({note})")
    return get_mode()
