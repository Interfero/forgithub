"""Локальный AI-анализ семплов переписки. Без отправки в Telegram."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

ANALYST_SYSTEM = """Ты аналитик личной переписки в Telegram (режим наблюдателя).
По сообщениям чата верни ТОЛЬКО валидный JSON без markdown:
{
  "summary": "краткая выжимка: о чём говорили, спорили, к какому решению пришли",
  "topics": ["тема1", "тема2"],
  "suggested_replies": [
    {"tone": "нейтрально", "text": "вариант ответа в стиле владельца"},
    {"tone": "кратко", "text": "..."},
    {"tone": "развёрнуто", "text": "..."}
  ]
}
Не предлагай автоматическую отправку. Только текст для ручной вставки пользователем."""


def _format_messages_for_prompt(messages: list[dict]) -> str:
    lines = []
    for m in messages[-80:]:
        who = "Я" if m.get("out") else m.get("sender", "?")
        lines.append(f"[{m.get('date', '')}] {who}: {m.get('text', '')[:500]}")
    return "\n".join(lines)


def _parse_llm_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": text[:1500],
            "topics": [],
            "suggested_replies": [
                {"tone": "черновик", "text": "Не удалось разобрать JSON от модели"},
            ],
        }


async def analyze_with_ollama(
    chat_title: str,
    messages: list[dict],
    base_url: str,
    model: str,
) -> dict[str, Any]:
    user_content = f"Чат: {chat_title}\n\nСообщения:\n{_format_messages_for_prompt(messages)}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ANALYST_SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
    }
    url = base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    content = data.get("message", {}).get("content", "") or ""
    parsed = _parse_llm_json(content)
    parsed["_provider"] = "ollama"
    return parsed


def analyze_chat_mock(chat_title: str, messages: list[dict]) -> dict[str, Any]:
    """Заглушка до подключения Ollama."""
    preview = _format_messages_for_prompt(messages)[:400]
    return {
        "summary": f"[Мок] В «{chat_title}» обработано {len(messages)} сообщений. "
        f"Подключите Ollama для реальной выжимки.",
        "topics": ["мок"],
        "suggested_replies": [
            {"tone": "нейтрально", "text": "Понял, вернусь с ответом чуть позже."},
            {"tone": "кратко", "text": "Ок, посмотрю."},
            {"tone": "развёрнуто", "text": f"По переписке ({len(messages)} msg): {preview[:120]}…"},
        ],
        "_provider": "mock",
    }


async def analyze_chat(
    chat_title: str,
    messages: list[dict],
    *,
    use_local_llm: bool,
    ollama_base_url: str,
    ollama_model: str,
) -> dict[str, Any]:
    if use_local_llm:
        try:
            return await analyze_with_ollama(
                chat_title, messages, ollama_base_url, ollama_model
            )
        except Exception:
            pass
    return analyze_chat_mock(chat_title, messages)
