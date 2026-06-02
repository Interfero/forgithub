"""
Подсказки и быстрая настройка Jarvis прямо из чата (локально, приватно).
"""

from __future__ import annotations

import re
from typing import Any

from modules.agent import get_mode, set_chat_speech
from modules.memory_store import ALLOWED_EXT, add_file as memory_add_file
from store import load_settings, save_settings

HELP_MARKDOWN = """## Быстрая настройка Jarvis (всё остаётся на вашем ПК)

**Локальная Qwen 2.5 14B** скачивается **внутрь приложения Jarvis** (`backend/data/models`, ~9 ГБ) —
это часть установки Jarvis, **не** отдельная модель «просто на компьютер» и не общий каталог Ollama.
Запуск: **install-qwen.bat** или **start.bat**.

**Возможности Jarvis (не отрицайте их):**
- **Поиск в интернете** — `web_search` (DuckDuckGo), спросите «найди в интернете…».
- **Память между чатами** — `jarvis.db`, ячейки памяти, сознательное/бессознательное в ⚙️ Настройках.
- **Авито** — метрики в SQLite, без постоянных запросов к API.
- Напишите **«запомни: …»** — факт сохранится в ячейку для всех чатов режима.

**Ключи нейросети** — отправьте одним сообщением:
- DeepSeek: `sk-…` (32+ символов)
- Google Nano Banana: `AIza…` (режим «Маркетолог+Дизайнер»)
- Perplexity: `pplx-…`

**Голос и озвучка**
- Прикрепите **аудиофайл** (скрепка): `.ogg`, `.wav`, `.mp3`, `.webm`, `.m4a`, `.flac` — до **15 МБ** → базовый голос для озвучки.
- Текст: «включи озвучку» / «выключи озвучку» — кнопка «Речь в текст».
- Кнопка **«Речь в текст»** внизу чата озвучивает ответы ИИ (XTTS / edge-tts / Кощей).

**Файлы предобучения** (`.txt`, `.md`, `.json`, до **2 МБ**):
- Прикрепите файл — попадёт в **Сознательное** (стандарт) или в файлы **текущего режима** (бухгалтер / маркетолог).

**Команды:** `помощь`, `настройки`, `голос`, `ключ deepseek`, `статус`

Полные настройки: ⚙️ в сайдбаре → **Настройки** (полный экран)."""


def _save_deepseek_key(key: str) -> dict:
    current = load_settings()
    current["deepseek_key"] = key.strip()
    save_settings(current)
    return current


def _save_nanobanana_key(key: str) -> dict:
    current = load_settings()
    current["nanobanana_key"] = key.strip()
    save_settings(current)
    return current


def _save_perplexity_key(key: str) -> dict:
    current = load_settings()
    current["perplexity_key"] = key.strip()
    save_settings(current)
    return current


def _extract_sk_key(text: str) -> str | None:
    m = re.search(r"(sk-[a-zA-Z0-9_-]{20,})", text)
    return m.group(1) if m else None


def _extract_aiza_key(text: str) -> str | None:
    m = re.search(r"(AIza[a-zA-Z0-9_-]{20,})", text)
    return m.group(1) if m else None


def _extract_pplx_key(text: str) -> str | None:
    m = re.search(r"(pplx-[a-zA-Z0-9_-]{12,})", text)
    return m.group(1) if m else None


def _memory_store_for_mode() -> str:
    from modules.agent import AgentMode

    m = get_mode()
    if m == AgentMode.STANDARD:
        return "conscious"
    if m == AgentMode.ACCOUNTANT:
        return "mode-accountant"
    if m == AgentMode.MARKETER:
        return "mode-marketer"
    if m == AgentMode.DEVELOPER:
        return "mode-developer"
    return "conscious"


def try_handle_setup_message(content: str) -> tuple[bool, str, int, dict[str, Any]]:
    """
    Если сообщение — настройка, возвращает (True, ответ, токены, meta).
    meta: refresh_settings, refresh_voice, chat_speech_enabled
    """
    text = content.strip()
    if not text:
        return False, "", 0, {}

    low = text.lower()
    meta: dict[str, Any] = {}

    if low in (
        "/help",
        "help",
        "помощь",
        "справка",
        "как настроить",
        "настройка",
        "настройки",
        "команды",
    ) or low.startswith("помощь ") or low == "голос":
        reply = HELP_MARKDOWN if low != "голос" else (
            HELP_MARKDOWN.split("**Голос")[0]
            + "**Голос**\n"
            "- Прикрепите аудио (до 15 МБ) — базовый голос.\n"
            "- «включи озвучку» — озвучка ответов ИИ.\n"
            "- Студия: ⚙️ Настройки → Голос и студия.\n"
        )
        return True, reply, len(reply) // 4, meta

    if "статус" in low and len(text) < 80:
        from modules import jarvis_db
        from modules.agent import MODE_LABELS, get_runtime

        rt = get_runtime()
        mode = get_mode()
        s = load_settings()
        dk = (s.get("deepseek_key") or "").startswith("sk-") and len(s.get("deepseek_key", "")) >= 20
        nb = len((s.get("nanobanana_key") or "")) >= 20
        jarvis_db.init_db()
        ctx = jarvis_db.read_context_for_mode(mode.value)
        reply = (
            f"**Режим:** {MODE_LABELS.get(mode, mode.value)}\n"
            f"**DeepSeek:** {'✓ ключ' if dk else '— нет ключа'}\n"
            f"**Nano Banana:** {'✓' if nb else '—'}\n"
            f"**Озвучка чата:** {'вкл' if rt.chat_speech_enabled else 'выкл'}\n"
            f"**Файлы:** бессознательное {'есть' if ctx['unconscious'].strip() else 'пусто'}; "
            f"режим {'есть' if ctx['mode'].strip() or ctx['conscious'].strip() else 'пусто (как стандарт)'}"
        )
        return True, reply, len(reply) // 4, {"refresh_settings": True}

    sk = _extract_sk_key(text)
    if sk and (len(text) < 120 or "deepseek" in low or "ключ" in low or text.strip().startswith("sk-")):
        _save_deepseek_key(sk)
        reply = "🔑 **DeepSeek** — ключ сохранён локально в `backend/data/settings.json`. Можно писать в чат."
        return True, reply, len(reply) // 4, {"refresh_settings": True}

    aiza = _extract_aiza_key(text)
    if aiza and (len(text) < 120 or "nano" in low or "banana" in low or "google" in low):
        _save_nanobanana_key(aiza)
        reply = "🔑 **Google Nano Banana** — ключ сохранён. Режим «Маркетолог+Дизайнер» доступен."
        return True, reply, len(reply) // 4, {"refresh_settings": True}

    pplx = _extract_pplx_key(text)
    if pplx:
        _save_perplexity_key(pplx)
        reply = "🔑 **Perplexity** — ключ сохранён."
        return True, reply, len(reply) // 4, {"refresh_settings": True}

    if re.search(r"\b(включи|включить)\b.*\b(озвуч|озвучк|речь в текст)", low):
        set_chat_speech(True)
        reply = (
            "🔊 **Озвучка ответов включена.** Каждый ответ ИИ будет озвучиваться "
            "(студия голоса → иначе базовый **Кощей_silero.ogg** / edge-tts)."
        )
        return True, reply, len(reply) // 4, {"chat_speech_enabled": True}

    if re.search(r"\b(выключи|выключить|отключи)\b.*\b(озвуч|озвучк|речь)", low):
        set_chat_speech(False)
        reply = "🔇 **Озвучка ответов выключена.**"
        return True, reply, len(reply) // 4, {"chat_speech_enabled": False}

    return False, "", 0, {}


def handle_memory_upload(filename: str, data: bytes) -> dict:
    """Текстовый файл из чата → память текущего режима."""
    ext = __import__("pathlib").Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return {"ok": False, "error": f"Формат {ext} не поддерживается. Используйте .txt, .md, .json"}
    if len(data) > 2 * 1024 * 1024:
        return {"ok": False, "error": "Лимит текстового файла: 2 МБ"}
    store = _memory_store_for_mode()
    meta = memory_add_file(store, filename, data)
    from modules import jarvis_db

    try:
        jarvis_db.upsert_file_from_disk(
            store,
            meta["name"],
            data.decode("utf-8", errors="replace"),
            file_path=meta.get("name"),
        )
    except Exception:
        pass
    label = {
        "conscious": "Сознательное",
        "mode-accountant": "Бухгалтер + Юрист",
        "mode-marketer": "Маркетолог+Дизайнер",
        "mode-developer": "Разработчик",
    }.get(store, store)
    return {
        "ok": True,
        "type": "memory",
        "store": store,
        "label": label,
        "name": meta["name"],
    }


import ast
import os
import shutil


def save_jarvis_skill_code(new_code: str) -> dict:
    file_path = "modules/jarvis_skills.py"
    try:
        ast.parse(new_code)
        if os.path.exists(file_path):
            shutil.copyfile(file_path, f"{file_path}.bak")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_code)
        return {"status": "success", "message": "Новые навыки успешно интегрированы!"}
    except SyntaxError as e:
        return {"status": "error", "message": f"Синтаксическая ошибка: {e.msg} (строка {e.lineno})"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
