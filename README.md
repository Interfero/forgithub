# forgithub

Публичный монорепозиторий проектов на GitHub.

**Ссылка:** https://github.com/Interfero/forgithub

## Структура

```
forgithub/
├── Jarvis_free/     # проекты (исходный код)
├── docs/            # документация
├── scripts/         # setup, безопасность, лимит диска
├── config/          # настройки workspace (лимит 10 GB)
├── .githooks/       # pre-commit проверка секретов
└── README.md        # вы здесь
```

## Быстрый старт

```powershell
git clone https://github.com/Interfero/forgithub.git
cd forgithub
.\scripts\setup-workspace.ps1
```

## Проекты

| Проект | Папка |
|--------|--------|
| **Jarvis Free** | [Jarvis_free/](./Jarvis_free/) — порт `8001`, AI-ассистент |

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
