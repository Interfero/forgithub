"""Фоновый asyncio-loop и единственный экземпляр Telethon-клиента (только чтение)."""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path

# Общая сессия userbot с модулем «Двойник» (ваш аккаунт Telegram, не Bot API)
from modules.tg_twin import SESSION_PATH

ANALYST_DIR = SESSION_PATH.parent

_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_client = None
_client_lock = threading.Lock()


def analyst_dir() -> Path:
    ANALYST_DIR.mkdir(parents=True, exist_ok=True)
    return ANALYST_DIR


def session_exists() -> bool:
    return SESSION_PATH.with_suffix(".session").is_file() or SESSION_PATH.is_file()


def telethon_installed() -> bool:
    try:
        import telethon  # noqa: F401

        return True
    except ImportError:
        return False


def credentials_configured() -> bool:
    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    if api_id and api_hash:
        return True
    cfg_path = analyst_dir() / "config.json"
    if cfg_path.is_file():
        import json

        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            return bool(str(raw.get("api_id", "")).strip() and str(raw.get("api_hash", "")).strip())
        except Exception:
            pass
    return False


def get_credentials() -> tuple[int, str] | None:
    api_id_raw = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    if not api_id_raw or not api_hash:
        import json

        cfg_path = analyst_dir() / "config.json"
        if cfg_path.is_file():
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8"))
                api_id_raw = str(raw.get("api_id", "")).strip()
                api_hash = str(raw.get("api_hash", "")).strip()
            except Exception:
                pass
    if not api_id_raw or not api_hash:
        return None
    try:
        return int(api_id_raw), api_hash
    except ValueError:
        return None


def ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_thread
    if _loop is not None and _loop.is_running():
        return _loop
    loop = asyncio.new_event_loop()

    def _run() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=_run, name="tg-analyst-loop", daemon=True)
    thread.start()
    _loop = loop
    _loop_thread = thread
    return loop


def run_async(coro, timeout: float = 300):
    loop = ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result(timeout=timeout)


async def get_client(*, connect: bool = True):
    """
    Userbot-клиент. ЗАПРЕЩЕНО использовать для send_message в модуле аналитика.
    """
    global _client
    from telethon import TelegramClient

    creds = get_credentials()
    if not creds:
        raise RuntimeError("TELEGRAM_API_ID / TELEGRAM_API_HASH не заданы")
    api_id, api_hash = creds
    analyst_dir()
    with _client_lock:
        if _client is None:
            _client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
        client = _client
    if connect and not client.is_connected():
        await client.connect()
    return client


async def disconnect_client() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            try:
                await _client.disconnect()
            except Exception:
                pass
            _client = None


def shutdown() -> None:
    try:
        run_async(disconnect_client(), timeout=15)
    except Exception:
        pass
