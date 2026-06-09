"""
Сессионная память диалога (runtime, сброс при рестарте приложения).
Уточнения «да/нет», «ещё», «второй пункт» — без записи в сознательное.
"""

from __future__ import annotations

import re

from modules.dialog_handlers import normalize_chat_user_text

_YES = frozenset({"да", "yes", "ага", "угу", "конечно", "давай", "ок", "окей", "okay", "ok"})
_NO = frozenset({"нет", "no", "не", "неа", "не надо", "не нужно"})
_MORE = frozenset({"ещё", "еще", "продолж", "дальше", "go on", "continue", "more"})
_SECOND_POINT = re.compile(
    r"(?:а\s+)?(?:второй|2(?:-?й)?|следующ)\s+(?:пункт|п\.?|позици)",
    re.I,
)


def dialog_layer_instruction() -> str:
    return (
        "\n\n[Диалоговый слой]\n"
        "Веди переписку естественно: **одной короткой фразой** отрази суть запроса Шефа, "
        "затем содержательный ответ (списки и абзацы — по делу).\n"
        "Если без одного уточнения нельзя выполнить задачу — **один** конкретный вопрос в конце.\n"
        "Не имитируй реплики Шефа и не продолжай диалог за него.\n"
        "Учитывай контекст сессии (последняя тема, ожидание ответа да/нет).\n"
    )


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _last_assistant(history: list[dict] | None) -> str:
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            return (msg.get("content") or "").strip()
    return ""


def _extract_list_items(text: str) -> list[str]:
    items: list[str] = []
    for line in (text or "").splitlines():
        m = re.match(r"^\s*(?:\d{1,2}\.|[-•*])\s+(.+)$", line.strip())
        if m:
            body = re.sub(r"\*\*([^*]+)\*\*", r"\1", m.group(1)).strip()
            if body:
                items.append(body)
    return items


def _pending_question_from_assistant(text: str) -> str:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for ln in reversed(lines[-4:]):
        if "?" in ln:
            return ln
    if text.rstrip().endswith("?"):
        return lines[-1] if lines else text.strip()
    return ""


def get_dialog_session(runtime) -> dict:
    if not hasattr(runtime, "dialog_session") or not isinstance(runtime.dialog_session, dict):
        runtime.dialog_session = {
            "last_topic": "",
            "last_user_intent": "",
            "pending_question": "",
            "awaiting_yes_no": False,
            "active_game": "",
        }
    return runtime.dialog_session


def prepare_user_turn(user_text: str, history: list[dict] | None) -> str:
    """Развернуть короткий follow-up в явный запрос для роутера."""
    from modules.agent import get_runtime
    from modules.operation_stream import append_thinking

    raw = normalize_chat_user_text(user_text)
    low = _norm(raw)
    if not low:
        return raw

    sess = get_dialog_session(get_runtime())
    last_asst = _last_assistant(history)

    tokens = [t for t in low.split() if t]
    if len(tokens) <= 3 and all(t in _YES for t in tokens) and sess.get("awaiting_yes_no"):
        q = sess.get("pending_question") or "подтверждение"
        append_thinking(f"Диалог: «да» → продолжаю тему «{sess.get('last_topic', '—')[:48]}»")
        return (
            f"[Контекст сессии: Шеф согласился. Последний вопрос Jarvis: {q}. "
            f"Тема: {sess.get('last_topic', 'предыдущий ответ')}.] "
            f"Да, продолжай по этой теме."
        )

    if len(tokens) <= 2 and all(t in _NO for t in tokens) and sess.get("last_topic"):
        append_thinking("Диалог: «нет» → закрываю ожидание подтверждения")
        return (
            f"[Контекст: Шеф отказался от продолжения темы «{sess.get('last_topic', '')[:80]}».] "
            "Нет, не нужно. Коротко подтверди и спроси, что дальше."
        )

    if any(w in low for w in _MORE) and sess.get("last_topic"):
        append_thinking(f"Диалог: «ещё» по теме «{sess.get('last_topic', '')[:48]}»")
        return (
            f"[Контекст: Шеф просит продолжить тему «{sess.get('last_topic', '')[:120]}».] "
            f"Расскажи ещё по этой теме, без повтора уже сказанного."
        )

    if _SECOND_POINT.search(low) and last_asst:
        items = _extract_list_items(last_asst)
        if len(items) >= 2:
            append_thinking("Диалог: запрос второго пункта из прошлого списка")
            return (
                f"[Контекст: в прошлом ответе был список. Шеф просит второй пункт.] "
                f"Подробнее только про пункт 2: {items[1]}"
            )

    return raw


def update_dialog_session(user_text: str, assistant_reply: str, history: list[dict] | None = None) -> None:
    from modules.agent import get_runtime
    from modules.operation_stream import append_thinking

    rt = get_runtime()
    sess = get_dialog_session(rt)
    intent = (user_text or "").strip()[:160]
    topic = intent
    if len(topic) > 80:
        topic = topic[:77] + "…"

    sess["last_user_intent"] = intent
    sess["last_topic"] = topic or sess.get("last_topic", "")

    pending = _pending_question_from_assistant(assistant_reply)
    sess["pending_question"] = pending
    sess["awaiting_yes_no"] = bool(
        pending
        and any(
            k in pending.lower()
            for k in ("?", "уточн", "нужно ли", "хотите", "продолж", "соглас")
        )
    )

    append_thinking(
        f"Диалог: тема «{sess.get('last_topic', '—')[:40]}»"
        + (f"; жду ответ: {pending[:50]}…" if sess["awaiting_yes_no"] else "")
    )
