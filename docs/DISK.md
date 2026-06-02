# Лимит диска: 10 ГБ

В этом репозитории действует **бюджет 10 ГБ** на типичную рабочую копию: исходники + venv + node_modules + модели + данные Jarvis в `%LOCALAPPDATA%`.

Это не лимит всего диска Windows — только зона ответственности проекта.

## Проверить занятое место

```powershell
cd C:\Users\420\Documents\develop\forgithub
.\scripts\disk-status.ps1
```

JSON для скриптов:

```powershell
.\scripts\disk-status.ps1 -Json
```

## Профили (рекомендации)

| Профиль | Модель Qwen | Примерно на диске | Когда использовать |
|---------|-------------|-------------------|---------------------|
| **apiOnly** (по умолчанию) | не скачивать | ~2–4 ГБ | DeepSeek API ключ, 10 ГБ хватает |
| localQwen3b | 3B GGUF ~2 ГБ | ~5–7 ГБ | локальная модель без облака |
| localQwen14b | 14B GGUF ~9 ГБ | **> 10 ГБ** | **не влезает** в бюджет вместе с venv и deps |

**Вывод:** при лимите 10 ГБ не запускайте `install-qwen.bat` (14B). Используйте ключ DeepSeek в `backend/config/deepseek_free.key`.

## Очистка

```powershell
# Безопасно: кэши, dist, частичные загрузки
.\scripts\cleanup-workspace.ps1

# Глубоко: + node_modules и venv (потом setup-workspace.ps1)
.\scripts\cleanup-workspace.ps1 -Deep
```

## Перед тяжёлыми операциями

```powershell
# Проверка с запасом под загрузку 500 MB
.\scripts\guard-disk.ps1 -RequiredBytes 524288000
```

`install-qwen-safe.bat` в Jarvis Free вызывает guard автоматически.

## Что входит в бюджет

Настройка путей: `config/workspace.json`

- папка репозитория
- `Jarvis_free/backend/venv`
- `Jarvis_free/frontend/node_modules`
- `Jarvis_free/backend/data/models`
- `%LOCALAPPDATA%\Jarvis_free\data`
- `%LOCALAPPDATA%\Jarvis\browsers` (опционально, общие с Pro)

## Изменить лимит

Отредактируйте `diskLimitGb` в `config/workspace.json` (по умолчанию **10**).
