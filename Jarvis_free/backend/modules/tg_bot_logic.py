"""
Обработка сообщений Telegram-бота по пользовательскому bot_logic.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

_TG_DIR = user_data_dir() / "telegram"
LOGIC_FILE = _TG_DIR / "bot_logic.json"
EXAMPLE_FILE = _TG_DIR / "bot_logic.example.json"

DEFAULT_LOGIC: dict[str, Any] = {
    "version": 1,
    "name": "Jarvis default",
    "on_start": {"text": "Привет! Я Jarvis. Загрузите bot_logic.json для своей логики."},
    "commands": {"/help": {"text": "Отправьте любое сообщение — отвечу по настройкам fallback."}},
    "messages": {"exact": [], "contains": []},
    "fallback": {
        "mode": "llm",
        "system_prompt": "Ты Telegram-бот Jarvis. Отвечай кратко по-русски.",
    },
}


def validate_logic(data: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Корень JSON должен быть объектом"
    if "version" not in data:
        return False, "Нужно поле version"
    for key in ("commands", "messages", "fallback", "on_start"):
        if key in data and data[key] is not None and not isinstance(data[key], (dict, list)):
            return False, f"Поле {key} должно быть объектом"
    return True, "OK"


def load_logic() -> dict[str, Any]:
    if LOGIC_FILE.is_file():
        try:
            data = json.loads(LOGIC_FILE.read_text(encoding="utf-8"))
            ok, msg = validate_logic(data)
            if ok:
                return data
        except Exception:
            pass
    return dict(DEFAULT_LOGIC)


def save_logic(data: dict[str, Any]) -> dict[str, Any]:
    ok, msg = validate_logic(data)
    if not ok:
        return {"save_ok": False, "message": msg}
    LOGIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOGIC_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "save_ok": True,
        "message": f"Логика сохранена: {data.get('name', 'bot')}",
        **get_logic_info(),
    }


def ensure_default_bot_logic() -> None:
    """Создаёт bot_logic.json из примера, чтобы ядро работало сразу после токена."""
    LOGIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOGIC_FILE.is_file():
        return
    if EXAMPLE_FILE.is_file():
        LOGIC_FILE.write_text(
            EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8"
        )
        return
    LOGIC_FILE.write_text(
        json.dumps(DEFAULT_LOGIC, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def inspect_logic_file() -> dict[str, Any]:
    """Состояние bot_logic.json: наличие, синтаксис JSON и validate_logic (компилируемость)."""
    path = LOGIC_FILE
    base: dict[str, Any] = {
        "bot_logic_path": str(path),
        "bot_logic_configured": path.is_file(),
        "bot_logic_valid": False,
        "bot_logic_error": None,
        "bot_logic_name": None,
        "bot_logic_version": None,
        "commands_count": 0,
    }
    if not path.is_file():
        base["bot_logic_error"] = "Файл bot_logic.json отсутствует"
        return base
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        base["bot_logic_error"] = f"Синтаксис JSON: {exc.msg}"
        return base
    except OSError as exc:
        base["bot_logic_error"] = str(exc)
        return base
    ok, msg = validate_logic(data)
    base["bot_logic_name"] = data.get("name") if isinstance(data, dict) else None
    base["bot_logic_version"] = data.get("version") if isinstance(data, dict) else None
    if isinstance(data, dict):
        base["commands_count"] = len(data.get("commands") or {})
    if not ok:
        base["bot_logic_error"] = msg
        return base
    base["bot_logic_valid"] = True
    return base


def get_logic_info() -> dict[str, Any]:
    return inspect_logic_file()


def _match_rule(text: str, rule: dict[str, Any]) -> bool:
    m = str(rule.get("match", ""))
    if not m:
        return False
    if rule.get("ignore_case", True):
        return m.lower() in text.lower() if rule.get("partial") else text.lower() == m.lower()
    return m in text if rule.get("partial") else text == m


def resolve_reply(
    text: str,
    *,
    is_command: bool,
    command: str | None,
    logic: dict[str, Any] | None = None,
    llm_callback: Any = None,
) -> str:
    """Вернуть текст ответа по bot_logic.json."""
    logic = logic or load_logic()
    cmd = (command or "").strip().lower()
    body = (text or "").strip()

    if is_command and cmd == "/start":
        start = logic.get("on_start") or {}
        if isinstance(start, dict) and start.get("text"):
            return str(start["text"])

    commands = logic.get("commands") or {}
    if is_command and cmd and cmd in commands:
        entry = commands[cmd]
        if isinstance(entry, dict) and entry.get("text"):
            return str(entry["text"])

    messages = logic.get("messages") or {}
    for rule in messages.get("exact") or []:
        if isinstance(rule, dict) and _match_rule(body, {**rule, "partial": False}):
            return str(rule.get("text", ""))

    for rule in messages.get("contains") or []:
        if isinstance(rule, dict) and _match_rule(body, {**rule, "partial": True}):
            return str(rule.get("text", ""))

    fallback = logic.get("fallback") or {}
    mode = str(fallback.get("mode", "static")).lower()
    if mode == "llm" and llm_callback:
        prompt = str(fallback.get("system_prompt", ""))
        return llm_callback(body, prompt)

    if fallback.get("text"):
        return str(fallback["text"])
    return "Принято."
