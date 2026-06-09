"""
Стереотипы — приоритетные сайты для веб-поиска Jarvis.

Файл: backend/data/memory/unconscious/Стерeотипы.txt
Не попадает в текст промпта — только web_research подбирает сайты по ключам.
Формат строки:
  ключ1, ключ2 | Название | https://site/.../{query}
  ключ1, ключ2 | Название | https://site/...   (без {query} — открыть как есть или site: поиск)
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, urlparse

from modules.memory_store import (
    STEREOTYPES_FILENAME,
    STEREOTYPES_FILENAME_ALT,
    UNCONSCIOUS_DIR,
    _ensure_dirs,
)

_STEREOTYPES_ALT = STEREOTYPES_FILENAME_ALT

_LINE_RE = re.compile(
    r"^(?P<keys>[^|]+)\|\s*(?P<title>[^|]+)\|\s*(?P<url>https?://\S+)\s*$",
    re.I,
)
_URL_ONLY_RE = re.compile(r"^(https?://\S+)\s*$", re.I)
_COMMENT_RE = re.compile(r"^\s*#")

_cache_lock = threading.Lock()
_cache_mtime: float = 0.0
_cache_items: list["StereotypeResource"] = []


@dataclass(frozen=True)
class StereotypeResource:
    title: str
    url_template: str
    keywords: tuple[str, ...]
    line_no: int


@dataclass
class ResearchIntent:
    """Что именно ищем в интернете."""

    query: str
    raw_user: str
    topic: str
    used_stereotypes: bool = False


def _stereotypes_bundle_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / STEREOTYPES_FILENAME
    )


def stereotypes_file_path() -> Path:
    _ensure_dirs()
    primary = UNCONSCIOUS_DIR / STEREOTYPES_FILENAME
    if primary.is_file():
        return primary
    alt = UNCONSCIOUS_DIR / _STEREOTYPES_ALT
    if alt.is_file():
        return alt
    return primary


def ensure_default_stereotypes_file() -> Path:
    """Создать Стерeотипы.txt в бессознательном, если файла нет."""
    _ensure_dirs()
    path = UNCONSCIOUS_DIR / STEREOTYPES_FILENAME
    if path.is_file():
        _dedupe_stereotypes_file(path)
        _merge_bundled_stereotypes(path)
        return path
    bundled = _stereotypes_bundle_path()
    if bundled.is_file():
        path.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        path.write_text(_default_stereotypes_content(), encoding="utf-8")
    return path


def _default_stereotypes_content() -> str:
    bundled = _stereotypes_bundle_path()
    if bundled.is_file():
        return bundled.read_text(encoding="utf-8")
    return "# Стерeотипы Jarvis\n"


def _merge_bundled_stereotypes(path: Path) -> None:
    """Дописать в файл строки из bundled-шаблона (по URL), не затирая свои правки."""
    bundled = _stereotypes_bundle_path()
    if not bundled.is_file() or not path.is_file():
        return
    try:
        if path.resolve() == bundled.resolve():
            return
        current = path.read_text(encoding="utf-8")
        bundled_text = bundled.read_text(encoding="utf-8")
    except Exception:
        return
    have_urls = {m.group("url").strip().lower() for m in _LINE_RE.finditer(current)}
    additions: list[str] = []
    for raw in bundled_text.splitlines():
        line = raw.strip()
        if not line or _COMMENT_RE.match(line):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        url = m.group("url").strip().lower()
        if url not in have_urls:
            additions.append(line)
            have_urls.add(url)
    if additions:
        sep = "" if current.endswith("\n") else "\n"
        path.write_text(current + sep + "\n".join(additions) + "\n", encoding="utf-8")


def _parse_stereotypes_text(text: str) -> list[StereotypeResource]:
    items: list[StereotypeResource] = []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or _COMMENT_RE.match(line):
            continue
        m = _LINE_RE.match(line)
        if m:
            keys = tuple(
                k.strip().lower()
                for k in m.group("keys").split(",")
                if k.strip() and len(k.strip()) >= 2
            )
            if not keys:
                continue
            items.append(
                StereotypeResource(
                    title=m.group("title").strip(),
                    url_template=m.group("url").strip(),
                    keywords=keys,
                    line_no=i,
                )
            )
            continue
        um = _URL_ONLY_RE.match(line)
        if um:
            url = um.group(1).strip()
            host = (urlparse(url).netloc or "site").lower().removeprefix("www.")
            items.append(
                StereotypeResource(
                    title=host,
                    url_template=url,
                    keywords=(host.split(".")[0],),
                    line_no=i,
                )
            )
    return items


def load_stereotypes(*, force: bool = False) -> list[StereotypeResource]:
    global _cache_mtime, _cache_items
    ensure_default_stereotypes_file()
    path = stereotypes_file_path()
    if not path.is_file():
        return []
    mtime = path.stat().st_mtime
    with _cache_lock:
        if not force and mtime == _cache_mtime and _cache_items:
            return list(_cache_items)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = path.read_text(encoding="utf-8", errors="replace")
        _cache_items = _parse_stereotypes_text(text)
        _cache_mtime = mtime
        return list(_cache_items)


def _dedupe_stereotypes_file(path: Path) -> None:
    """Убрать дубликаты строк по URL (после сбоев merge)."""
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return
    seen: set[str] = set()
    out: list[str] = []
    changed = False
    for raw in text.splitlines():
        line = raw.rstrip()
        m = (
            _LINE_RE.match(line.strip())
            if line.strip() and not _COMMENT_RE.match(line.strip())
            else None
        )
        if m:
            url = m.group("url").strip().lower()
            if url in seen:
                changed = True
                continue
            seen.add(url)
        out.append(raw)
    if changed:
        path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def _tokenize_query(query: str) -> set[str]:
    words = re.findall(r"[a-z0-9а-яё]{3,}", (query or "").lower().replace("ё", "е"))
    stop = {
        "найди",
        "найти",
        "поиск",
        "интернет",
        "интернете",
        "google",
        "гугл",
        "загугли",
        "погугли",
        "что",
        "как",
        "это",
        "про",
        "для",
        "или",
        "the",
        "and",
        "игра",
        "игре",
        "игры",
        "game",
    }
    tokens = {w for w in words if w not in stop}
    return _expand_tokens_translit(tokens)


def _expand_tokens_translit(tokens: set[str]) -> set[str]:
    """Кириллица ↔ латиница для стереотипов (игры, Steam)."""
    try:
        from modules.user_preferences import expand_alias_variants, name_match_score
    except Exception:
        return tokens

    out = set(tokens)
    for tok in list(tokens):
        for variant in expand_alias_variants(tok):
            vk = variant.lower().replace("ё", "е")
            if len(vk) >= 3:
                out.add(vk)
        for group_word in ("helldivers", "хелдайверс", "steam", "стим", "helldiver"):
            if name_match_score(tok, group_word) >= 0.88:
                out.update(
                    {
                        "helldivers",
                        "helldivers2",
                        "helldiver",
                        "хелдайверс",
                        "хелдайвер",
                        "steam",
                        "steampowered",
                        "стим",
                        "игра",
                        "игры",
                        "game",
                    }
                )
    return out


def match_stereotypes(query: str, *, limit: int = 4) -> list[StereotypeResource]:
    """Подобрать стереотипы по ключевым словам запроса."""
    items = load_stereotypes()
    if not items:
        return []

    tokens = _tokenize_query(query)
    if not tokens:
        return []

    scored: list[tuple[int, int, StereotypeResource]] = []
    for item in items:
        score = 0
        for kw in item.keywords:
            kw_n = kw.lower().replace("ё", "е")
            if kw_n in tokens:
                score += 3
            elif any(kw_n in t or t in kw_n for t in tokens):
                score += 1
        if score > 0:
            scored.append((score, -item.line_no, item))

    scored.sort(key=lambda x: (-x[0], x[1]))
    out: list[StereotypeResource] = []
    seen_hosts: set[str] = set()
    for _, _, item in scored:
        host = (urlparse(item.url_template).netloc or "").lower()
        if host in seen_hosts:
            continue
        seen_hosts.add(host)
        out.append(item)
        if len(out) >= max(1, limit):
            break
    return out


def resolve_stereotype_url(item: StereotypeResource, query: str) -> str:
    q = (query or "").strip()
    tpl = item.url_template
    if "{query}" in tpl:
        return tpl.replace("{query}", quote_plus(q))
    if q and "?" not in tpl and tpl.rstrip("/").count("/") <= 3:
        return f"{tpl.rstrip('/')}/?s={quote_plus(q)}"
    return tpl


def stereotypes_prompt_hint(*, max_items: int = 8) -> str:
    """Не используется в системном промпте — стереотипы подключаются только в web_research."""
    del max_items
    return ""


def stereotypes_status() -> dict:
    path = ensure_default_stereotypes_file()
    items = load_stereotypes(force=True)
    return {
        "path": str(path),
        "count": len(items),
        "ready": len(items) > 0,
        "message": f"Стерeотипов: {len(items)}" if items else "Файл пуст — добавьте сайты",
    }
