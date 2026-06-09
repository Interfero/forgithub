"""Локальное хранилище: чаты, настройки, файлы."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from modules.app_paths import ensure_user_data_dir, user_data_dir

DATA_DIR = user_data_dir()
CHATS_FILE = DATA_DIR / "chats.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
FILES_DIR = DATA_DIR / "files"

# Единственный диалог Jarvis (нельзя создавать дополнительные чаты)
SINGLE_CHAT_ID = "00000000-0000-4000-8000-jarvis000001"
SINGLE_CHAT_TITLE = "Диалог с Jarvis"

DEFAULT_SETTINGS = {
    "provider": "deepseek",
    "default_model": "deepseek-chat",
    "openai_key": "",
    "openai_model": "gpt-5.5-instant",
    "anthropic_key": "",
    "deepseek_key": "",
    "perplexity_key": "",
    "perplexity_model": "sonar",
    "xai_key": "",
    "xai_model": "grok-4.20",
    "nanobanana_key": "",
    "ideogram_key": "",
    # Qwen 2.5 14B в ОЗУ — только по кнопке в сайдбаре (не при старте)
    "qwen_ram_enabled": False,
    # Сервисы API / XTTS — ключи остаются, вызовы отключаются тумблером.
    # DeepSeek и XTTS — ядро; остальные API включаются только при сохранённом ключе.
    "deepseek_active": True,
    "openai_active": False,
    "perplexity_active": False,
    "xai_active": False,
    "nanobanana_active": False,
    "ideogram_active": False,
    "xtts_active": True,
    "silero_speaker": "aidar",
    "silero_tempo": 1.0,
    # Словарь ударений Silero: «на связи» → «на св+язи» (+ перед ударной гласной)
    "silero_stress_lexicon": {
        "на связи": "на св+язи",
    },
    # Классические смайлики ICQ (:icq:код:) в чате; в TTS не озвучиваются
    "icq_smileys_enabled": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    if CHATS_FILE.exists():
        return json.loads(CHATS_FILE.read_text(encoding="utf-8"))
    return {"chats": []}


def _save(data: dict) -> None:
    CHATS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings() -> dict:
    from modules.service_flags import normalize_active_flags

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SETTINGS_FILE.exists():
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        merged = {**DEFAULT_SETTINGS, **data}
    else:
        merged = dict(DEFAULT_SETTINGS)
    return normalize_active_flags(merged)


def save_settings(data: dict) -> dict:
    current = load_settings()
    current.update(data)
    SETTINGS_FILE.write_text(
        json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return current


def list_chats() -> list[dict]:
    chat = ensure_single_chat()
    return [chat]


def get_chat(chat_id: str) -> dict | None:
    chat = ensure_single_chat()
    if chat_id and chat_id != chat["id"]:
        return None
    return chat


def ensure_single_chat() -> dict:
    """Один чат на установку; лишние записи в chats.json удаляются."""
    data = _load()
    chats = data.get("chats") or []
    main = next((c for c in chats if c.get("id") == SINGLE_CHAT_ID), None)
    if not main and chats:
        main = chats[0]
        main["id"] = SINGLE_CHAT_ID
    if not main:
        main = {
            "id": SINGLE_CHAT_ID,
            "title": SINGLE_CHAT_TITLE,
            "updated_at": _now(),
            "messages": [],
        }
    main["title"] = main.get("title") or SINGLE_CHAT_TITLE
    main.setdefault("messages", [])
    data["chats"] = [main]
    _save(data)
    return main


def create_chat(title: str = SINGLE_CHAT_TITLE) -> dict:
    """Всегда возвращает единственный чат (новый не создаётся)."""
    chat = ensure_single_chat()
    if title and title.strip() and title.strip() != chat.get("title"):
        return update_chat_title(chat["id"], title.strip()) or chat
    return chat


def clear_chat_messages(chat_id: str | None = None) -> dict | None:
    """Очистить историю единственного чата."""
    chat = ensure_single_chat()
    if chat_id and chat_id != chat["id"]:
        return None
    data = _load()
    for c in data["chats"]:
        if c["id"] == chat["id"]:
            c["messages"] = []
            c["updated_at"] = _now()
            _save(data)
            return c
    return None


def reset_chats_storage() -> dict:
    """Полный сброс чата (после сохранения важного в сознательное)."""
    data = _load()
    chat = {
        "id": SINGLE_CHAT_ID,
        "title": SINGLE_CHAT_TITLE,
        "updated_at": _now(),
        "messages": [],
    }
    data["chats"] = [chat]
    _save(data)
    return chat


def update_chat_title(chat_id: str, title: str) -> dict | None:
    data = _load()
    for c in data["chats"]:
        if c["id"] == chat_id:
            c["title"] = title
            c["updated_at"] = _now()
            _save(data)
            return c
    return None


def delete_chat(chat_id: str) -> bool:
    """Удаление чата запрещено — только очистка сообщений."""
    chat = ensure_single_chat()
    if chat_id != chat["id"]:
        return False
    return clear_chat_messages(chat_id) is not None


def add_message(
    chat_id: str,
    role: str,
    content: str,
    *,
    notify_level: str | None = None,
) -> dict | None:
    data = _load()
    for c in data["chats"]:
        if c["id"] == chat_id:
            msg = {
                "id": str(uuid.uuid4()),
                "role": role,
                "content": content,
                "created_at": _now(),
            }
            if notify_level:
                msg["notify_level"] = notify_level
            c["messages"].append(msg)
            c["updated_at"] = _now()
            _save(data)
            return msg
    return None


def save_uploaded_file(filename: str, content: bytes) -> str:
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    fid = str(uuid.uuid4())[:8]
    ext = Path(filename).suffix
    path = FILES_DIR / f"{fid}{ext}"
    path.write_bytes(content)
    return str(path.name)
