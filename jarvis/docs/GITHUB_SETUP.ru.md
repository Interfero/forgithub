# Настройка страницы репозитория на GitHub

Краткая инструкция, чтобы репозиторий выглядел **понятно и по-русски**, как у [OpenConnect GUI](https://github.com/openconnect/openconnect-gui/releases).

---

## 1. Репозиторий forgithub

Публичный монорепозиторий: [Interfero/forgithub](https://github.com/Interfero/forgithub).

Jarvis v1 лежит в папке `jarvis/`. Инструкция по запуску: [START.ru.txt](../START.ru.txt).

---

## 2. Описание репозитория (About)

В правой колонке на GitHub → **⚙ About** → **Edit**:

**Description (кратко):**
```
Jarvis v1 — бесплатный голосовой AI-ассистент для Windows (open-source)
```

**Website (по желанию):**
```
https://github.com/Interfero/forgithub/tree/main/jarvis
```

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

---

## 4. Первый релиз (Releases)

1. GitHub → **Releases** → **Draft a new release**
2. Tag: `v1.0.0` (или ваша версия)
3. Title: **`v1.0.0 — Jarvis v1`**
4. Описание — скопируйте из [.github/release_template.md](../.github/release_template.md) и заполните пункты
5. Прикрепите zip-сборку (если есть) + исходники создаст GitHub автоматически

---

## 5. Что не публиковать

Перед push проверьте, что **нет в репозитории**:

- паролей SSH, API-ключей;
- `settings.json`, `huggingface.key`, `.env`.

Запустите `scripts/check-secrets.ps1` из корня forgithub.

---

## 6. Язык интерфейса GitHub

**Settings → Language → Русский**

---

## 7. Бейдж «бесплатно» (опционально)

```markdown
![License: MIT](https://img.shields.io/badge/лицензия-MIT-green)
![Free](https://img.shields.io/badge/стоимость-бесплатно-blue)
```
