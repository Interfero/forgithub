# forgithub

Публичный монорепозиторий проектов на GitHub.

**Ссылка:** https://github.com/Interfero/forgithub

## Структура

```
forgithub/                    ← корень репозитория (документация, скрипты)
├── README.md
├── docs/
├── scripts/
├── config/
├── .githooks/
└── jarvis/                   ← Jarvis v1 — AI-ассистент для Windows
    ├── start.bat             ← первый запуск / установка
    ├── start-quick.bat       ← ежедневный запуск
    ├── backend/
    ├── frontend/
    └── ...
```

## Быстрый старт

```powershell
git clone https://github.com/Interfero/forgithub.git
cd forgithub
.\scripts\setup-workspace.ps1
cd jarvis
.\start.bat
```

Откройте http://127.0.0.1:8000/ после запуска.

Подробнее: [jarvis/START.ru.txt](./jarvis/START.ru.txt)

## Проекты

| Проект | Папка |
|--------|--------|
| **Jarvis v1** | [jarvis/](./jarvis/) — порт `8000`, голосовой AI-ассистент |

Подробнее: [docs/PROJECTS.md](./docs/PROJECTS.md)

## Команды

```powershell
.\scripts\disk-status.ps1          # диск: лимит 10 GB
.\scripts\cleanup-workspace.ps1    # очистка кэшей
.\scripts\check-secrets.ps1        # перед коммитом
```

## Документация

Вся документация — в папке **[docs/](./docs/)**:

- [CONTRIBUTING.md](./docs/CONTRIBUTING.md) — как работать с репозиторием
- [DISK.md](./docs/DISK.md) — лимит 10 ГБ
- [SECURITY.md](./docs/SECURITY.md) — безопасность и секреты
- [ACCESS.md](./docs/ACCESS.md) — доступ collaborators

## Правила

- Публикуем только то, что готовы показать всем.
- Секреты — локально; в git только `*.example`.
- EXE и `dist/` не коммитим.
