from __future__ import annotations

import json
from typing import AsyncIterator

from app.agent_state import get_agent_state, with_agent_lock
from app.db import add_message, get_chat_messages, load_settings
from app.schemas import MessageOut
from app.services.llm import chat_completion, parse_tool_call
from app.services.rag import search as rag_search
from app.services.web_search import search_web

MAX_TOOL_ROUNDS = 3


def _sliding_window(messages: list[MessageOut], max_messages: int = 24) -> list[dict]:
    recent = messages[-max_messages:] if len(messages) > max_messages else messages
    return [{"role": m.role, "content": m.content} for m in recent]


async def run_agent(chat_id: str, user_content: str) -> AsyncIterator[dict]:
    """
    Генератор событий SSE:
    - {"type": "status", "status": "..."}
    - {"type": "log", "tool": "...", "message": "..."}
    - {"type": "chunk", "content": "..."}
    - {"type": "done", "message": MessageOut}
    - {"type": "error", "message": "..."}
    """
    settings = load_settings()
    state = get_agent_state()

    with with_agent_lock():
        state.set_status("Thinking...")
        state.log("chat", f"Новое сообщение в чате {chat_id[:8]}…")

    user_msg = add_message(chat_id, "user", user_content)
    history = get_chat_messages(chat_id)
    llm_messages = _sliding_window(history)

    yield {"type": "user", "message": user_msg.model_dump()}
    yield {"type": "status", "status": "Thinking..."}

    tool_rounds = 0
    final_text = ""

    while tool_rounds <= MAX_TOOL_ROUNDS:
        try:
            response, tokens = await chat_completion(settings, llm_messages)
        except Exception as e:
            with with_agent_lock():
                state.set_status("IDLE")
                state.log("llm.error", str(e))
            yield {"type": "error", "message": str(e)}
            return

        with with_agent_lock():
            state.add_tokens(tokens)
            state.log("llm.request", f"Ответ получен (~{tokens} токенов)")

        tool = parse_tool_call(response)
        if tool and tool_rounds < MAX_TOOL_ROUNDS:
            name, query = tool
            tool_rounds += 1

            if name == "memory_search":
                with with_agent_lock():
                    state.set_status("Thinking...")
                    state.log("memory.search", f"RAG: «{query[:60]}»")
                yield {"type": "status", "status": "Thinking..."}
                yield {"type": "log", "tool": "memory.search", "message": f"Запрос: {query}"}

                hits = rag_search(query)
                if hits:
                    context = "\n\n".join(
                        f"[{h['filename']}] {h['text'][:400]}" for h in hits[:5]
                    )
                    tool_result = f"Результаты memory_search:\n{context}"
                else:
                    tool_result = "Документы не найдены или индекс пуст."

            elif name == "web_search":
                with with_agent_lock():
                    state.set_status("Searching Web...")
                    state.log("web.search", f"Поиск: «{query[:60]}»")
                yield {"type": "status", "status": "Searching Web..."}
                yield {"type": "log", "tool": "web.search", "message": f"Поиск: {query}"}

                results = search_web(query)
                lines = []
                for i, r in enumerate(results, 1):
                    lines.append(
                        f"{i}. **{r['title']}** — {r['url']}\n   {r['snippet'][:300]}"
                    )
                tool_result = "Результаты web_search:\n" + ("\n".join(lines) or "Ничего не найдено.")

                with with_agent_lock():
                    state.set_status("Thinking...")
            else:
                tool_result = f"Неизвестный инструмент: {name}"

            llm_messages.append({"role": "assistant", "content": response})
            llm_messages.append(
                {
                    "role": "user",
                    "content": f"[Результат инструмента]\n{tool_result}\n\nСформируй финальный ответ пользователю.",
                }
            )
            yield {"type": "status", "status": "Thinking..."}
            continue

        final_text = response
        break

    # Потоковая отдача финального текста
    words = final_text.split(" ")
    accumulated = ""
    for i, w in enumerate(words):
        accumulated += (" " if i else "") + w
        if i % 3 == 0 or i == len(words) - 1:
            yield {"type": "chunk", "content": accumulated}

    msg = add_message(chat_id, "assistant", final_text)
    with with_agent_lock():
        state.set_status("IDLE")
        state.log("chat", "Ответ сохранён")

    yield {"type": "done", "message": msg.model_dump()}
