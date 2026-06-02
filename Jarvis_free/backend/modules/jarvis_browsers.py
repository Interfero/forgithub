"""
Два браузера внутри Jarvis (Playwright, один каталог %LOCALAPPDATA%\\Jarvis\\browsers):

- chromium-* — headless Chromium (фон, быстрые страницы);
- chrome-*   — Google Chrome (окно «как у человека», UI Jarvis, 2ГИС).

Не используем Chrome/Edge по умолчанию в Windows.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

_INSTALL_LOCK = threading.Lock()
_CHROME_INSTALL: dict[str, Any] = {
    "phase": "idle",
    "message": "",
    "error": None,
}
_CHROME_INSTALL_THREAD: threading.Thread | None = None
_PROGRESS_RE = re.compile(r"(\d+)\s*%")


def jarvis_browsers_dir() -> Path:
    """Единый корень браузеров Jarvis (PLAYWRIGHT_BROWSERS_PATH), общий для Pro и Free."""
    from modules.app_paths import shared_browsers_dir

    return shared_browsers_dir()


def jarvis_chrome_profile_dir() -> Path:
    """Отдельный профиль Chrome для интерфейса Jarvis (не системный Chrome пользователя)."""
    base = (os.environ.get("LOCALAPPDATA") or "").strip() or str(Path.home())
    d = Path(base) / "Jarvis" / "chrome-ui-profile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_playwright_browsers_env() -> None:
    root = jarvis_browsers_dir()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(root)


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        key = str(p).lower()
        if key in seen:
            return
        seen.add(key)
        roots.append(p)

    add(jarvis_browsers_dir())
    env = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if env:
        add(Path(env))
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        add(Path(local) / "ms-playwright")
    return roots


_EXTRA_REL_PATHS: dict[str, tuple[str, ...]] = {
    "chromium_headless_shell": (
        "chrome-headless-shell-win64/chrome-headless-shell.exe",
        "chrome-headless-shell-linux64/chrome-headless-shell",
    ),
}


def _find_exe_in_prefix(root: Path, prefix: str) -> str | None:
    if not root.is_dir():
        return None
    win_rels = ("chrome-win64/chrome.exe", "chrome-win/chrome.exe")
    unix_rels = ("chrome-linux/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium")
    rels = list(win_rels if sys.platform == "win32" else unix_rels)
    rels.extend(_EXTRA_REL_PATHS.get(prefix, ()))
    for d in sorted(root.glob(f"{prefix}-*"), reverse=True):
        if not d.is_dir():
            continue
        for rel in rels:
            p = d / rel
            if p.is_file():
                return str(p)
        for sub in d.iterdir():
            if not sub.is_dir():
                continue
            for name in ("chrome.exe", "chrome-headless-shell.exe", "chrome"):
                p = sub / name
                if p.is_file():
                    return str(p)
            for sub2 in sub.iterdir():
                if not sub2.is_dir():
                    continue
                for name in ("chrome.exe", "chrome-headless-shell.exe"):
                    p = sub2 / name
                    if p.is_file() and "proxy" not in name:
                        return str(p)
    return None


def _jarvis_root_only() -> Path:
    return jarvis_browsers_dir()


def find_headless_chromium_exe() -> str | None:
    """Headless shell или chromium — только каталог Jarvis."""
    root = _jarvis_root_only()
    found = _find_exe_in_prefix(root, "chromium_headless_shell")
    if found:
        return found
    return _find_exe_in_prefix(root, "chromium")


def find_windowed_chrome_exe() -> str | None:
    """
    Оконный браузер внутри Jarvis.
    Playwright на Windows не кладёт отдельный google-chrome-* в папку,
    поэтому используем chrome.exe из chromium-* (тот же движок, headless=False).
    """
    root = _jarvis_root_only()
    found = _find_exe_in_prefix(root, "chrome")
    if found:
        return found
    return _find_exe_in_prefix(root, "chromium")


def headless_chromium_installed() -> bool:
    return find_headless_chromium_exe() is not None


def windowed_chrome_installed() -> bool:
    return find_windowed_chrome_exe() is not None


def both_browsers_ready() -> bool:
    return headless_chromium_installed() and windowed_chrome_installed()


def _subprocess_env() -> dict[str, str]:
    ensure_playwright_browsers_env()
    env = dict(os.environ)
    for key in list(env.keys()):
        if "proxy" not in key.lower():
            continue
        val = (env.get(key) or "").strip().lower()
        if val.startswith(("socks://", "socks4://", "socks5://")):
            env.pop(key, None)
    return env


def _playwright_importable() -> bool:
    import importlib.util

    if importlib.util.find_spec("playwright") is None:
        return False
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def _pip_install_playwright() -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright>=1.49.0", "-q"],
        capture_output=True,
        text=True,
        timeout=300,
        env=_subprocess_env(),
    )
    return r.returncode == 0 and _playwright_importable()


def _run_playwright_install(
    browser: str,
    on_line: Callable[[str], None] | None = None,
    *,
    force: bool = False,
) -> bool:
    args = [sys.executable, "-m", "playwright", "install"]
    if force:
        args.append("--force")
    args.append(browser)
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=_subprocess_env(),
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if line and on_line:
            on_line(line)
    proc.wait(timeout=900)
    return proc.returncode == 0


def _set_chrome_install(phase: str, message: str, *, error: str | None = None) -> None:
    with _INSTALL_LOCK:
        _CHROME_INSTALL["phase"] = phase
        _CHROME_INSTALL["message"] = message
        _CHROME_INSTALL["error"] = error


def install_windowed_chrome(
    *,
    on_message: Callable[[str], None] | None = None,
    force: bool = False,
) -> tuple[bool, str]:
    """
    Оконный браузер в Jarvis/browsers.
    На Windows `playwright install chrome` часто не качает файлы (видит системный Chrome),
    поэтому ставим chromium --force и используем chrome.exe оттуда.
    """
    if windowed_chrome_installed() and not force:
        _set_chrome_install("ready", "Chrome (окно) в составе Jarvis.")
        return True, find_windowed_chrome_exe() or "OK"

    _set_chrome_install("installing", "Jarvis: браузер для оконного режима…")
    if not _playwright_importable() and not _pip_install_playwright():
        _set_chrome_install("error", "Не удалось установить playwright.", error="pip")
        return False, _CHROME_INSTALL["message"]

    def _line(s: str) -> None:
        if on_message:
            on_message(s)

    if not headless_chromium_installed():
        _line("Скачивание Chromium в Jarvis…")
        _run_playwright_install("chromium", on_line=_line, force=force)
    if not headless_chromium_installed():
        _run_playwright_install("chromium", on_line=_line, force=True)

    _line("Headless shell…")
    _run_playwright_install("chromium-headless-shell", on_line=_line, force=force)

    if windowed_chrome_installed():
        exe = find_windowed_chrome_exe()
        _set_chrome_install(
            "ready",
            f"Браузер Jarvis (окно) готов — {exe or 'chrome.exe'}.",
        )
        return True, exe or "OK"

    _set_chrome_install(
        "error",
        "Браузер не найден в Jarvis/browsers. Запустите install-browsers.bat или restart.bat.",
        error="missing_exe",
    )
    return False, _CHROME_INSTALL["message"]


def install_headless_chromium(
    *,
    on_message: Callable[[str], None] | None = None,
    force: bool = False,
) -> bool:
    if headless_chromium_installed() and not force:
        return True
    if not _playwright_importable() and not _pip_install_playwright():
        return False

    def _line(s: str) -> None:
        if on_message:
            on_message(s)

    ok = _run_playwright_install("chromium", on_line=_line, force=force)
    _run_playwright_install("chromium-headless-shell", on_line=_line, force=force)
    return ok and headless_chromium_installed()


def install_jarvis_browsers(
    *,
    on_message: Callable[[str], None] | None = None,
    force: bool = False,
) -> tuple[bool, bool]:
    """Оба режима в каталог Jarvis. Возвращает (headless_ok, windowed_ok)."""
    ch_ok = install_headless_chromium(on_message=on_message, force=force)
    chrome_ok, _ = install_windowed_chrome(on_message=on_message, force=force)
    return ch_ok, chrome_ok


def repair_jarvis_browsers_force() -> tuple[bool, bool]:
    """Переустановка браузеров в Jarvis (--force)."""
    _set_chrome_install("installing", "Переустановка браузеров Jarvis…")
    return install_jarvis_browsers(force=True)


def _chrome_install_snapshot() -> dict[str, Any]:
    with _INSTALL_LOCK:
        return dict(_CHROME_INSTALL)


def google_chrome_status() -> dict[str, Any]:
    exe = find_windowed_chrome_exe()
    snap = _chrome_install_snapshot()
    phase = str(snap.get("phase") or "idle")
    installed = exe is not None
    in_prog = phase == "installing"
    if installed:
        phase = "ready"
    detail = (
        f"Внутри Jarvis: {jarvis_browsers_dir()} · оконный режим и UI (Chromium/Chrome)."
        if installed
        else "Jarvis скачает браузеры в свою папку (restart.bat / install-browsers.bat)."
    )
    status_label = "На связи" if installed else "Установка…" if in_prog else "Нужен браузер"
    if in_prog:
        detail = str(snap.get("message") or detail)
    elif not installed and phase == "error":
        detail = str(snap.get("message") or snap.get("error") or detail)
    return {
        "required_on_windows": True,
        "embedded_in_jarvis": True,
        "installed": installed,
        "ready": installed,
        "executable_path": exe,
        "browsers_dir": str(jarvis_browsers_dir()),
        "status_label": status_label,
        "detail": detail,
        "install_phase": phase,
        "install_message": str(snap.get("message") or ""),
        "install_in_progress": in_prog,
        "install_error": snap.get("error"),
        "windowed_engine": "jarvis-chrome",
    }


def start_chrome_install_if_needed(*, force: bool = False) -> bool:
    global _CHROME_INSTALL_THREAD
    if windowed_chrome_installed():
        _set_chrome_install("ready", "Chrome в составе Jarvis.")
        return False
    if _CHROME_INSTALL_THREAD is not None and _CHROME_INSTALL_THREAD.is_alive():
        return True
    snap = _chrome_install_snapshot()
    if snap.get("phase") == "error" and not force:
        force = True

    def _thread() -> None:
        try:
            install_windowed_chrome(force=force or snap.get("phase") == "error")
        except Exception as e:
            _log.exception("Jarvis chrome install")
            _set_chrome_install("error", str(e)[:200], error="exception")

    _CHROME_INSTALL_THREAD = threading.Thread(
        target=_thread,
        daemon=True,
        name="jarvis-chrome-install",
    )
    _CHROME_INSTALL_THREAD.start()
    return True


def warmup_jarvis_browsers_async() -> None:
    """Фон: chromium + chrome в Jarvis/browsers."""

    def _work() -> None:
        try:
            from modules.network_env import probe_internet

            ok, _ = probe_internet()
            if not ok:
                _set_chrome_install("idle", "Ждём интернет для скачивания браузеров…")
                return
            install_jarvis_browsers(force=False)
            from modules.jarvis_free_updates import maybe_run_free_updates_async

            maybe_run_free_updates_async(force=False)
        except Exception as e:
            _log.warning("warmup_jarvis_browsers: %s", e)

    threading.Thread(target=_work, daemon=True, name="jarvis-browsers-warmup").start()


def warmup_jarvis_browsers_repair_async() -> None:
    """Принудительная переустановка (после ошибки «chrome.exe не найден»)."""

    def _work() -> None:
        try:
            repair_jarvis_browsers_force()
        except Exception as e:
            _log.warning("repair browsers: %s", e)

    threading.Thread(target=_work, daemon=True, name="jarvis-browsers-repair").start()


def open_jarvis_ui_in_chrome(url: str | None = None, *, fullscreen: bool = False) -> tuple[bool, str]:
    """
    Открыть интерфейс Jarvis во встроенном Chrome (не браузер по умолчанию Windows).
    """
    exe = find_windowed_chrome_exe()
    if not exe:
        return False, "Google Chrome Jarvis не установлен — дождитесь start.bat или install-google-chrome.bat."

    host = os.getenv("JARVIS_HOST", "127.0.0.1")
    port = os.getenv("JARVIS_PORT", "8000")
    target = (url or "").strip() or f"http://{host}:{port}/"
    profile = jarvis_chrome_profile_dir()

    args = [
        exe,
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--lang=ru",
    ]
    if fullscreen:
        args.append("--start-fullscreen")
        args.append(f"--app={target}")
    else:
        args.append(target)
    try:
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return True, target
    except Exception as e:
        return False, str(e)[:200]


def open_jarvis_game_in_chrome() -> tuple[bool, str]:
    """2D-игра Jarvis: /game во встроенном Chrome, полный экран."""
    host = os.getenv("JARVIS_HOST", "127.0.0.1")
    port = os.getenv("JARVIS_PORT", "8000")
    target = f"http://{host}:{port}/game"
    return open_jarvis_ui_in_chrome(target, fullscreen=True)


# --- совместимость со старым system_google_chrome ---

def find_google_chrome_exe() -> str | None:
    return find_windowed_chrome_exe()


def google_chrome_installed() -> bool:
    return windowed_chrome_installed()


def install_google_chrome_windows(*, silent: bool = True) -> tuple[bool, str]:
    del silent
    return install_windowed_chrome()


def start_auto_install_if_needed(*, force: bool = False) -> bool:
    return start_chrome_install_if_needed(force=force)


def warmup_google_chrome_async() -> None:
    start_chrome_install_if_needed(force=False)


@dataclass
class _BrowseHit:
    body: str
    title: str
    final_url: str
    engine_label: str
    windowed: bool
    score: int


def _score_browse(body: str, raw_check: str) -> int:
    from modules.page_extract import is_2gis_browser_wall

    if is_2gis_browser_wall(body) or is_2gis_browser_wall(raw_check):
        return -1
    text = (body or "").strip()
    if len(text) < 40:
        return len(text) - 80
    return len(text)


def browse_page_best(
    url: str,
    *,
    max_chars: int = 12_000,
    wait_ms: int | None = None,
    prefer_windowed_first: bool = False,
) -> str:
    """
    Пробует headless Chromium и Chrome (окно/headless), возвращает лучший текст.
    """
    from playwright.sync_api import sync_playwright

    from modules.chromium_stealth import (
        apply_stealth_to_context,
        browser_context_options,
        chromium_launch_args,
    )
    from modules.page_extract import (
        browse_wait_ms,
        extract_page_text,
        is_map_heavy_url,
        message_for_2gis_wall,
        sanitize_chat_text,
        scroll_2gis_catalog,
        try_dismiss_2gis_browser_wall,
    )

    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return "Ошибка: укажите полный URL (https://…)."

    if not headless_chromium_installed():
        from modules.chromium_browser import start_auto_install_if_needed, chromium_browser_status

        start_auto_install_if_needed()
        st = chromium_browser_status(force_refresh=True)
        if st.get("install_in_progress"):
            return (
                f"Браузеры Jarvis ещё скачиваются ({st.get('install_progress', 0)}%). "
                f"{st.get('install_message') or st.get('detail', '')}"
            )
        return "Headless Chromium Jarvis не готов — дождитесь установки на панели."

    if not windowed_chrome_installed():
        start_chrome_install_if_needed()

    map_heavy = is_map_heavy_url(u)
    attempts: list[tuple[str, bool, bool]] = []
    # (label, windowed, use_chrome_branded_exe)
    if map_heavy or prefer_windowed_first:
        attempts.extend(
            [
                ("Chrome Jarvis (окно)", True, True),
                ("Chromium Jarvis (headless)", False, False),
                ("Chrome Jarvis (headless)", False, True),
            ]
        )
    else:
        attempts.extend(
            [
                ("Chromium Jarvis (headless)", False, False),
                ("Chrome Jarvis (headless)", False, True),
                ("Chrome Jarvis (окно)", True, True),
            ]
        )

    best: _BrowseHit | None = None
    last_body = ""
    pw = sync_playwright().start()
    try:
        for label, windowed, chrome_exe in attempts:
            if chrome_exe and not windowed_chrome_installed():
                continue
            if not chrome_exe and not headless_chromium_installed():
                continue

            browser = None
            context = None
            page = None
            try:
                ensure_playwright_browsers_env()
                exe = (
                    find_windowed_chrome_exe()
                    if chrome_exe
                    else find_headless_chromium_exe()
                )
                if not exe:
                    continue
                browser = pw.chromium.launch(
                    headless=not windowed,
                    executable_path=exe,
                    ignore_default_args=["--enable-automation"],
                    args=chromium_launch_args(),
                )
                context = browser.new_context(**browser_context_options())
                apply_stealth_to_context(context)
                page = context.new_page()
                nav_timeout = 45_000 if map_heavy else 28_000
                page.set_default_timeout(nav_timeout)
                page.goto(u, wait_until="domcontentloaded", timeout=nav_timeout)
                if map_heavy:
                    try:
                        page.wait_for_load_state("networkidle", timeout=12_000)
                    except Exception:
                        pass
                try_dismiss_2gis_browser_wall(page)
                effective_wait = wait_ms if wait_ms is not None else browse_wait_ms(u)
                if effective_wait > 0:
                    page.wait_for_timeout(min(effective_wait, 14_000))
                try_dismiss_2gis_browser_wall(page)
                if map_heavy:
                    scroll_2gis_catalog(page)
                body, title = extract_page_text(page, u, max_chars=max_chars)
                final = page.url
                last_body = body
                raw_check = sanitize_chat_text((page.inner_text("body") or "")[:3000])
                score = _score_browse(body, raw_check)
                if windowed and score > 0:
                    score += 200
                hit = _BrowseHit(
                    body=body,
                    title=title or "",
                    final_url=final,
                    engine_label=label,
                    windowed=windowed,
                    score=score,
                )
                if best is None or hit.score > best.score:
                    best = hit
                if map_heavy:
                    if hit.score > 400:
                        break
                elif hit.score >= 180:
                    break
            except Exception as e:
                _log.warning("browse %s: %s", label, e)
            finally:
                for obj in (page, context, browser):
                    if obj is not None:
                        try:
                            obj.close()
                        except Exception:
                            pass
    finally:
        try:
            pw.stop()
        except Exception:
            pass

    if best and best.score >= 0 and best.body:
        mode = "окно" if best.windowed else "headless"
        head = f"**Браузер Jarvis ({best.engine_label})**\nURL: {best.final_url}\n"
        if best.title:
            head += f"Заголовок: {best.title}\n\n"
        note = (
            f"_Лучший результат из встроенных браузеров Jarvis ({mode})._"
            if len(attempts) > 1
            else f"_Страница открыта ({mode})._"
        )
        return head + best.body + f"\n\n{note}"

    if last_body:
        return f"**По ссылке** {u}\n\n{last_body}"
    if map_heavy:
        return message_for_2gis_wall(u)
    from modules.chromium_browser import chromium_browser_status

    st = chromium_browser_status(force_refresh=True)
    hint = st.get("detail") or ""
    if st.get("launch_error"):
        hint = str(st["launch_error"])
    if not st.get("ready"):
        return (
            "Не удалось открыть страницу во встроенном браузере Jarvis.\n\n"
            f"**Статус:** {hint}\n\n"
            "Браузер нужен **только для ссылок** в чате (не для «привет» и не для отчёта Авито). "
            "Проверьте чип «Браузер Jarvis» на панели или запустите "
            "`scripts/install-chromium.ps1` из папки Jarvis Free."
        )
    return (
        "Не удалось получить текст страницы ни через Chromium, ни через Chrome Jarvis. "
        "Проверьте ссылку или откройте её вручную для сравнения."
    )
