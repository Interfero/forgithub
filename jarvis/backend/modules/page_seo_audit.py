"""
Анализ страницы для Шефа: SEO, дизайн, функционал, сложность разработки.
Ответ простым языком, без лишних ссылок (кроме URL из запроса).
"""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlparse

from modules.page_extract import sanitize_chat_text, to_plain_text
from modules.chromium_stealth import strip_chromium_wrapper

_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"')]+", re.I)
_BROWSE_HEAD = re.compile(
    r"^\*\*Браузер Jarvis[^\n]*\*\*\s*\n(?:URL:\s*[^\n]+\n)?(?:Заголовок:\s*[^\n]+\n+)?",
    re.M | re.I,
)
_BROWSE_TAIL = re.compile(
    r"\n+_\s*(?:Лучший результат|Страница открыта)[^\n]*_\s*$",
    re.I,
)
_BY_LINK = re.compile(r"^\*\*По ссылке\*\*\s+https?://\S+\s*\n+", re.I | re.M)
_PAGE_CONTENT_HDR = re.compile(
    r"^\*\*Содержимое страницы\*\*\s+https?://\S+\s*\n+",
    re.I | re.M,
)

_FEATURE_HINTS: list[tuple[str, str]] = [
    (r"\b(корзин|оформить заказ|купить|каталог|товар)\b", "интернет-магазин / каталог"),
    (r"\b(войти|регистрац|личн\w+\s+кабинет|авторизац)\b", "регистрация и вход"),
    (r"\b(оплат|банковск\w+\s+карт|paypal|stripe)\b", "оплата онлайн"),
    (r"\b(поиск|найти|фильтр)\b", "поиск и фильтры"),
    (r"\b(карт[аы]|маршрут|2гис|яндекс\.карт)\b", "карта или геосервис"),
    (r"\b(блог|новост|стать[ия])\b", "блог или новости"),
    (r"\b(контакт|обратн\w+\s+связ|заявк|форм)\b", "формы обратной связи"),
    (r"\b(скачать|pdf|документ)\b", "скачивание файлов"),
    (r"\b(чат|поддержк|telegram|whatsapp)\b", "онлайн-поддержка / мессенджеры"),
    (r"\b(видео|youtube|плеер)\b", "видео-контент"),
    (r"\b(язык|english|русск)\b", "мультиязычность"),
]

_COMPLEXITY_HIGH = (
    "личный кабинет",
    "оплата",
    "интернет-магазин",
    "карта",
    "регистрация",
    "фильтр",
)
_COMPLEXITY_LOW = ("визитка", "лендинг", "одна страница", "контакты")


def strip_browse_metadata(raw: str) -> str:
    """Убрать служебные строки Playwright из текста страницы."""
    s = strip_chromium_wrapper(raw or "")
    s = _BROWSE_HEAD.sub("", s)
    s = _BROWSE_TAIL.sub("", s)
    s = _BY_LINK.sub("", s)
    s = _PAGE_CONTENT_HDR.sub("", s)
    s = re.sub(r"^URL:\s*https?://\S+\s*\n", "", s, flags=re.I | re.M)
    s = re.sub(r"^HTTP:\s*\d+\s*\n", "", s, flags=re.I | re.M)
    s = re.sub(r"_Загрузка через HTTP[^_]*_", "", s, flags=re.I)
    return sanitize_chat_text(s.strip())


def strip_extra_urls(text: str, keep_url: str | None) -> str:
    """Удалить все http(s) ссылки, кроме URL из запроса Шефа."""
    keep = (keep_url or "").strip().rstrip(".,);]")
    if not keep:
        return _URL_IN_TEXT.sub("", text or "")

    def repl(m: re.Match[str]) -> str:
        u = m.group(0).rstrip(".,);]")
        if u.rstrip("/") == keep.rstrip("/"):
            return u
        return ""

    return _URL_IN_TEXT.sub(repl, text or "")


def _site_kind(url: str, body: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    low = (body or "").lower()[:4000]
    if "2gis" in host or "2гис" in low:
        return "каталог организаций / карта (похоже на 2ГИС)"
    if any(x in host for x in ("avito", "ozon", "wildberries", "market")):
        return "маркетплейс или объявления"
    if any(x in host for x in ("github", "gitlab")):
        return "репозиторий или документация для разработчиков"
    if any(x in low for x in ("войти", "регистрация", "корзина")):
        return "сервис с личным кабинетом или покупками"
    if len(body) < 400:
        return "короткая страница (визитка или лендинг)"
    return "информационный сайт или сервис"


def _detect_features(body: str) -> list[str]:
    low = body.lower()
    found: list[str] = []
    for pat, label in _FEATURE_HINTS:
        if re.search(pat, low, re.I) and label not in found:
            found.append(label)
    return found[:8]


def _estimate_dev_complexity(features: list[str], body: str) -> tuple[str, str]:
    n = len(body)
    score = 0
    if n > 8000:
        score += 2
    elif n > 2500:
        score += 1
    score += min(len(features), 5)
    for f in features:
        if any(h in f.lower() for h in _COMPLEXITY_HIGH):
            score += 2
    if score <= 2:
        level = "низкая"
        detail = (
            "Похоже на визитку или простой лендинг: можно собрать за несколько дней "
            "на конструкторе или за 1–2 недели с нуля у небольшой команды."
        )
    elif score <= 5:
        level = "средняя"
        detail = (
            "Нужны типовые блоки, формы, возможно каталог или личный кабинет — "
            "ориентир от нескольких недель до пары месяцев у команды из 2–3 человек."
        )
    else:
        level = "высокая"
        detail = (
            "Много сценариев (покупки, карты, кабинеты, интеграции) — "
            "это уже полноценный продукт на месяцы разработки и поддержки."
        )
    return level, detail


def _first_lines(body: str, n: int = 6) -> str:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return "\n".join(lines[:n])


def _seo_notes(body: str, title_hint: str) -> str:
    words = re.findall(r"[а-яёa-z0-9]{3,}", body.lower(), re.I)
    wc = len(words)
    uniq = len(set(words))
    lines: list[str] = []
    if title_hint:
        tl = len(title_hint)
        if tl < 25:
            lines.append("Заголовок страницы короткий — для поиска лучше 30–60 символов с ключевыми словами.")
        elif tl > 70:
            lines.append("Заголовок длинноват для сниппета в поиске — часть обрежется.")
        else:
            lines.append("Заголовок по длине подходит для поисковой выдачи.")
    if wc < 120:
        lines.append("Мало текста на странице — поисковикам сложнее понять тему.")
    elif wc > 2500:
        lines.append("Много текста — хорошо для SEO, если он структурирован заголовками.")
    else:
        lines.append("Объём текста умеренный — для SEO нормально при понятной структуре.")
    if uniq and wc and uniq / max(wc, 1) < 0.25:
        lines.append("Много повторяющихся слов — возможно, шаблонный или списочный контент.")
    top = Counter(w for w in words if len(w) > 4).most_common(5)
    if top:
        keys = ", ".join(w for w, _ in top)
        lines.append(f"Частые темы на странице: {keys}.")
    return " ".join(lines) if lines else "Явных SEO-меток в тексте мало — ориентируйтесь на заголовок и первый экран."


def _design_notes(body: str) -> str:
    low = body.lower()
    hints: list[str] = []
    if re.search(r"меню|навигац|главная|о нас|услуг", low):
        hints.append("есть навигация и разделы")
    if re.search(r"подвал|контакт|политик|cookie", low):
        hints.append("есть подвал с контактами или юридическими ссылками")
    if re.search(r"фильтр|сортиров|категор", low):
        hints.append("много элементов списка — важна аккуратная вёрстка карточек")
    if len(body) > 6000:
        hints.append("страница перегружена текстом — пользователю нужна чёткая иерархия")
    if not hints:
        return "По тексту страница выглядит простой: один основной блок без сложного интерфейса."
    return "По структуре: " + "; ".join(hints) + "."


def _content_summary(body: str, url: str) -> str:
    lines = [ln.strip() for ln in body.splitlines() if len(ln.strip()) > 20]
    if not lines:
        return "Текст страницы почти пустой или не удалось его извлечь (блокировка, капча, только картинки)."
    preview = lines[0][:280]
    if len(lines) > 1:
        preview += " … " + lines[1][:120]
    kind = _site_kind(url, body)
    return f"Это {kind}. Суть: {preview}"


def build_page_audit_reply(
    url: str,
    raw_page: str,
    user_text: str = "",
    *,
    full_text: bool = False,
) -> str:
    """
    Понятный отчёт для чата. Одна ссылка — из запроса Шефа.
    """
    body = strip_browse_metadata(raw_page)
    if not body and raw_page:
        body = sanitize_chat_text(to_plain_text(raw_page, limit=14_000))

    title_hint = ""
    m = re.search(r"^Заголовок:\s*(.+)$", raw_page or "", re.M | re.I)
    if m:
        title_hint = m.group(1).strip()[:200]
    if not title_hint:
        first = body.split("\n", 1)[0].strip()
        if 10 < len(first) < 120:
            title_hint = first

    if full_text:
        block = body[:7500] + ("…" if len(body) > 7500 else "")
        text = (
            f"Полный текст страницы по вашей ссылке:\n{url}\n\n{block}"
            if block
            else f"Текст не получен. Ссылка: {url}"
        )
        return strip_extra_urls(text, url)

    low_raw = (raw_page or "").lower()
    if any(
        x in low_raw[:600]
        for x in (
            "не готов",
            "ещё скачивается",
            "не удалось",
            "chrome.exe не найден",
            "нет интернета",
        )
    ):
        return strip_extra_urls(
            f"Страницу открыть не удалось.\n\n{sanitize_chat_text(raw_page)[:500]}",
            url,
        )

    if len(body) < 40:
        return (
            f"Страница по ссылке {url} открылась, но текста почти нет — "
            "возможны капча, блокировка бота или сайт рисуется только картинками. "
            "Проверьте чип «Chromium» на панели и откройте ссылку вручную для сравнения."
        )

    features = _detect_features(body)
    complexity, complexity_detail = _estimate_dev_complexity(features, body)
    feature_line = (
        ", ".join(features) if features else "типовой информационный контент без сложных сервисов"
    )

    parts = [
        f"**Разбор страницы** (ваша ссылка: {url})",
        "",
        "### О чём сайт",
        _content_summary(body, url),
        "",
        "### SEO и тексты",
        _seo_notes(body, title_hint),
        "",
        "### Дизайн и удобство (по структуре текста)",
        _design_notes(body),
        "",
        "### Функционал",
        f"На странице заметно: {feature_line}.",
        "",
        "### Сложность сделать похожее",
        f"Оценка: **{complexity}**. {complexity_detail}",
    ]

    if user_text and len(user_text.strip()) > 8:
        q = user_text.strip()[:200]
        parts.extend(["", "### На ваш вопрос", f"Смотрел страницу в контексте: «{q}» — ответ основан только на её тексте."])

    parts.extend(
        [
            "",
            "### Фрагмент с страницы",
            _first_lines(body, 5),
        ]
    )

    text = "\n".join(parts)
    return strip_extra_urls(text, url)
