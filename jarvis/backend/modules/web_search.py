"""
Веб у Jarvis:
- search_google — Google SERP через headless Chromium (основной для исследований);
- web_search — DuckDuckGo (сниппеты, резерв);
- fetch_url — сначала встроенный headless Chromium (Playwright), иначе httpx.
"""

from __future__ import annotations

import concurrent.futures
import re
from html import unescape

_PROBE_TOTAL_SEC = 8.0
_PROBE_HTML_SEC = 4.0


def _sanitize_probe_error(exc: BaseException) -> str:
    """Короткое описание для отчёта «Проверка систем» — без обрезанных URL."""
    raw = str(exc or "").replace("\n", " ").strip()
    low = raw.lower()
    if "bing.com" in low or "duckduckgo" in low and "connect" in low:
        return (
            "Сервер поиска недоступен (сеть, VPN или прокси Windows). "
            "Jarvis использует библиотеку duckduckgo-search."
        )
    if "proxy" in low or "socks" in low:
        return "Прокси Windows мешает поиску — проверьте настройки сети"
    if "timeout" in low or "timed out" in low:
        return "Таймаут запроса к поисковику"
    if "connect" in low:
        return "Нет соединения с сервером поиска"
    if len(raw) > 100:
        return raw[:97] + "…"
    return raw or "неизвестная ошибка"


def _probe_duckduckgo_html_fallback(query: str = "jarvis", *, timeout_sec: float = _PROBE_HTML_SEC) -> bool:
    """Запасная проверка без duckduckgo-search (часто ломается из-за Bing API)."""
    import httpx

    q = (query or "jarvis").strip()[:40]
    url = f"https://html.duckduckgo.com/html/?q={q}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    for trust_env in (False, True):
        try:
            with httpx.Client(
                timeout=timeout_sec,
                follow_redirects=True,
                trust_env=trust_env,
                headers=headers,
            ) as client:
                r = client.get(url)
            if r.status_code != 200:
                continue
            body = (r.text or "").lower()
            if "result" in body or "web-result" in body or len(body) > 2000:
                return True
        except Exception:
            continue
    return False


def _probe_duckduckgo_search_inner() -> tuple[str, str]:
    from modules.network_env import probe_internet

    net_ok, net_detail = probe_internet()
    if not net_ok:
        return "warn", f"Нет интернета: {net_detail[:80]}"

    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text("jarvis", max_results=1))
        if raw:
            title = (raw[0].get("title") or "").strip()
            if title and title != "Ошибка поиска":
                return "ok", "DuckDuckGo — ответ получен"
    except Exception as e:
        if _probe_duckduckgo_html_fallback():
            return (
                "warn",
                "API duckduckgo-search недоступен; HTML-поиск DuckDuckGo работает",
            )
        return "warn", _sanitize_probe_error(e)

    if _probe_duckduckgo_html_fallback():
        return "warn", "Сниппеты пустые; HTML DuckDuckGo отвечает"
    return "warn", "Пустой ответ DuckDuckGo"


def probe_duckduckgo_search() -> tuple[str, str]:
    """
    Проверка веб-поиска для отчёта. Уровень: ok | warn | err.
    Не смешивает с Chromium. Жёсткий таймаут — отчёт не должен висеть минутами.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_probe_duckduckgo_search_inner)
        try:
            return fut.result(timeout=_PROBE_TOTAL_SEC)
        except concurrent.futures.TimeoutError:
            return (
                "warn",
                f"Проверка DuckDuckGo > {_PROBE_TOTAL_SEC:.0f} с — пропущено (сеть/VPN)",
            )
        except Exception as e:
            return "warn", _sanitize_probe_error(e)


def probe_jarvis_browsers() -> tuple[str, str]:
    """Статус встроенных браузеров Jarvis для отчёта."""
    from modules.chromium_browser import probe_embedded_chromium
    from modules.jarvis_browsers import (
        find_headless_chromium_exe,
        find_windowed_chrome_exe,
        jarvis_browsers_dir,
    )

    ch_lv, ch_det = probe_embedded_chromium()
    head = find_headless_chromium_exe()
    win = find_windowed_chrome_exe()
    if ch_lv == "ok" and head and win:
        return "ok", "Headless и оконный браузер в Jarvis/browsers"
    if head or win:
        parts = []
        if head:
            parts.append("headless OK")
        if win:
            parts.append("окно OK")
        return "warn", f"{', '.join(parts)} · {ch_det[:70]}"
    return ch_lv, f"{ch_det[:90]} · каталог {jarvis_browsers_dir()}"


def search_google(
    query: str, max_results: int = 10
) -> tuple[list[dict[str, str]], str]:
    """
    Поиск в Google через headless Chromium Jarvis.
    Возвращает (results, engine_tag). При ошибке — DuckDuckGo как резерв.
    """
    q = (query or "").strip()
    if not q:
        return [], "none"
    n = max(1, min(int(max_results or 10), 10))
    try:
        from modules.chromium_browser import google_search_results

        raw = google_search_results(q, max_results=n)
        out: list[dict[str, str]] = []
        for r in raw or []:
            out.append(
                {
                    "title": (r.get("title") or "").strip(),
                    "url": (r.get("url") or "").strip(),
                    "snippet": (r.get("snippet") or "").strip(),
                }
            )
        if out:
            return out, "google_chromium"
    except Exception:
        pass
    ddg = search_web(q, max_results=n)
    if ddg and ddg[0].get("title") != "Ошибка поиска":
        return ddg, "duckduckgo_fallback"
    return ddg, "duckduckgo_fallback"


def search_web(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Список результатов: title, url, snippet."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            raw = list(ddgs.text(q, max_results=max_results))
        out: list[dict[str, str]] = []
        for r in raw:
            out.append(
                {
                    "title": (r.get("title") or "").strip(),
                    "url": (r.get("href") or r.get("link") or "").strip(),
                    "snippet": (r.get("body") or r.get("snippet") or "").strip(),
                }
            )
        return out
    except Exception as e:
        return [{"title": "Ошибка поиска", "url": "", "snippet": str(e)[:500]}]


def search_web_text(query: str, max_results: int = 5) -> str:
    """Чистый текст сниппетов для LLM / Qwen."""
    results = search_web(query, max_results=max_results)
    if not results:
        return "По запросу ничего не найдено в DuckDuckGo."
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title") or "Без названия"
        snippet = r.get("snippet") or ""
        url = r.get("url") or ""
        block = f"{i}. **{title}**\n{snippet}"
        if url:
            block += f"\nИсточник: {url}"
        lines.append(block)
    return "\n\n".join(lines)


def _html_to_plain(html: str, limit: int = 8000) -> str:
    from modules.markitdown_bridge import try_convert_html

    md = try_convert_html(html, max_chars=limit)
    if md:
        return md[0]

    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s


def _looks_like_html(text: str) -> bool:
    low = (text or "")[:2000].lower()
    return "<html" in low or "<body" in low or ("<div" in low and "</" in low)


def _fetch_url_httpx(url: str, max_chars: int = 8000) -> str:
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    last_err: Exception | None = None
    r = None
    for trust_env in (True, False):
        try:
            with httpx.Client(
                follow_redirects=True,
                timeout=25.0,
                trust_env=trust_env,
                headers=headers,
            ) as client:
                r = client.get(url)
            break
        except Exception as e:
            last_err = e
            err = str(e).lower()
            if not trust_env or "proxy" not in err and "scheme" not in err:
                raise
    if r is None:
        raise last_err or RuntimeError("HTTP fetch failed")
    ctype = (r.headers.get("content-type") or "").lower()
    if "text" not in ctype and "html" not in ctype and "json" not in ctype:
        return (
            f"Ответ {r.status_code}, тип {ctype or '?'}. "
            "Jarvis не открывает бинарные файлы — только текст/HTML."
        )
    raw = r.text
    plain = _html_to_plain(raw, limit=max_chars)
    final = str(r.url)
    engine = "markitdown" if _looks_like_html(raw) else "httpx"
    if len(plain) < 80:
        return (
            f"Страница (HTTP без JS): {final}\n"
            "Текста мало — для таких сайтов нужен встроенный Chromium "
            "(install-chromium.bat)."
        )
    return (
        f"URL: {final}\nHTTP: {r.status_code} · движок: {engine}\n\n{plain}\n\n"
        "_Загрузка через HTTP, без JavaScript._"
    )


def fetch_url_text(url: str, max_chars: int = 8000) -> str:
    """
    Открыть страницу: встроенный Chromium (Playwright), при недоступности — httpx.
    """
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return "Ошибка: укажите полный URL (https://…)."

    chromium_err = ""
    chromium_body = ""
    try:
        from modules.chromium_browser import browse_url_text as chromium_browse

        chromium_body = chromium_browse(u, max_chars=max_chars)
        low = chromium_body.lower()
        hard_fail = (
            "не готов",
            "не запускается",
            "ещё скачивается",
            "ошибка: укажите полный url",
            "chrome.exe не найден",
        )
        if chromium_body and not any(x in low[:500] for x in hard_fail):
            if len(chromium_body) > 60 or "встроенный chromium" in low:
                if _looks_like_html(chromium_body):
                    from modules.markitdown_bridge import try_convert_html

                    md = try_convert_html(chromium_body, max_chars=max_chars)
                    if md:
                        text, engine = md
                        return f"URL: {u}\nДвижок: {engine}\n\n{text}"
                return chromium_body
    except Exception as e:
        chromium_err = str(e)[:200]

    try:
        from modules.chromium_browser import chromium_browser_status

        st = chromium_browser_status()
        if chromium_body.strip():
            return chromium_body
        fallback = _fetch_url_httpx(u, max_chars=max_chars)
        if chromium_err:
            return f"{fallback}\n\n_Chromium: {chromium_err}_"
        if not st.get("ready"):
            return (
                f"{fallback}\n\n_Chromium: {st.get('detail') or 'установка или проверка запуска…'}_"
            )
        return fallback
    except Exception as e:
        if chromium_err:
            return f"Не удалось открыть страницу. Chromium: {chromium_err}. HTTP: {e}"[:500]
        return f"Не удалось загрузить страницу: {e}"[:500]
