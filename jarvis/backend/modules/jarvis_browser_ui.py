"""
Управление оконным Chrome/Chromium Jarvis через Playwright.
Клики, ввод, обновление страницы, снимок UI — для инструментов Qwen.
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Каталоги кеша Chromium (cookies / Local Storage не трогаем).
_PROFILE_CACHE_NAMES = frozenset(
    {
        "Cache",
        "Code Cache",
        "GPUCache",
        "GrShaderCache",
        "ShaderCache",
        "GraphiteDawnCache",
        "DawnGraphiteCache",
        "DawnWebGPUCache",
        "blob_storage",
        "BrowserMetrics",
        "optimization_guide_hint_cache",
        "component_crx_cache",
        "extensions_crx_cache",
        "Safe Browsing Network",
        "Safe Browsing",
        "Reporting and NEL",
    }
)
_ROOT_CACHE_NAMES = frozenset(
    {
        "GrShaderCache",
        "ShaderCache",
        "GraphiteDawnCache",
        "BrowserMetrics",
        "BrowserMetrics-spare.pma",
    }
)

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_pw = None
_context = None  # BrowserContext (persistent)
_page = None
_profile_kind: str | None = None


@dataclass
class PageSnapshot:
    url: str = ""
    title: str = ""
    logged_in_hint: bool = False
    auth_visible: bool = False
    phone_form_visible: bool = False
    qr_visible: bool = False
    buttons: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)


def clear_chromium_profile_cache(profile_dir: Path) -> int:
    """
    Очистить дисковый кеш профиля Chrome перед запуском.
    Сессия (Cookies, Local Storage, IndexedDB) сохраняется.
    """
    profile_dir = Path(profile_dir)
    if not profile_dir.is_dir():
        return 0

    removed = 0

    def _rm(path: Path) -> None:
        nonlocal removed
        if not path.exists():
            return
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
            removed += 1
        except Exception as e:
            _log.warning("cache rm %s: %s", path, e)

    for name in _ROOT_CACHE_NAMES:
        _rm(profile_dir / name)

    default = profile_dir / "Default"
    if default.is_dir():
        for child in default.iterdir():
            if child.name in _PROFILE_CACHE_NAMES or child.name.startswith("Cache"):
                _rm(child)
        _rm(default / "Service Worker")

    _log.info("jarvis browser: cache cleared in %s (%s dirs)", profile_dir, removed)
    return removed


def browser_profile_dir() -> Path:
    import os

    base = (os.getenv("LOCALAPPDATA") or "").strip() or str(Path.home())
    d = Path(base) / "Jarvis" / "browser-window-profile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_playwright():
    from modules.jarvis_browsers import ensure_playwright_browsers_env, windowed_chrome_installed

    if not windowed_chrome_installed():
        raise RuntimeError(
            "Chrome Jarvis не установлен. Запустите start.bat или install-google-chrome.bat."
        )
    ensure_playwright_browsers_env()


def is_session_open() -> bool:
    with _lock:
        return _context is not None and _page is not None


def get_page():
    with _lock:
        return _page


def open_window(
    url: str,
    *,
    reuse: bool = True,
    clear_cache: bool = True,
) -> PageSnapshot:
    """Открыть или переиспользовать оконный браузер с сохранением профиля (cookies)."""
    global _pw, _context, _page, _profile_kind
    profile = "default"
    with _lock:
        if reuse and _context is not None and _page is not None and _profile_kind == profile:
            try:
                if url and _page.url != url:
                    _page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                return snapshot_page(_page)
            except Exception as e:
                _log.warning("browser reuse failed: %s", e)
                _close_unlocked()

        _close_unlocked()
        profile_dir = browser_profile_dir()
        if clear_cache:
            clear_chromium_profile_cache(profile_dir)
        _ensure_playwright()
        from playwright.sync_api import sync_playwright

        from modules.chromium_stealth import (
            apply_stealth_to_context,
            browser_context_options,
            chromium_launch_args,
        )
        from modules.jarvis_browsers import find_windowed_chrome_exe

        _pw = sync_playwright().start()
        exe = find_windowed_chrome_exe()
        opts = browser_context_options()
        launch_kw: dict[str, Any] = {
            "user_data_dir": str(profile_dir),
            "headless": False,
            "ignore_default_args": ["--enable-automation"],
            "args": chromium_launch_args(),
            "locale": opts.get("locale", "ru-RU"),
            "timezone_id": opts.get("timezone_id", "Europe/Moscow"),
            "viewport": opts.get("viewport"),
            "user_agent": opts.get("user_agent"),
        }
        if exe:
            launch_kw["executable_path"] = exe
        _context = _pw.chromium.launch_persistent_context(**launch_kw)
        apply_stealth_to_context(_context)
        _page = _context.pages[0] if _context.pages else _context.new_page()
        _page.set_default_timeout(60_000)
        _profile_kind = profile
        if url:
            _page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        return snapshot_page(_page)


def _close_unlocked() -> None:
    global _pw, _context, _page, _profile_kind
    # Persistent context: закрываем только context (все вкладки вместе).
    if _context is not None:
        try:
            _context.close()
        except Exception:
            pass
    if _pw is not None:
        try:
            _pw.stop()
        except Exception:
            pass
    _page = None
    _context = None
    _pw = None
    _profile_kind = None


def close_window() -> None:
    with _lock:
        _close_unlocked()


def clear_window_cache() -> int:
    """Очистить кеш профиля браузера (браузер должен быть закрыт)."""
    with _lock:
        if _context is not None:
            raise RuntimeError("Сначала закройте браузер (browser_window_close)")
        return clear_chromium_profile_cache(browser_profile_dir())


def reload_page() -> PageSnapshot:
    with _lock:
        if _page is None:
            raise RuntimeError("Браузер не открыт")
        _page.reload(wait_until="domcontentloaded", timeout=60_000)
        return snapshot_page(_page)


def goto(url: str) -> PageSnapshot:
    with _lock:
        if _page is None:
            return open_window(url)
        _page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        return snapshot_page(_page)


def snapshot_page(page) -> PageSnapshot:
    snap = PageSnapshot(url=page.url or "", title="")
    try:
        snap.title = page.title() or ""
    except Exception:
        pass
    try:
        snap.logged_in_hint = page.locator("#page-chats").is_visible()
    except Exception:
        snap.logged_in_hint = False
    try:
        snap.auth_visible = page.locator("#auth-pages").is_visible()
    except Exception:
        snap.auth_visible = True
    try:
        snap.phone_form_visible = page.locator(".page-sign.active").count() > 0
    except Exception:
        pass
    try:
        snap.qr_visible = page.locator(".page-signQR.active").count() > 0
    except Exception:
        pass
    try:
        for btn in page.locator("button").all()[:25]:
            t = (btn.inner_text() or "").strip()
            if t:
                snap.buttons.append(t.replace("\n", " ")[:120])
    except Exception:
        pass
    try:
        for h in page.locator("h4, h3, .subtitle").all()[:8]:
            t = (h.inner_text() or "").strip()
            if t:
                snap.headings.append(t[:200])
    except Exception:
        pass
    return snap


def click_text(text: str, *, exact: bool = False) -> bool:
    with _lock:
        if _page is None:
            raise RuntimeError("Браузер не открыт")
        page = _page
    patterns = [text]
    if not exact:
        patterns.extend([text, text[:40]])
    for p in patterns:
        if not p:
            continue
        try:
            if exact:
                page.get_by_text(p, exact=True).first.click(timeout=8000)
            else:
                page.get_by_text(re.compile(re.escape(p[:60]), re.I)).first.click(timeout=8000)
            return True
        except Exception:
            try:
                page.get_by_role("button", name=re.compile(re.escape(p[:60]), re.I)).first.click(
                    timeout=5000
                )
                return True
            except Exception:
                continue
    return False


def click_selector(selector: str) -> bool:
    with _lock:
        if _page is None:
            raise RuntimeError("Браузер не открыт")
        _page.locator(selector).first.click(timeout=8000)
        return True


def type_into(selector: str, text: str, *, clear: bool = True) -> bool:
    with _lock:
        if _page is None:
            raise RuntimeError("Браузер не открыт")
        page = _page
    loc = page.locator(selector).first
    loc.wait_for(state="visible", timeout=10_000)
    loc.click(timeout=3000)
    if clear:
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
    page.keyboard.type(text, delay=25)
    return True


def format_snapshot(snap: PageSnapshot) -> str:
    lines = [
        f"URL: {snap.url}",
        f"Заголовок: {snap.title}",
        f"Вход выполнен (чаты): {'да' if snap.logged_in_hint else 'нет'}",
        f"Экран авторизации: {'да' if snap.auth_visible else 'нет'}",
        f"Форма телефона: {'да' if snap.phone_form_visible else 'нет'}",
        f"Экран QR: {'да' if snap.qr_visible else 'нет'}",
    ]
    if snap.headings:
        lines.append("Заголовки: " + " | ".join(snap.headings[:4]))
    if snap.buttons:
        lines.append("Кнопки: " + "; ".join(snap.buttons[:12]))
    return "\n".join(lines)
