"""
Глубокий веб-поиск Jarvis:
- уточнение запроса (что именно ищем);
- стереотипы (приоритетные сайты из Стереотипы.txt);
- Google → до 10 страниц → выжимка (источники — отдельно внизу).
"""

from __future__ import annotations

import queue
import re
import threading
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from modules.web_stereotypes import (
    ResearchIntent,
    match_stereotypes,
    resolve_stereotype_url,
)

ProgressFn = Callable[[int, int, str], None]

_RESEARCH_HINT = re.compile(
    r"загугл|погугл|гугл(?:и|ь)|google|"
    r"найди\s+(?:в\s+)?(?:интернет|сет(?:и|ь)|google|гугл)|"
    r"поиск\s+в\s+(?:интернет|google|гугл)|"
    r"что\s+пишут|актуальн(?:ая|ые|ую)\s+(?:данн|информ|свед)|"
    r"свеж(?:ие|ая|ую)\s+(?:новост|данн|информ)|"
    r"обзор\s+(?:по|на|о)|изучи\s+(?:в\s+)?(?:интернет|сет)|"
    r"исследуй|выжимк|просмотри\s+(?:сайты|страниц)|"
    r"search\s+(?:the\s+)?web|look\s+up",
    re.I,
)

_META_SEARCH_ABILITY = re.compile(
    r"(?:"
    r"научил(?:ся|ись|ась)|"
    r"научишься|"
    r"умеешь|можешь|"
    r"есть\s+ли\s+у\s+тебя|"
    r"ты\s+(?:умеешь|можешь)|"
    r"как\s+(?:ты\s+)?(?:ищ|работа|гугл)|"
    r"в\s+состоянии\s+(?:ли\s+)?(?:ты\s+)?"
    r")",
    re.I,
)

_META_SEARCH_TOPIC = re.compile(
    r"гугл|google|интернет|поиск|web_research|duckduckgo|стереотип|"
    r"искать\s+(?:в\s+)?(?:сет|интернет)|"
    r"гуглить|загуглить",
    re.I,
)

_STRIP_PREFIX = re.compile(
    r"^(?:"
    r"загугли|погугли|гугл(?:и|ь)|"
    r"найди\s+(?:в\s+)?(?:интернет|сет(?:и|ь)|google|гугл)|"
    r"поиск\s+в\s+(?:интернет|google|гугл)|"
    r"изучи\s+(?:в\s+)?(?:интернет|сет)|"
    r"исследуй|обзор\s+(?:по|на|о)"
    r")\s*[:—\-]?\s*",
    re.I,
)

_GENERIC_QUERY = re.compile(
    r"^(?:интернет|сеть|google|гугл|поиск|найди|найти|информаци[яю]|"
    r"актуальн(?:ая|ые)?\s+информаци[яю])$",
    re.I,
)

_SKIP_DOMAINS = (
    "google.com",
    "google.ru",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
)


def _norm_host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def _dedupe_urls(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for r in results:
        url = (r.get("url") or "").strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        host = _norm_host(url)
        if any(host == d or host.endswith("." + d) for d in _SKIP_DOMAINS):
            continue
        key = url.split("#")[0].rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def extract_search_query(text: str) -> str:
    t = (text or "").strip()
    t = _STRIP_PREFIX.sub("", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:320] or (text or "").strip()[:320]


def refine_research_intent(
    user_text: str,
    history: list[dict] | None = None,
    *,
    deepseek_key: str = "",
    model: str = "deepseek-chat",
) -> ResearchIntent:
    """Понять, какую именно информацию искать в интернете."""
    raw = (user_text or "").strip()
    query = extract_search_query(raw)
    topic = query

    if _GENERIC_QUERY.match(query.strip()) or len(query.strip()) < 4:
        for msg in reversed(history or []):
            if msg.get("role") != "user":
                continue
            prev = extract_search_query(str(msg.get("content") or ""))
            if prev and len(prev) >= 4 and not _GENERIC_QUERY.match(prev.strip()):
                query = prev
                topic = prev
                break

    key_ok = (deepseek_key or "").strip().startswith("sk-") and len(deepseek_key.strip()) >= 20
    if key_ok and len(query.split()) >= 2:
        try:
            from modules.http_proxy import httpx_client

            hist_tail = ""
            for msg in (history or [])[-4:]:
                role = msg.get("role")
                if role in ("user", "assistant"):
                    hist_tail += f"{role}: {str(msg.get('content') or '')[:400]}\n"
            prompt = (
                "Шеф просит найти информацию в интернете. Верни ОДНУ строку — "
                "точный поисковый запрос на русском (5–15 слов), без кавычек и пояснений. "
                "Только суть: что именно нужно узнать.\n\n"
                f"Сообщение: {raw}\n"
                f"Черновик: {query}\n"
            )
            if hist_tail.strip():
                prompt += f"\nКонтекст чата:\n{hist_tail}\n"
            with httpx_client(timeout=45.0, proxy=None) as client:
                resp = client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {deepseek_key.strip()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": (model or "deepseek-chat").strip() or "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "Только поисковый запрос одной строкой."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                        "max_tokens": 120,
                    },
                )
                resp.raise_for_status()
                refined = resp.json()["choices"][0]["message"]["content"].strip()
                refined = re.sub(r"^[\"«]|[\"»]$", "", refined).strip()
                refined = _STRIP_PREFIX.sub("", refined).strip()
                if len(refined) >= 4 and not _GENERIC_QUERY.match(refined):
                    query = refined[:320]
                    topic = query
        except Exception:
            pass

    query = re.sub(r"\s+", " ", query).strip()[:320]
    return ResearchIntent(query=query or raw[:200], raw_user=raw, topic=topic)


def is_web_search_meta_question(text: str) -> bool:
    """Вопрос «умеешь гуглить?» — про возможности Jarvis, не запрос поиска."""
    msg = (text or "").strip()
    if len(msg) < 6:
        return False
    try:
        from modules.local_qwen import user_requests_live_web_action

        if user_requests_live_web_action(msg):
            return False
    except Exception:
        pass
    low = msg.lower()
    if _META_SEARCH_ABILITY.search(low) and _META_SEARCH_TOPIC.search(low):
        return True
    if any(
        p in low
        for p in (
            "научился гугл",
            "научился искать",
            "умеешь гугл",
            "можешь гугл",
            "умеешь искать в интернет",
            "можешь искать в интернет",
            "ты умеешь искать",
            "ты можешь искать",
            "научился ли ты",
            "умеешь ли ты искать",
        )
    ):
        return True
    try:
        from modules.jarvis_capabilities import is_jarvis_meta_question

        if is_jarvis_meta_question(msg) and _META_SEARCH_TOPIC.search(low):
            return True
    except Exception:
        pass
    return False


def user_wants_web_research(text: str, history: list[dict] | None = None) -> bool:
    msg = (text or "").strip()
    if len(msg) < 4:
        return False
    if is_web_search_meta_question(msg):
        return False
    try:
        from modules.dialog_handlers import is_casual_smalltalk

        if is_casual_smalltalk(msg):
            return False
    except Exception:
        pass
    try:
        from modules.url_page_handler import extract_first_url, user_wants_page_lookup

        if extract_first_url(msg) and user_wants_page_lookup(msg, history):
            return False
    except Exception:
        pass
    if any(
        w in msg.lower()
        for w in (
            "можешь ли",
            "умеешь ли",
            "есть ли",
            "есть у тебя",
            "встроенн браузер",
            "просматривать страниц",
        )
    ):
        return False
    return bool(_RESEARCH_HINT.search(msg))


def _report(progress: ProgressFn | None, current: int, total: int, message: str) -> None:
    if progress:
        try:
            progress(current, total, message)
        except Exception:
            pass
    try:
        from modules.agent import get_runtime

        get_runtime().log("web.research", message)
    except Exception:
        pass


def _search_results(query: str, *, max_results: int = 10) -> tuple[list[dict[str, str]], str]:
    from modules.web_search import search_google

    results, engine = search_google(query, max_results=max_results)
    return _dedupe_urls(results)[:max_results], engine


def _fetch_page_summary(url: str, *, max_chars: int = 3800) -> str:
    from modules.local_text_utils import extractive_summarize
    from modules.web_search import fetch_url_text

    raw = fetch_url_text(url, max_chars=max_chars)
    low = raw.lower()
    if "не удалось" in low or "ошибка:" in low[:80]:
        return raw[:900]
    plain = raw
    for marker in ("URL:", "Движок:", "HTTP:"):
        if marker in raw:
            parts = raw.split("\n\n", 1)
            if len(parts) > 1:
                plain = parts[-1]
            break
    summary = extractive_summarize(plain, max_sentences=5, max_chars=1400)
    return summary or plain[:1200]


def _page_from_url(
    url: str,
    title: str,
    *,
    stereotype: bool = False,
    snippet: str = "",
) -> dict[str, str]:
    summary = snippet
    if url:
        try:
            summary = _fetch_page_summary(url)
        except Exception as e:
            summary = (snippet or "") + f" (ошибка: {str(e)[:80]})"
    return {
        "title": title,
        "url": url,
        "snippet": snippet,
        "summary": summary,
        "stereotype": stereotype,
    }


def _gather_pages(
    intent: ResearchIntent,
    *,
    max_pages: int = 10,
    progress: ProgressFn | None = None,
) -> tuple[list[dict[str, str]], str, bool]:
    query = intent.query
    total = max(1, min(int(max_pages or 10), 10))
    used_stereo = False
    pages: list[dict[str, str]] = []
    seen_hosts: set[str] = set()

    stereo_limit = min(4, max(1, total // 2 + 1))
    stereotypes = match_stereotypes(query, limit=stereo_limit)
    if stereotypes:
        used_stereo = True
        _report(progress, 0, total, f"Стереотипы: {len(stereotypes)} сайт(ов)…")
        for i, st in enumerate(stereotypes, 1):
            url = resolve_stereotype_url(st, query)
            host = _norm_host(url)
            if host in seen_hosts:
                continue
            seen_hosts.add(host)
            _report(progress, i, total, f"★ {st.title[:48]}…")
            pages.append(_page_from_url(url, st.title, stereotype=True))

    remaining = total - len(pages)
    engine = "stereotypes"
    if remaining > 0:
        _report(progress, len(pages), total, f"Google: «{query[:64]}»…")
        hits, engine = _search_results(query, max_results=remaining + 4)
        for hit in hits:
            if len(pages) >= total:
                break
            url = hit.get("url") or ""
            host = _norm_host(url)
            if host in seen_hosts:
                continue
            seen_hosts.add(host)
            title = hit.get("title") or host or "Страница"
            idx = len(pages) + 1
            _report(progress, idx, total, f"Читаю {idx}/{total}: {title[:52]}…")
            pages.append(
                _page_from_url(
                    url,
                    title,
                    snippet=hit.get("snippet") or "",
                )
            )

    intent.used_stereotypes = used_stereo
    return pages[:total], engine, used_stereo


def _format_sources_block(pages: list[dict[str, str]]) -> str:
    if not pages:
        return ""
    lines = ["", "---", "**Источники:**"]
    n = 0
    for p in pages:
        url = (p.get("url") or "").strip()
        if not url:
            continue
        n += 1
        title = (p.get("title") or _norm_host(url) or f"Источник {n}").strip()
        mark = " ★" if p.get("stereotype") else ""
        lines.append(f"{n}. [{title}{mark}]({url})")
    if n == 0:
        return ""
    return "\n".join(lines)


def _synthesize_digest(
    intent: ResearchIntent,
    pages: list[dict[str, str]],
    *,
    deepseek_key: str = "",
    model: str = "deepseek-chat",
    voice_mode: bool = False,
) -> str:
    query = intent.query
    if not pages:
        return (
            f"По запросу «{query}» не удалось собрать материалы из интернета. "
            "Проверьте сеть, Chromium и файл **Стереотипы.txt** в бессознательном."
        )

    blocks: list[str] = []
    for i, p in enumerate(pages, 1):
        title = p.get("title") or "Без названия"
        tag = " [стереотип]" if p.get("stereotype") else ""
        body = (p.get("summary") or p.get("snippet") or "").strip()
        blocks.append(f"[{i}] {title}{tag}\n{body[:1600]}")

    context = "\n\n".join(blocks)[:28_000]
    key_ok = (deepseek_key or "").strip().startswith("sk-") and len(deepseek_key.strip()) >= 20
    body = ""

    if key_ok:
        try:
            from modules.http_proxy import httpx_client
            from modules.text_sanitize import reply_max_tokens

            sys_prompt = (
                "Ты Jarvis. Собери выжимку по материалам из интернета для Шефа.\n"
                "Правила:\n"
                "- В основном тексте — только факты и выводы, без URL и без «я нашёл».\n"
                "- Не перечисляй названия сайтов в теле ответа — ссылки добавятся отдельно.\n"
                "- Без рассуждений и внутреннего монолога; не пиши от имени Шефа.\n"
                "- Краткость — сестра таланта: без воды; списки — с текстом в каждом пункте.\n"
                + (
                    "2–4 коротких предложения."
                    if voice_mode
                    else "4–8 предложений или короткий маркированный список по сути."
                )
            )
            user = (
                f"Что искали: {query}\n"
                f"Исходная просьба: {intent.raw_user[:400]}\n\n"
                f"Материалы:\n{context}\n\n"
                "Выжимка (без ссылок):"
            )
            with httpx_client(timeout=90.0, proxy=None) as client:
                resp = client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {deepseek_key.strip()}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": (model or "deepseek-chat").strip() or "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": sys_prompt},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.35,
                        "max_tokens": reply_max_tokens(intent.raw_user, cloud=True),
                    },
                )
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"].strip()
                if text:
                    from modules.text_sanitize import polish_assistant_reply

                    body = polish_assistant_reply(
                        text, intent.raw_user, voice_mode=voice_mode
                    )
        except Exception as e:
            try:
                from modules.agent import get_runtime

                get_runtime().log("web.research", f"DeepSeek digest → локально: {e}")
            except Exception:
                pass

    if not body:
        bullets: list[str] = []
        for p in pages[:6]:
            sn = (p.get("summary") or p.get("snippet") or "").strip()
            if not sn:
                continue
            bullets.append(f"• {sn[:260].rstrip('.')}.")
        body = (
            f"**По запросу «{query}»** (просмотрено {len(pages)} страниц):\n\n"
            + ("\n".join(bullets) if bullets else "Данных мало.")
        )

    sources = _format_sources_block(pages)
    return body.strip() + sources


def research_web_query(
    user_text: str,
    *,
    history: list[dict] | None = None,
    max_pages: int = 10,
    deepseek_key: str = "",
    model: str = "deepseek-chat",
    voice_mode: bool = False,
    progress: ProgressFn | None = None,
) -> str:
    intent = refine_research_intent(
        user_text,
        history,
        deepseek_key=deepseek_key,
        model=model,
    )
    if len(intent.query.strip()) < 3:
        return (
            "Задача поиска неясна — уточните, **что именно** найти в интернете "
            "(тема, даты, объект)."
        )

    total = max(1, min(int(max_pages or 10), 10))
    pages, engine, used_stereo = _gather_pages(intent, max_pages=total, progress=progress)
    if not pages:
        return (
            f"По запросу «{intent.query}» ничего не найдено. "
            "Проверьте интернет и install-chromium.bat."
        )

    _report(progress, total, total, "Собираю выжимку…")
    digest = _synthesize_digest(
        intent,
        pages,
        deepseek_key=deepseek_key,
        model=model,
        voice_mode=voice_mode,
    )
    try:
        from modules.agent import get_runtime

        tag = "stereo+" if used_stereo else ""
        get_runtime().last_router_intent = "LOCAL_HELP"
        get_runtime().last_router_engine = f"web_research_{tag}{engine}"
        get_runtime().log("web.research", f"Запрос: «{intent.query[:80]}»")
    except Exception:
        pass
    return digest


def research_web_query_async(
    user_text: str,
    *,
    progress_queue: queue.Queue[tuple[int, int, str]] | None = None,
    history: list[dict] | None = None,
    **kwargs: Any,
) -> str:
    def cb(cur: int, tot: int, msg: str) -> None:
        if progress_queue is not None:
            progress_queue.put((cur, tot, msg))

    return research_web_query(
        user_text,
        history=history,
        progress=cb,
        **kwargs,
    )


def run_research_in_background(
    user_text: str,
    *,
    on_done: Callable[[str], None],
    on_error: Callable[[BaseException], None] | None = None,
    **kwargs: Any,
) -> threading.Thread:
    def worker() -> None:
        try:
            on_done(research_web_query(user_text, **kwargs))
        except Exception as e:
            if on_error:
                on_error(e)

    th = threading.Thread(target=worker, daemon=True, name="jarvis-web-research")
    th.start()
    return th
