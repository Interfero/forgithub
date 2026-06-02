"""
Классические смайлики ICQ для чата Jarvis.
Маркер в тексте: :icq:{id}:  → картинка в UI; в TTS не озвучивается.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r":icq:([a-z0-9_-]+):", re.I)
_TOGGLE_ON = re.compile(
    r"(?:включ|вруб|активир).{0,12}(?:смайл|эмотикон|icq|аськ)",
    re.I,
)
_TOGGLE_OFF = re.compile(
    r"(?:выключ|отключ|убери|без).{0,12}(?:смайл|эмотикон|icq|аськ)",
    re.I,
)
_SMILEY_QUESTION = re.compile(
    r"(?:какие|список|каталог).{0,20}(?:смайл|icq|аськ)|"
    r"смайлик.{0,15}(?:icq|аськ)",
    re.I,
)

_catalog_cache: dict[str, Any] | None = None


def _bundle_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "icq_smileys"


def _images_dir() -> Path:
    from modules.app_paths import user_data_dir

    dst = user_data_dir() / "icq_smileys" / "images"
    src = _bundle_dir() / "images"
    if not dst.exists() and src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for p in src.glob("*.png"):
            t = dst / p.name
            if not t.exists() or t.stat().st_size < 200:
                try:
                    shutil.copy2(p, t)
                except Exception:
                    pass
    return dst


def load_catalog() -> dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    for path in (
        _bundle_dir() / "catalog.json",
        Path(__file__).resolve().parent.parent / "data" / "icq_smileys" / "catalog.json",
    ):
        if path.is_file():
            _catalog_cache = json.loads(path.read_text(encoding="utf-8"))
            return _catalog_cache
    _catalog_cache = {"smileys": []}
    return _catalog_cache


def smiley_by_id(sid: str) -> dict[str, Any] | None:
    sid = (sid or "").strip().lower()
    for row in load_catalog().get("smileys") or []:
        if (row.get("id") or "").lower() == sid:
            return row
    return None


def image_path(sid: str) -> Path | None:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", (sid or ""))
    if not safe:
        return None
    p = _images_dir() / f"{safe}.png"
    if p.is_file() and p.stat().st_size > 200:
        return p
    return None


def is_enabled() -> bool:
    import store

    return bool(store.load_settings().get("icq_smileys_enabled"))


def set_enabled(enabled: bool) -> bool:
    import store

    store.save_settings({"icq_smileys_enabled": bool(enabled)})
    return is_enabled()


def is_smiley_toggle_request(text: str) -> bool:
    low = (text or "").lower().strip()
    if len(low) > 120:
        return False
    return bool(_TOGGLE_ON.search(low) or _TOGGLE_OFF.search(low))


def is_smiley_catalog_question(text: str) -> bool:
    return bool(_SMILEY_QUESTION.search(text or ""))


def try_handle_smiley_command(text: str) -> tuple[bool, str]:
    """Вкл/выкл смайлики или каталог."""
    low = (text or "").lower()
    if _TOGGLE_OFF.search(low):
        set_enabled(False)
        return True, (
            "Смайлики ICQ **выключены**. В ответах только текст.\n\n"
            "Включить: напишите «включи смайлики»."
        )
    if _TOGGLE_ON.search(low):
        set_enabled(True)
        return True, (
            "Смайлики ICQ **включены**. В ответах можно ставить маркеры `:icq:код:` "
            "(например `:icq:smile:`, `:icq:devil:`).\n\n"
            "Выключить: «выключи смайлики»."
        )
    if is_smiley_catalog_question(text):
        return True, catalog_summary_for_user()
    return False, ""


def catalog_summary_for_user() -> str:
    lines = [
        "**Смайлики ICQ в Jarvis**",
        "",
        f"Статус: **{'включены' if is_enabled() else 'выключены'}**.",
        "Формат в ответе: `:icq:код:` — в чате станет картинкой; **в голосе не читается**.",
        "",
    ]
    for row in load_catalog().get("smileys") or []:
        sid = row.get("id", "")
        emo = ", ".join((row.get("emotions") or [])[:3]) or "—"
        sit = ", ".join((row.get("situations") or [])[:2]) or "—"
        lines.append(f"• **{sid}** ({row.get('name_ru', sid)}) — эмоции: {emo}; ситуации: {sit}")
    lines.append("\nВкл/выкл: «включи смайлики» / «выключи смайлики».")
    return "\n".join(lines)


def icq_smileys_system_block() -> str:
    if not is_enabled():
        return ""
    rows = load_catalog().get("smileys") or []
    compact: list[str] = []
    for r in rows[:20]:
        sid = r.get("id", "")
        emo = "/".join((r.get("emotions") or [])[:2]) or "нейтр."
        sit = "/".join((r.get("situations") or [])[:2]) or "контекст"
        rud = " [грубость]" if r.get("rudeness_reply") else ""
        compact.append(f"  • `:icq:{sid}:` — {r.get('name_ru')}; эмоции: {emo}; ситуации: {sit}{rud}")
    return (
        "\n\n---\n[Смайлики ICQ — включены]\n"
        "Jarvis **имитирует** эмоции, не чувствует их. Выбор смайлика — **по контексту** разговора "
        "(и ситуация, и эмоция, если есть). В одном ответе **0–2** маркера, не в каждом предложении.\n"
        "Маркер: `:icq:код:` (картинка в чате). В **озвучке** маркеры не произносятся.\n"
        "На грубость — коротко + `:icq:devil:` / `:icq:sticking_tongue_out:` / `:icq:yelling:` по тону.\n"
        "Без смайликов в отчётах систем, юридике, длинных таблицах.\n"
        "Каталог:\n"
        + "\n".join(compact)
        + "\n"
    )


def strip_icq_tokens_for_tts(text: str) -> str:
    """Убрать маркеры смайликов перед озвучкой."""
    s = _TOKEN_RE.sub("", text or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def expand_icq_tokens_to_markdown(text: str) -> str:
    """`:icq:smile:` → markdown-картинка для чата."""
    if not text or ":icq:" not in text.lower():
        return text

    def _repl(m: re.Match[str]) -> str:
        sid = m.group(1).lower()
        if not smiley_by_id(sid) or not image_path(sid):
            return ""
        name = smiley_by_id(sid).get("name_ru") or sid
        return f"![{name}](/api/icq-smileys/{sid}.png)"

    return _TOKEN_RE.sub(_repl, text)


def suggest_smiley_for_context(
    *,
    insult: bool = False,
    mood_tier: str = "neutral",
    success: bool = False,
    error: bool = False,
) -> str | None:
    """Подсказка одного маркера для постобработки (не всегда)."""
    if not is_enabled():
        return None
    if insult or mood_tier in ("critical", "chilly"):
        return ":icq:devil:" if insult else None
    if error:
        return ":icq:sad:"
    if success:
        return ":icq:thumbs_up:"
    return None


def apply_context_smiley_hint(text: str, user_text: str = "") -> str:
    """Добавить маркер в конец короткого ответа при оскорблении (если включено)."""
    if not is_enabled() or ":icq:" in (text or "").lower():
        return text
    try:
        from modules.insult_handler import classify_insult

        kind = classify_insult(user_text or "")
        if kind != "at_jarvis":
            return text
        if len((text or "").strip()) > 400:
            return text
        hint = suggest_smiley_for_context(insult=True)
        if hint and hint not in text:
            return (text or "").rstrip() + f" {hint}"
    except Exception:
        pass
    return text


def polish_reply_smileys(text: str, user_text: str = "") -> str:
    if not is_enabled():
        return _TOKEN_RE.sub("", text or "").strip()
    t = expand_icq_tokens_to_markdown(text or "")
    t = apply_context_smiley_hint(t, user_text)
    return t
