"""
Запросы «посмотри ссылку / покажи содержимое» — Chromium (fetch_url), понятный разбор для Шефа.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re

_log = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)

_PAGE_ACTION_RE = re.compile(
    r"посмотр|открой|зайди|перейди|что\s+на\s+(?:страниц|сайт)|"
    r"содержим|текст\s+страниц|покажи\s+(?:мне\s+)?(?:страниц|сайт|url|ссылк)|"
    r"прочитай\s+страниц|оцени\s+сайт|разбор\s+сайт|seo|сео|"
    r"fetch|browse|open\s+(?:the\s+)?(?:page|url|link)",
    re.I,
)

_FULL_PAGE_RE = re.compile(
    r"покажи\s+содержим|текст\s+страниц|весь\s+текст|полный\s+текст|"
    r"скопируй\s+страниц|выведи\s+страниц|содержимое\s+страниц|"
    r"show\s+(?:me\s+)?(?:the\s+)?content|full\s+page",
    re.I,
)

_REFUSAL_BLEED_RE = re.compile(
    r"impossible as an ai|without using external tools|"
    r"не могу просматривать|не умею открывать|as an ai assistant|"
    r"зайдите\s+сами|откройте\s+(?:эту\s+)?страниц|в\s+браузере\s+сам|"
    r"перейдите\s+на\s+сайт|не\s+могу\s+определить",
    re.I,
)

_FETCH_TIMEOUT_SEC = 75.0
_PAGE_CACHE: dict[str, tuple[float, str]] = {}
_PAGE_CACHE_TTL = 300.0


def extract_first_url(text: str) -> str | None:
    m = _URL_RE.search(text or "")
    if not m:
        return None
    return m.group(0).rstrip(".,);]}")


def extract_url_from_context(
    user_text: str,
    history: list[dict] | None = None,
) -> str | None:
    url = extract_first_url(user_text)
    if url:
        return url
    for msg in reversed(history or []):
        if msg.get("role") not in ("user", "assistant"):
            continue
        url = extract_first_url(str(msg.get("content") or ""))
        if url:
            return url
    return None


def user_wants_full_page_content(text: str) -> bool:
    return bool(_FULL_PAGE_RE.search(text or ""))


_PAGE_FOLLOWUP_RE = re.compile(
    r"эта\s+страниц|этот\s+сайт|по\s+ссылк|на\s+страниц|там\s+на\s+сайт|"
    r"что\s+там\s+на|организац|2\s*gis|seo|сео|пересчит|"
    r"не\s+то\s+число|неправильно\s+счит",
    re.I,
)


def user_wants_page_lookup(text: str, history: list[dict] | None = None) -> bool:
    """
    Браузер только при ссылке в **текущем** сообщении или явном продолжении разбора страницы.
    Старая ссылка в истории + «привет» — не открывать Chromium.
    """
    from modules.page_extract import user_disputes_page_answer

    msg = (text or "").strip()
    if not msg:
        return False

    try:
        from modules.dialog_handlers import is_casual_smalltalk

        if is_casual_smalltalk(msg):
            return False
    except Exception:
        pass

    if extract_first_url(msg):
        return True

    if not history:
        return False
    if extract_url_from_context("", history) is None:
        return False

    if user_disputes_page_answer(msg):
        return True
    if _PAGE_ACTION_RE.search(msg):
        return True
    if _PAGE_FOLLOWUP_RE.search(msg):
        return True

    return False


def fetch_page_raw(url: str, *, max_chars: int = 12_000) -> str:
    from modules.web_search import fetch_url_text

    return fetch_url_text(url, max_chars=max_chars)


def _cache_get(url: str) -> str | None:
    import time

    key = (url or "").strip().rstrip("/").lower()
    hit = _PAGE_CACHE.get(key)
    if not hit:
        return None
    at, body = hit
    if time.monotonic() - at > _PAGE_CACHE_TTL:
        _PAGE_CACHE.pop(key, None)
        return None
    return body


def _cache_put(url: str, body: str) -> None:
    import time

    key = (url or "").strip().rstrip("/").lower()
    if body and len(body.strip()) > 40:
        _PAGE_CACHE[key] = (time.monotonic(), body)


def _fetch_page_safe(url: str, *, max_chars: int = 14_000) -> str:
    """Загрузка страницы (вызывать из worker-потока, не из event loop)."""
    cached = _cache_get(url)
    if cached:
        return cached
    try:
        body = fetch_page_raw(url, max_chars=max_chars)
        _cache_put(url, body)
        return body
    except concurrent.futures.TimeoutError:
        return (
            "Страница открывается слишком долго (таймаут). "
            "Попробуйте позже или упростите сайт; проверьте Chromium на панели."
        )
    except Exception as e:
        _log.warning("fetch_page_safe %s: %s", url, e)
        return f"Ошибка при открытии страницы: {str(e)[:240]}"


def format_page_for_chat(
    raw: str,
    url: str,
    *,
    full_text: bool = False,
    title: str = "",
) -> str:
    from modules.page_seo_audit import build_page_audit_reply

    return build_page_audit_reply(url, raw, full_text=full_text)


def try_handle_url_page_request(
    user_text: str,
    history: list[dict] | None = None,
) -> tuple[bool, str]:
    if not user_wants_page_lookup(user_text, history):
        return False, ""

    url = extract_first_url(user_text or "") or extract_url_from_context(
        user_text, history
    )
    if not url:
        return False, ""

    from modules.agent import get_runtime

    full = user_wants_full_page_content(user_text)
    rt = get_runtime()
    prev = rt.status
    rt.status = "Searching Web..."
    try:
        raw = _fetch_page_safe(url, max_chars=14_000 if full else 12_000)
    finally:
        rt.status = prev if prev != "Searching Web..." else "IDLE"

    recount = False
    from modules.page_extract import user_disputes_page_answer

    if user_disputes_page_answer(user_text):
        recount = True
    return True, _reply_from_page_text(user_text, url, raw, full=full, recount=recount)


def _reply_from_page_text(
    user_text: str,
    url: str,
    raw: str,
    *,
    full: bool = False,
    recount: bool = False,
) -> str:
    from modules.page_extract import (
        answer_org_count_from_page,
        is_2gis_browser_wall,
        message_for_2gis_wall,
        sanitize_chat_text,
        user_asks_org_count,
    )
    from modules.page_seo_audit import build_page_audit_reply, strip_browse_metadata
    from modules.text_sanitize import polish_page_content_reply

    body = strip_browse_metadata(raw)
    if is_2gis_browser_wall(body) or (is_2gis_browser_wall(raw) and len(body) < 80):
        msg = message_for_2gis_wall(url)
        return "<!-- jarvis-page-content -->\n" + polish_page_content_reply(msg, user_text)

    want_count = user_asks_org_count(user_text) or recount
    if want_count:
        direct = answer_org_count_from_page(user_text, url, body, recount=recount)
        if direct:
            from modules.page_seo_audit import strip_extra_urls

            return (
                "<!-- jarvis-page-content -->\n"
                + polish_page_content_reply(strip_extra_urls(direct, url), user_text)
            )

    reply = build_page_audit_reply(url, raw, user_text, full_text=full)
    return "<!-- jarvis-page-content -->\n" + polish_page_content_reply(reply, user_text)
