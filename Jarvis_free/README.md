# Jarvis Free

Бесплатная редакция Jarvis. Публичная копия в репозитории [forgithub](https://github.com/Interfero/forgithub).

> Не коммитьте ключи API и личные чаты. См. [SECURITY.md](../docs/SECURITY.md) и [DISK.md](../docs/DISK.md).

## Структура (внутри Jarvis_free)

```
Jarvis_free/
├── README.md, .gitignore, Dockerfile, docker-compose.yml
├── start.bat, restart.bat, start-dev.bat   ← запуск
├── backend/
├── frontend/
├── scripts/launch/      ← VBS
├── scripts/windows/     ← install-*, serve, …
├── packaging/           ← build-exe.bat
├── assets/images/
├── docs/
└── var/                 ← временные файлы (не в git)
```

## Запуск

1. Ключ: `backend\config\deepseek_free.key.example` → `deepseek_free.key`
2. `start.bat` → http://127.0.0.1:8001/

## Утилиты

| Задача | Путь |
|--------|------|
| Qwen 14B (проверка 10 GB) | `scripts\windows\install-qwen-safe.bat` |
| Сборка EXE | `packaging\build-exe.bat` |
| Dev-режим | `start-dev.bat` |

Данные пользователя: `%LOCALAPPDATA%\Jarvis_free\data`
