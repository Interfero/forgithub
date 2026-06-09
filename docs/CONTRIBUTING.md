# Участие в проекте

Публичный репозиторий: [Interfero/forgithub](https://github.com/Interfero/forgithub).

## Первый день

```powershell
git clone https://github.com/Interfero/forgithub.git
cd forgithub
.\scripts\setup-workspace.ps1
cd jarvis
.\start.bat
```

Это включает:

- pre-commit проверку секретов (`setup-security.ps1`)
- отчёт по диску (лимит **10 ГБ**, см. [DISK.md](./DISK.md))
- установку зависимостей Jarvis (Python venv + npm) при первом `start.bat`

## Перед каждым коммитом

1. Не коммитьте `.env`, ключи, чаты, `.db` с личными данными.
2. Pre-commit запустит `check-secrets.ps1` автоматически.
3. Вручную: `.\scripts\check-secrets.ps1`

## Обновить Jarvis из develop

```powershell
.\scripts\prepare-jarvis-for-public.ps1 -SourcePath "C:\Users\420\Documents\develop\jarvis"
.\scripts\check-secrets.ps1 -Path jarvis
git add jarvis
git commit -m "Update Jarvis v1"
git push
```

## Добавить новый проект из develop

```powershell
.\scripts\prepare-project-for-public.ps1 -SourcePath "C:\path\to\project" -TargetName "ProjectName"
.\scripts\check-secrets.ps1 -Path "ProjectName"
git add .
git commit -m "Add ProjectName"
git push
```

## Jarvis v1

- Код: [jarvis/](../jarvis/)
- Запуск: `jarvis\start.bat` → http://127.0.0.1:8000/
- Ключи: Настройки в UI или `jarvis\backend\data\settings.json` (не в git)
- **Не** качайте Qwen 14B при лимите 10 ГБ — см. `jarvis\install-qwen.bat` и [DISK.md](./DISK.md)

## Доступ collaborator

См. [ACCESS.md](./ACCESS.md). Нужна роль **Write** для push.

## Сборка EXE

Только после `check-secrets.ps1`. EXE и `dist/` **не** пушим в GitHub — см. [SECURITY.md](./SECURITY.md).
