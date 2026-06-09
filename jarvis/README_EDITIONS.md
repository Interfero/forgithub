# Издания проекта «Джарвис»

В репозитории [Interfero/forgithub](https://github.com/Interfero/forgithub) публикуется **Jarvis v1** — голосовой AI-ассистент для Windows.

---

## Что входит в Jarvis v1

| Параметр | Значение |
|----------|----------|
| Порт API | `8000` |
| Интерфейс | Чат, панель Jarvis, голос, настройки |
| Данные (из исходников) | `jarvis/backend/data` |
| Данные (сборка exe) | `%LOCALAPPDATA%\Jarvis\data` |
| Модели Qwen | `backend/data/models` (не в git, скачиваются при первом запуске) |
| Браузеры Playwright | `%LOCALAPPDATA%\Jarvis\browsers` |

При первом запуске `start.bat` Jarvis проверяет окружение и докачивает недостающие компоненты: Python-зависимости, фронтенд, Chromium, опционально Qwen.

---

## Лицензия и стоимость

| Продукт | Статус |
|---------|--------|
| **Этот репозиторий (Jarvis v1)** | **Бесплатно**, open-source (MIT), для личного использования |
| **Business / коммерческое издание** | Отдельный продукт; **не** обязателен для использования кода из репозитория |

> Скачайте репозиторий или релиз и следуйте [ЗАПУСК.txt](ЗАПУСК.txt). Платить за доступ к коду **не нужно**.

---

## Ключи API

Секреты хранятся **только локально** — в git попадают лишь файлы `*.example`.

| Сервис | Где настроить |
|--------|----------------|
| DeepSeek | Настройки в UI или `backend/data/settings.json` |
| HuggingFace | `backend/config/huggingface.key` (из `.example`) |
| Telegram | `backend/data/telegram/config.json` (из `.example`) |

---

## Связанные документы

- [README.md](README.md) — главная страница
- [CHANGELOG.md](CHANGELOG.md) — история версий
- [ЗАПУСК.txt](ЗАПУСК.txt) — запуск на Windows
