# Telegram-Аналитик (режим наблюдателя)

## Отличие от текущего «Двойника Telegram»

| Было (`tg_twin`) | Нужно (`tg_analyst`) |
|------------------|----------------------|
| Мок + частичный Telethon | Полноценный **userbot** (Telethon) |
| Включение = «активен» | Явная **синхронизация** по кнопке |
| Автоответы (мок) | **Только чтение**, отправки в TG **нет** |
| CLI-авторизация (`tg_login`) | **Телефон + OTP в UI** |
| Сброс непрочитанного при toggle | **«Сбросить шум»** — отдельная команда |
| — | **Семплирование** + **дайджест LLM** + копирование ответов |

Старый `tg_twin` постепенно выводим из UI; логику чёрного списка переносим в `tg_analyst`.

---

## Архитектура бэкенда (FastAPI)

```
backend/modules/tg_analyst/
├── __init__.py      # публичный фасад для main.py
├── models.py        # Pydantic / dataclass
├── runtime.py       # фоновый asyncio-loop, один TelegramClient
├── auth.py          # телефон → код → 2FA → .session
├── reader.py        # mark_all_read, fetch_messages (семпл)
├── analyzer.py      # промпт → локальная LLM (Ollama / DeepSeek)
├── storage.py       # SQLite или JSON в data/telegram_analyst/
└── service.py       # оркестрация sync + analyze
```

### Потоки и потоки выполнения

1. **Один долгоживущий asyncio loop** в daemon-thread (как сейчас в `tg_twin`, но выделенный модуль).
2. Все вызовы Telethon — только через `runtime.run(coro)` из sync-эндпоинтов FastAPI.
3. **Никаких** `client.send_message` в продакшен-путях аналитика (только read / get_history / read_ack).
4. Тяжёлые операции (sync + analyze) — `BackgroundTasks` или отдельный job-id со статусом опроса.

### Локальная LLM

Приоритет (настраивается в `settings.json` / UI):

1. **Ollama** — `http://127.0.0.1:11434` (полностью локально).
2. Fallback: **DeepSeek** / другой ключ из настроек Jarvis (если Ollama недоступна).

Анализ **по одному чату** (батчами), чтобы не переполнить контекст: N последних сообщений или окно 24ч.

### Хранение

`data/telegram_analyst/`

- `session.session` — Telethon (отдельно от twin или общий — решить на этапе 2)
- `config.json` — blocklist, `sample_hours`, `sample_limit_per_chat`
- `digests.db` (SQLite) — чаты, сырой семпл, summary, suggested_replies[], `analyzed_at`

---

## API (эндпоинты)

### Авторизация

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/tg-analyst/status` | Сессия, этап auth, последний sync |
| POST | `/api/tg-analyst/auth/start` | `{ "phone": "+79..." }` → `phone_code_hash` |
| POST | `/api/tg-analyst/auth/verify` | `{ "phone", "code" }` → signed_in / need_2fa |
| POST | `/api/tg-analyst/auth/password` | `{ "password" }` — 2FA |
| POST | `/api/tg-analyst/auth/logout` | Отключить сессию |

### Настройки

| PUT | `/api/tg-analyst/config` | blocklist (ID + @ник), sample_hours, limit |
| GET | `/api/tg-analyst/config` | |

### Операции пользователя

| POST | `/api/tg-analyst/mark-all-read` | Сброс шума (все непрочитанные → прочитано, кроме blocklist) |
| POST | `/api/tg-analyst/sync` | Сбор сообщений → storage (без LLM или с флагом) |
| POST | `/api/tg-analyst/analyze` | LLM по всем чатам из последнего sync |
| POST | `/api/tg-analyst/analyze/{chat_id}` | Один чат |

### UI / дайджест

| GET | `/api/tg-analyst/digests` | Карточки чатов с summary + replies |
| GET | `/api/tg-analyst/digests/{chat_id}` | Детали + сырой семпл (опционально) |
| GET | `/api/tg-analyst/jobs/{job_id}` | Прогресс sync/analyze |

---

## Пошаговый план реализации

### Этап 1 — Скелет (сейчас)

- [x] Пакет `tg_analyst`, эндпоинты-заглушки, модели, storage
- [x] `runtime` + заготовки `auth` / `reader` / `analyzer`
- [ ] Подключить роуты в `main.py`

### Этап 2 — Telethon userbot

- Реализовать auth start/verify/password в UI
- Проверка: сессия только локально, без отправки сообщений
- `mark-all-read` + blocklist (перенос из `tg_twin`)

### Этап 3 — Семплирование

- `iter_dialogs` → фильтр blocklist → `get_messages` за 24ч / limit N
- Сохранение в SQLite, job progress

### Этап 4 — LLM-анализ

- Системный промпт: summary + 2–3 reply variants в стиле пользователя
- Интеграция Ollama + fallback
- Кэш: не переанализировать без нового sync

### Этап 5 — React UI

- Экран/панель «Telegram-Аналитик»
- Кнопки: Синхронизировать, Сбросить шум, Обновить анализ
- Карточки дайджеста, копирование ответа в буфер, локальное поле правки
- Удалить/скрыть старый «Двойник» из сайдбара

### Этап 6 — Полировка

- Rate limits Telethon, retry, логи в tool_logs
- Экспорт дайджеста в markdown
- Опционально: только «чаты с непрочитанными» при sync

---

## Системный промпт (черновик для analyzer)

```
Ты аналитик переписки. Пользователь — владелец аккаунта.
По сообщениям чата верни JSON:
{
  "summary": "краткая выжимка: о чём говорили, к чему пришли",
  "topics": ["тема1", "тема2"],
  "suggested_replies": [
    {"tone": "нейтрально", "text": "..."},
    {"tone": "кратко", "text": "..."},
    {"tone": "развёрнуто", "text": "..."}
  ]
}
Не предлагай отправлять сообщения автоматически. Только текст для ручной вставки.
```

---

## Безопасность

- `.session` и `digests.db` только в `data/`, не в git
- API только `127.0.0.1` (CORS как сейчас)
- Явный запрет send_message в код-ревью / lint-комментарии модуля
