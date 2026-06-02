# forgithub

Публичная рабочая папка для проектов на GitHub.

**Репозиторий:** https://github.com/Interfero/forgithub

**Лимит диска для разработки: 10 ГБ** — см. [DISK.md](./DISK.md).

## Один раз — настроить всё

```powershell
cd C:\Users\420\Documents\develop\forgithub
.\scripts\setup-workspace.ps1
```

- pre-commit проверка секретов
- отчёт по занятому месту
- venv + npm для Jarvis Free (если установлены Python/Node)

## Проекты

| Проект | Папка | Ссылка на GitHub |
|--------|-------|------------------|
| Jarvis Free | [Jarvis_free/](./Jarvis_free/) | [tree/main/Jarvis_free](https://github.com/Interfero/forgithub/tree/main/Jarvis_free) |

Полный список: [PROJECTS.md](./PROJECTS.md)

## Полезные команды

```powershell
.\scripts\disk-status.ps1          # сколько занято из 10 GB
.\scripts\cleanup-workspace.ps1    # очистка кэшей
.\scripts\check-secrets.ps1        # проверка перед коммитом
.\scripts\guard-disk.ps1           # блок перед тяжёлой загрузкой
```

## Перенос проекта из develop

```powershell
.\scripts\prepare-project-for-public.ps1 -SourcePath "C:\Users\420\Documents\develop\ИМЯ" -TargetName "ИМЯ"
.\scripts\check-secrets.ps1 -Path "ИМЯ"
git add .
git commit -m "Add project"
git push
```

## Документация

| Файл | Описание |
|------|----------|
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Работа collaborators, первый запуск |
| [DISK.md](./DISK.md) | Лимит 10 ГБ, профили, очистка |
| [SECURITY.md](./SECURITY.md) | Секреты, EXE, что нельзя публиковать |
| [ACCESS.md](./ACCESS.md) | Доступ к репозиторию |

## Правила

- Только код, готовый к публичному показу.
- Секреты — локально (`.env`, `*.key`), в git только `*.example`.
- EXE и `dist/` не коммитим.
