from __future__ import annotations

import json
import re
from typing import AsyncIterator

import httpx

from app.agent_state import get_agent_state
from app.schemas import AppSettings, MessageOut

SYSTEM_PROMPT = """Ты Jarvis — персональный локальный AI-ассистент на Windows.
Отвечай на русском, если пользователь пишет по-русски. Используй Markdown.

У тебя есть инструменты. Чтобы вызвать инструмент, ответь ТОЛЬКО одной строкой в формате:
<tool>имя|запрос</tool>

Доступные инструменты:
- memory_search — поиск по загруженным документам пользователя (RAG)
- web_search — поиск актуальной информации в интернете

Примеры:
<tool>web_search|курс доллара сегодня</tool>
<tool>memory_search|требования к архитектуре</tool>

Если инструмент не нужен — отвечай пользователю напрямую без тега <tool>.
После получения результатов инструментов формируй финальный ответ со ссылками на источники (для веб-поиска)."""


TOOL_RE = re.compile(r"<tool>([^|]+)\|([^<]+)</tool>", re.IGNORECASE)


def parse_tool_call(text: str) -> tuple[str, str] | None:
    m = TOOL_RE.search(text.strip())
    if not m:
        return None
    return m.group(1).strip().lower(), m.group(2).strip()


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


async def chat_completion(
    settings: AppSettings,
    messages: list[dict],
) -> tuple[str, int]:
    """Возвращает (текст ответа, примерное число токенов)."""
    model = settings.default_model or "gpt-4o-mini"
    state = get_agent_state()
    state.model = model

    provider = settings.provider
    if provider == "openai" and settings.openai_key:
        return await _openai_compatible(
            base_url="https://api.openai.com/v1",
            api_key=settings.openai_key,
            model=model,
            messages=messages,
        )
    if provider == "openrouter" and settings.openrouter_key:
        return await _openai_compatible(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_key,
            model=model,
            messages=messages,
        )
    if provider == "anthropic" and settings.anthropic_key:
        return await _anthropic(settings.anthropic_key, model, messages)
    if provider == "ollama":
        return await _ollama(settings.ollama_base_url, model, messages)

    # Fallback без ключей
    last = messages[-1]["content"] if messages else ""
    return (
        "⚠️ API-ключ не настроен. Откройте **Настройки** и укажите ключ для выбранного провайдера.\n\n"
        f"Ваш запрос: {last[:500]}",
        estimate_tokens(last) + 50,
    )


async def _openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
) -> tuple[str, int]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        temperature=0.7,
    )
    text = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    tokens = usage.total_tokens if usage else estimate_tokens(text)
    return text, tokens


async def _anthropic(api_key: str, model: str, messages: list[dict]) -> tuple[str, int]:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=api_key)
    system = SYSTEM_PROMPT
    api_messages = []
    for m in messages:
        role = "user" if m["role"] == "user" else "assistant"
        api_messages.append({"role": role, "content": m["content"]})

    resp = await client.messages.create(
        model=model if model.startswith("claude") else "claude-3-5-haiku-20241022",
        max_tokens=4096,
        system=system,
        messages=api_messages,
    )
    parts = [b.text for b in resp.content if hasattr(b, "text")]
    text = "".join(parts)
    tokens = (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else estimate_tokens(text)
    return text, tokens


async def _ollama(base_url: str, model: str, messages: list[dict]) -> tuple[str, int]:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        "stream": False,
    }
    url = base_url.rstrip("/") + "/api/chat"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    text = data.get("message", {}).get("content", "")
    return text, estimate_tokens(text)


async def stream_chat_completion(
    settings: AppSettings,
    messages: list[dict],
) -> AsyncIterator[str]:
    """Потоковая генерация (Ollama / OpenAI). Упрощённо — чанки целого ответа."""
    text, _ = await chat_completion(settings, messages)
    # Имитация потока по словам для UI
    words = text.split(" ")
    buf = ""
    for i, w in enumerate(words):
        buf += (" " if i else "") + w
        yield buf
