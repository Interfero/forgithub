"""
Однократная авторизация Telegram для Двойника.
Запуск из каталога backend:
  venv\\Scripts\\python.exe -m modules.tg_login
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


async def main() -> None:
    try:
        from telethon import TelegramClient
    except ImportError:
        print("Установите: pip install telethon")
        sys.exit(1)

    api_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    if not api_id or not api_hash:
        print("Задайте TELEGRAM_API_ID и TELEGRAM_API_HASH в backend/.env")
        sys.exit(1)

    from modules.tg_twin import SESSION_PATH, TG_DIR

    TG_DIR.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(str(SESSION_PATH), int(api_id), api_hash)
    await client.start()
    me = await client.get_me()
    name = me.first_name or ""
    if me.username:
        name += f" (@{me.username})"
    print(f"Вход выполнен: {name}")
    print(f"Сессия: {SESSION_PATH}.session")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
