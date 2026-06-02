# Доступ к репозиторию

## Collaborator с правом изменять файлы

Чтобы человек мог **добавлять и менять файлы** (push в репозиторий), ему нужна роль **Write**.

### Приглашение по email (рекомендуется)

1. Откройте (владелец репозитория `Interfero`):
   **https://github.com/Interfero/forgithub/settings/access**
2. **Add people** → введите: `teddymyfirxnews@gmail.com`
3. Role: **Write**
4. **Add to repository**

GitHub отправит приглашение на почту. Человек должен:
- иметь аккаунт GitHub с этой почтой (или добавить её в Settings → Emails);
- принять приглашение по ссылке из письма.

### После принятия приглашения

Collaborator может клонировать и пушить:

```powershell
git clone https://github.com/Interfero/forgithub.git
cd forgithub
.\scripts\setup-security.ps1
```

Перед первым коммитом — прочитать `SECURITY.md`.

## Роли

| Роль | Что может |
|------|-----------|
| Read | Только читать (для публичного repo и так видно всем) |
| **Write** | Push, ветки, issues — **нужно для редактирования** |
| Maintain | Write + часть настроек |
| Admin | Полный доступ к настройкам repo |

Для редактирования кода достаточно **Write**.

## Важно

- Публичный репозиторий виден всем; Write даёт право **менять код**, не скрывает его.
- Collaborators тоже обязаны соблюдать `SECURITY.md` — не коммитить `.env` и ключи.
