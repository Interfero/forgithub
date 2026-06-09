# Настройка страницы репозитория на GitHub

Краткая инструкция, чтобы репозиторий выглядел **понятно и по-русски**, как у [OpenConnect GUI](https://github.com/openconnect/openconnect-gui/releases).

---

## 1. Создайте отдельный репозиторий (рекомендуется)

Сейчас папка `jarvis` может лежать внутри большого репозитория (`svyazi`). Для публичного «Джарвиса» лучше:

1. GitHub → **New repository** → имя, например: `jarvis`
2. Описание (Description) — см. ниже
3. Public, без README (мы уже добавили свой)
4. Залейте только содержимое папки `jarvis`

---

## 2. Описание репозитория (About)

В правой колонке на GitHub → **⚙ About** → **Edit**:

**Description (кратко):**
```
Бесплатный голосовой ассистент для Windows — open-source разработка проекта «Джарвис»
```

**Website (по желанию):**
```
https://github.com/Interfero/jarvis/releases
```
_(замените на свой URL)_

**Topics (темы):**
```
jarvis
voice-assistant
windows
russian
open-source
speech-recognition
assistant
```

---

## 3. README на главной

Файл [README.md](../README.md) уже оформлен на русском. После push он станет главной страницей репозитория.

**Важно:** в README и CHANGELOG замените `ВАШ_АККАУНТ/jarvis` на реальный путь, например `Interfero/jarvis`.

---

## 4. Первый релиз (Releases)

1. GitHub → **Releases** → **Draft a new release**
2. Tag: `v0.1.0` (или ваша версия)
3. Title: **`v0.1.0 — первый публичный релиз`**
4. Описание — скопируйте из [.github/release_template.md](../.github/release_template.md) и заполните пункты
5. Прикрепите zip-сборку (если есть) + исходники создаст GitHub автоматически

Пример заголовка в стиле OpenConnect:

> **v0.2.0**  
> Пара исправлений и несколько небольших улучшений:

Список с `-` и ссылками на `#issue` — как на скриншоте OpenConnect.

---

## 5. Что не публиковать

Перед push проверьте, что **нет в репозитории**:

- паролей SSH, API-ключей;
- `deepseek_free.key`, `.env`.

Добавьте их в `.gitignore`, если ещё не добавлены.

> Настройки VPN вынесены в отдельный проект `develop/vpn`.

---

## 6. Язык интерфейса GitHub

Подписи вроде «Assets» / «Активы» и «Latest» / «Последние» GitHub переводит **сам**, если в профиле выбран русский язык:

**Settings → Language → Русский**

Текст релизов и README вы пишете сами — они будут на русском.

---

## 7. Бейдж «бесплатно» (опционально)

В README можно добавить вверху:

```markdown
![License: MIT](https://img.shields.io/badge/лицензия-MIT-green)
![Free](https://img.shields.io/badge/стоимость-бесплатно-blue)
```

---

Готово: понятное описание, русские релизы, MIT-лицензия и явное сообщение, что репозиторий для **бесплатного** развития «Джарвиса».
