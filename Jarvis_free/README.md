# Jarvis Free

Бесплатная редакция Jarvis: весь функционал в одном чате, без экрана-аватара и 2D-игры.

> **Публичный репозиторий.** Не коммитьте `.env`, ключи API, токены Telegram/Avito и личные чаты.
> Перед сборкой EXE см. [SECURITY.md](../SECURITY.md). Лимит диска **10 ГБ** — [DISK.md](../DISK.md).

## Быстрый старт (из корня forgithub)

```powershell
cd ..
.\scripts\setup-workspace.ps1
```

Или только Jarvis:

```powershell
.\scripts\setup-dev.ps1
copy backend\config\deepseek_free.key.example backend\config\deepseek_free.key
# вставьте ключ DeepSeek sk-…
.\start.bat
```

Откройте http://127.0.0.1:8001/

## Данные пользователя

Чаты и настройки: `%LOCALAPPDATA%\Jarvis_free\data` (не в git).

Шаблоны: `backend/data/*.example`, `backend/data/*/config.example.json`.

## Модели Qwen

В git **нет** GGUF (~9 ГБ). При лимите **10 ГБ** рекомендуется **DeepSeek API** без локальной модели.

Если всё же нужен Qwen 14B (не влезает в 10 ГБ вместе с deps):

```powershell
.\scripts\install-qwen-safe.bat
```

## Сборка EXE

После `..\scripts\check-secrets.ps1`. Артефакты (`dist/`, `*.exe`) не публикуются на GitHub.

## Порт

Jarvis Free: **8001** (Pro: **8000**).
