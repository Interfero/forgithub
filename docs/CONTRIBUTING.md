# Участие в проекте

Публичный репозиторий: [Interfero/forgithub](https://github.com/Interfero/forgithub).

## Первый день

```powershell
git clone https://github.com/Interfero/forgithub.git
cd forgithub
.\scripts\setup-workspace.ps1
```

Это включает:

- pre-commit проверку секретов (`setup-security.ps1`)
- отчёт по диску (лимит **10 ГБ**, см. [DISK.md](./DISK.md))
- установку зависимостей Jarvis Free (Python venv + npm), если есть Node/Python

## Перед каждым коммитом

1. Не коммитьте `.env`, ключи, чаты, `.db` с личными данными.
2. Pre-commit запустит `check-secrets.ps1` автоматически.
3. Вручную: `.\scripts\check-secrets.ps1`

## Добавить новый проект из develop

```powershell
.\scripts\prepare-project-for-public.ps1 -SourcePath "C:\path\to\project" -TargetName "ProjectName"
.\scripts\check-secrets.ps1 -Path "ProjectName"
git add .
git commit -m "Add ProjectName"
git push
```

## Jarvis Free

- Код: [Jarvis_free/](../Jarvis_free/)
- Запуск: `Jarvis_free\start.bat` → http://127.0.0.1:8001/
- Ключ: `Jarvis_free\backend\config\deepseek_free.key` (не в git)
- **Не** качайте Qwen 14B при лимите 10 ГБ — см. `Jarvis_free\scripts\install-qwen-safe.bat`

## Доступ collaborator

См. [ACCESS.md](./ACCESS.md). Нужна роль **Write** для push.

## Сборка EXE

Только после `check-secrets.ps1`. EXE и `dist/` **не** пушим в GitHub — см. [SECURITY.md](./SECURITY.md).
