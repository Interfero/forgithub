# forgithub

Публичная рабочая папка для проектов на GitHub.

**Репозиторий публичный** — всё в `main` видно в интернете. Перед переносом проектов и сборкой EXE обязательно соблюдайте [SECURITY.md](./SECURITY.md).

## Быстрый старт

```powershell
cd C:\Users\420\Documents\develop\forgithub
.\scripts\setup-security.ps1
```

Включает pre-commit проверку секретов перед каждым коммитом.

## Перенос проекта из develop

```powershell
.\scripts\prepare-project-for-public.ps1 -SourcePath "C:\Users\420\Documents\develop\ИМЯ_ПРОЕКТА" -TargetName "ИМЯ_ПРОЕКТА"
.\scripts\check-secrets.ps1 -Path "ИМЯ_ПРОЕКТА"
git add .
git commit -m "Add project NAME"
git push
```

## Документация

| Файл | Описание |
|------|----------|
| [SECURITY.md](./SECURITY.md) | Чеклист безопасности, EXE, что нельзя публиковать |
| [ACCESS.md](./ACCESS.md) | Как выдать доступ collaborators |

## Правила

- Только код, готовый к публичному показу.
- Секреты — в локальный `.env` (не в git), в репозитории только `.env.example`.
- EXE и `dist/` не коммитим — только исходники.

## Лицензия

Укажите лицензию для каждого проекта отдельно или добавьте общий `LICENSE` в корень.
