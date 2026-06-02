"""
Встроенный браузер Jarvis — headless Chromium через Playwright (бесплатно, в составе Jarvis).

Установка запускается автоматически (как install-chromium.bat): pip playwright + скачивание Chromium.
Прогресс отдаётся в /api/status для полосы на панели индикации.
"""

from __future__ import annotations

import concurrent.futures
import importlib.util
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

_log = logging.getLogger(__name__)

_BROWSER_LOCK = threading.Lock()
_PLAYWRIGHT = None
_BROWSER = None

_INSTALL_LOCK = threading.Lock()
_INSTALL: dict[str, Any] = {
    "phase": "idle",  # idle | checking_internet | installing_playwright | downloading | ready | error | no_internet
    "progress": 0,
    "message": "",
    "error": None,
}
_NO_INTERNET_RETRY_AT = 0.0
_ERROR_RETRY_AT = 0.0
_INSTALL_PROGRESS_AT = 0.0

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="jarvis-chromium",
)

_LAUNCH_OK: bool | None = None
_LAST_VERIFY_AT: float = 0.0
_VERIFY_LOCK = threading.Lock()
_CACHED_EXE_PATH: str | None = None
_INSTALL_THREAD: threading.Thread | None = None

_PROGRESS_RE = re.compile(r"(\d+)\s*%")


def _on_chromium_worker_thread() -> bool:
    return threading.current_thread().name.startswith("jarvis-chromium")


def get_chromium_status(*, force_refresh: bool = False) -> dict[str, Any]:
    """Алиас для совместимости (jarvis_mood и др.)."""
    return chromium_browser_status(force_refresh=force_refresh)


def _playwright_importable() -> bool:
    if importlib.util.find_spec("playwright") is None:
        return False
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def _canonical_ms_playwright_root() -> Path:
    """Каталог браузеров Jarvis (Chromium + Chrome внутри приложения)."""
    from modules.jarvis_browsers import jarvis_browsers_dir

    return jarvis_browsers_dir()


def _ms_playwright_root() -> Path:
    """Каталог для playwright install (всегда канонический, чтобы не ставить в пустой sandbox)."""
    return _canonical_ms_playwright_root()


def _browser_search_roots() -> list[Path]:
    """Все каталоги, где может лежать chromium-* (env + LOCALAPPDATA + кэш)."""
    roots: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        key = str(p).lower()
        if key in seen:
            return
        seen.add(key)
        roots.append(p)

    env = (os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if env:
        add(Path(env))
    add(_canonical_ms_playwright_root())
    add(Path.home() / ".cache" / "ms-playwright")
    return roots


def _find_chromium_executable_in_root(root: Path) -> str | None:
    if not root.is_dir():
        return None
    rels = (
        "chrome-win/chrome.exe",
        "chrome-win64/chrome.exe",
        "chrome-linux/chrome",
        "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    )
    for d in sorted(root.glob("chromium-*"), reverse=True):
        if not d.is_dir():
            continue
        for rel in rels:
            p = d / rel
            if p.is_file():
                return str(p)
        for sub in d.iterdir():
            if not sub.is_dir():
                continue
            for name in ("chrome.exe", "chrome"):
                p = sub / name
                if p.is_file():
                    return str(p)
    return None


def _find_chromium_executable_path() -> str | None:
    """Путь к chrome.exe — обход всех известных корней (env может указывать не туда)."""
    for root in _browser_search_roots():
        found = _find_chromium_executable_in_root(root)
        if found:
            return found
    return None


def _refresh_exe_cache_from_playwright_cli() -> bool:
    """Точный путь из Playwright (только поток установки, не /api/status)."""
    global _CACHED_EXE_PATH
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-c",
                "from playwright.sync_api import sync_playwright\n"
                "p = sync_playwright().start()\n"
                "print(p.chromium.executable_path or '')\n"
                "p.stop()",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env_for_playwright(),
        )
        if r.returncode != 0:
            return False
        path = (r.stdout or "").strip().splitlines()[-1].strip()
        if path and os.path.isfile(path):
            _CACHED_EXE_PATH = path
            return True
    except Exception as e:
        _log.warning("Chromium path resolve: %s", e)
    return False


def _chromium_executable_exists() -> bool:
    """Проверка chrome.exe на диске (без sync_playwright — иначе /api/status зависает)."""
    global _CACHED_EXE_PATH
    if _CACHED_EXE_PATH and os.path.isfile(_CACHED_EXE_PATH):
        return True
    found = _find_chromium_executable_path()
    if found:
        _CACHED_EXE_PATH = found
        return True
    return False


def _is_ready() -> bool:
    return _playwright_importable() and _chromium_executable_exists()


_STATUS_CACHE: dict[str, Any] | None = None
_STATUS_CACHE_AT = 0.0
_STATUS_LOCK = threading.Lock()


def _invalidate_status_cache() -> None:
    global _STATUS_CACHE, _STATUS_CACHE_AT
    with _STATUS_LOCK:
        _STATUS_CACHE = None
        _STATUS_CACHE_AT = 0.0


def _set_install(
    phase: str,
    progress: int,
    message: str,
    *,
    error: str | None = None,
) -> None:
    global _INSTALL_PROGRESS_AT
    with _INSTALL_LOCK:
        prev = int(_INSTALL.get("progress") or 0)
        _INSTALL["phase"] = phase
        _INSTALL["progress"] = max(0, min(100, int(progress)))
        _INSTALL["message"] = message
        _INSTALL["error"] = error
        if int(progress) != prev or phase in (
            "checking_internet",
            "installing_playwright",
            "downloading",
        ):
            _INSTALL_PROGRESS_AT = time.monotonic()
    _invalidate_status_cache()


def _install_snapshot() -> dict[str, Any]:
    with _INSTALL_LOCK:
        return dict(_INSTALL)


def _install_in_progress() -> bool:
    ph = _install_snapshot()["phase"]
    return ph in ("checking_internet", "installing_playwright", "downloading")


def _install_thread_alive() -> bool:
    global _INSTALL_THREAD
    t = _INSTALL_THREAD
    return t is not None and t.is_alive()


def _heal_install_state() -> None:
    """Сброс зависших фаз (ready без chrome.exe, install без потока)."""
    global _INSTALL_THREAD, _INSTALL_PROGRESS_AT
    snap = _install_snapshot()
    ph = str(snap.get("phase") or "idle")
    pw = _playwright_importable()
    exe = _chromium_executable_exists() if pw else False
    now = time.monotonic()

    if ph == "ready" and not (pw and exe):
        with _INSTALL_LOCK:
            _INSTALL["phase"] = "idle"
            _INSTALL["progress"] = 0
            _INSTALL["message"] = ""
            _INSTALL["error"] = None
        _INSTALL_THREAD = None
        return

    if ph in ("checking_internet", "installing_playwright", "downloading"):
        if not _install_thread_alive():
            with _INSTALL_LOCK:
                _INSTALL["phase"] = "idle"
                _INSTALL["progress"] = 0
                _INSTALL["message"] = "Повтор установки Chromium…"
            _INSTALL_THREAD = None
            return
        if _INSTALL_PROGRESS_AT > 0 and (now - _INSTALL_PROGRESS_AT) > 900.0:
            _log.warning("Chromium install stalled >15 min, resetting")
            with _INSTALL_LOCK:
                _INSTALL["phase"] = "idle"
                _INSTALL["progress"] = 0
                _INSTALL["message"] = "Установка прервана — повтор…"
            _INSTALL_THREAD = None


def _subprocess_env_for_playwright() -> dict[str, str]:
    """Прокси + единый каталог браузера (%LOCALAPPDATA%\\ms-playwright)."""
    env = dict(os.environ)
    for key in list(env.keys()):
        if "proxy" not in key.lower():
            continue
        val = (env.get(key) or "").strip().lower()
        if val.startswith(("socks://", "socks4://", "socks5://")):
            env.pop(key, None)
    canon = _canonical_ms_playwright_root()
    canon.mkdir(parents=True, exist_ok=True)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(canon)
    return env


def _pip_install_playwright() -> bool:
    _set_install("installing_playwright", 8, "Jarvis: pip install playwright…")
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "playwright>=1.49.0", "-q"],
        capture_output=True,
        text=True,
        timeout=300,
        env=_subprocess_env_for_playwright(),
    )
    if r.returncode != 0:
        tail = ((r.stderr or "") + (r.stdout or ""))[-400:]
        _set_install(
            "error",
            0,
            "Не удалось установить пакет playwright.",
            error=tail or f"pip exit {r.returncode}",
        )
        return False
    _set_install("installing_playwright", 18, "Playwright установлен.")
    return _playwright_importable()


def _install_playwright_os_deps() -> None:
    """Системные библиотеки для Chromium (Linux; на Windows уже в сборке)."""
    if sys.platform == "win32":
        return
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install-deps", "chromium"],
            capture_output=True,
            text=True,
            timeout=600,
            env=_subprocess_env_for_playwright(),
        )
    except Exception as e:
        _log.warning("playwright install-deps: %s", e)


def _run_playwright_install_chromium(
    on_progress: Callable[[int, str], None],
) -> bool:
    proc = subprocess.Popen(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=_subprocess_env_for_playwright(),
    )
    last_pct = 20
    on_progress(last_pct, "Скачивание Chromium (~180 МБ)…")
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        m = _PROGRESS_RE.search(line)
        if m:
            dl = int(m.group(1))
            last_pct = 20 + int(dl * 0.75)
            on_progress(min(95, last_pct), line[:160])
        elif "Downloading" in line or "Скачивание" in line:
            on_progress(last_pct, line[:160])
    proc.wait(timeout=600)
    if proc.returncode != 0:
        _set_install(
            "error",
            last_pct,
            "Ошибка playwright install chromium.",
            error=f"exit {proc.returncode}",
        )
        return False
    _install_playwright_os_deps()
    return True


def _probe_internet_for_install() -> tuple[bool, str]:
    """Несколько попыток — не путать краткий сбой прокси с отсутствием интернета."""
    from modules.network_env import probe_internet

    last_detail = ""
    for attempt in range(3):
        if attempt:
            time.sleep(1.2 * attempt)
        ok, detail = probe_internet(force=attempt > 0)
        if ok:
            return True, detail
        last_detail = detail
    return False, last_detail


def _run_auto_install() -> None:
    """Полный цикл install-chromium.bat внутри процесса Jarvis."""
    try:
        if _is_ready():
            _set_install("ready", 100, "Chromium готов.")
            return

        _set_install("checking_internet", 2, "Проверка сети для установки Chromium…")
        from modules.network_env import probe_internet

        net_ok, net_detail = _probe_internet_for_install()
        if not net_ok:
            _set_install(
                "no_internet",
                0,
                f"Не удалось скачать Chromium: {net_detail}. "
                "Интернет Windows может работать — Jarvis повторит попытку.",
            )
            return

        if not _playwright_importable():
            if not _pip_install_playwright():
                return

        if _chromium_executable_exists():
            _set_install("ready", 100, "Chromium уже установлен.")
            _invalidate_status_cache()
            return

        _set_install("downloading", 22, "Jarvis скачивает Chromium…")

        def on_dl(pct: int, msg: str) -> None:
            _set_install("downloading", pct, msg)

        if not _run_playwright_install_chromium(on_dl):
            return

        if not _chromium_executable_exists():
            _refresh_exe_cache_from_playwright_cli()

        if _is_ready():
            _set_install("ready", 100, "Chromium готов — fetch_url пробует оба браузера Jarvis.")
            from modules.jarvis_browsers import start_chrome_install_if_needed

            start_chrome_install_if_needed()
            global _LAUNCH_OK
            _LAUNCH_OK = True
        else:
            _set_install(
                "error",
                0,
                "Скачивание завершилось, но chrome.exe не найден.",
                error="browser_missing_after_install",
            )
    except Exception as e:
        _log.exception("Chromium auto-install failed")
        _set_install("error", 0, "Ошибка установки Chromium.", error=str(e)[:300])
    finally:
        _invalidate_status_cache()


def start_auto_install_if_needed(*, force: bool = False) -> bool:
    """
    Запуск фоновой установки (аналог двойного клика install-chromium.bat).
    Возвращает True, если поток установки запущен или уже идёт.
    """
    global _NO_INTERNET_RETRY_AT, _ERROR_RETRY_AT, _INSTALL_THREAD

    _heal_install_state()

    if _is_ready():
        with _INSTALL_LOCK:
            _INSTALL["phase"] = "ready"
            _INSTALL["progress"] = 100
            if not _INSTALL["message"]:
                _INSTALL["message"] = "Chromium готов."
        return False

    if _install_in_progress() or _install_thread_alive():
        return True

    now = time.monotonic()
    snap = _install_snapshot()
    phase = str(snap.get("phase") or "idle")
    if phase == "no_internet":
        if not force and (now - _NO_INTERNET_RETRY_AT) < 45.0:
            return False
        _NO_INTERNET_RETRY_AT = now
    elif phase == "error" and not force:
        if (now - _ERROR_RETRY_AT) < 25.0:
            return False
        _ERROR_RETRY_AT = now

    if _install_thread_alive():
        return True

    def _thread() -> None:
        try:
            _run_auto_install()
        finally:
            _invalidate_status_cache()

    _INSTALL_THREAD = threading.Thread(
        target=_thread,
        daemon=True,
        name="jarvis-chromium-install",
    )
    _INSTALL_THREAD.start()
    return True


def ensure_playwright_browsers_env() -> None:
    from modules.jarvis_browsers import ensure_playwright_browsers_env as _ensure

    _ensure()


def warmup_chromium_dependencies_async() -> None:
    """При старте: headless Chromium + Chrome внутри Jarvis."""
    global _LAUNCH_OK, _CACHED_EXE_PATH
    from modules.jarvis_browsers import warmup_jarvis_browsers_async

    ensure_playwright_browsers_env()
    _CACHED_EXE_PATH = None
    if _chromium_executable_exists():
        _set_install("ready", 100, "Chromium готов.")
        _LAUNCH_OK = True
    else:
        start_auto_install_if_needed(force=True)
    warmup_jarvis_browsers_async()


def ensure_playwright_dependencies(*, install_browser: bool = True) -> dict[str, Any]:
    """Синхронная установка (API / ручной вызов)."""
    if _install_in_progress():
        return chromium_browser_status(force_refresh=True)
    if not _is_ready():
        if install_browser:
            _run_auto_install()
        elif not _playwright_importable():
            _pip_install_playwright()
    return chromium_browser_status(force_refresh=True)


def _verify_launch_sync() -> tuple[bool, str | None]:
    """Реальный запуск headless Chromium (не только наличие chrome.exe на диске)."""
    global _LAUNCH_OK, _LAST_VERIFY_AT

    if not _playwright_importable() or not _chromium_executable_exists():
        _LAUNCH_OK = False
        return False, "Playwright или chrome.exe не найден"

    try:
        ensure_playwright_browsers_env()
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        try:
            browser = _launch_playwright_browser(pw, prefer_system_chrome=False)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto("about:blank", timeout=25_000, wait_until="domcontentloaded")
            page.close()
            ctx.close()
            browser.close()
        finally:
            pw.stop()
        _LAUNCH_OK = True
        _LAST_VERIFY_AT = time.monotonic()
        return True, None
    except Exception as e:
        _LAUNCH_OK = False
        _log.warning("Chromium launch verify failed: %s", e)
        return False, str(e)[:280]


def _verify_launch_cached(*, force: bool = False, max_age: float = 180.0) -> tuple[bool, str | None]:
    global _LAST_VERIFY_AT

    with _VERIFY_LOCK:
        if _LAUNCH_OK is True and not force and (time.monotonic() - _LAST_VERIFY_AT) < max_age:
            return True, None

    if _on_chromium_worker_thread():
        return _verify_launch_sync()

    try:
        return _EXECUTOR.submit(_verify_launch_sync).result(timeout=55.0)
    except concurrent.futures.TimeoutError:
        return False, "Таймаут проверки запуска Chromium (55 с)"
    except Exception as e:
        return False, str(e)[:280]


def chromium_browser_status(*, force_refresh: bool = False) -> dict[str, Any]:
    """Статус для отчёта и API."""
    global _STATUS_CACHE, _STATUS_CACHE_AT, _LAUNCH_OK

    _heal_install_state()

    if not _is_ready() and not _install_in_progress() and not _install_thread_alive():
        snap_phase = str(_install_snapshot().get("phase") or "idle")
        force_kick = snap_phase in ("idle", "error", "no_internet")
        start_auto_install_if_needed(force=force_kick)

    ttl = 0.8 if _install_in_progress() else 12.0
    now = time.monotonic()
    if not force_refresh:
        with _STATUS_LOCK:
            if _STATUS_CACHE is not None and (now - _STATUS_CACHE_AT) < ttl:
                return dict(_STATUS_CACHE)

    from modules.network_env import get_cached_internet, probe_internet

    inst = _install_snapshot()
    pw = _playwright_importable()
    exe = _chromium_executable_exists() if pw else False

    phase = str(inst.get("phase") or "idle")
    in_prog = phase in ("checking_internet", "installing_playwright", "downloading")
    if (
        not in_prog
        and _install_thread_alive()
        and phase in ("idle", "checking_internet")
    ):
        in_prog = True

    launch_verified = False
    launch_error: str | None = None
    if pw and exe and not in_prog:
        launch_verified, launch_error = _verify_launch_cached(
            force=force_refresh,
            max_age=30.0 if force_refresh else 180.0,
        )

    ready = pw and exe and not in_prog and launch_verified
    progress = int(inst.get("progress") or 0)
    inst_msg = str(inst.get("message") or "")

    detail = "Headless Chromium в Jarvis; страницы — лучший ответ из двух браузеров"
    status_label = "На связи"

    if in_prog:
        status_label = f"Загрузка {progress}%"
        detail = inst_msg or "Jarvis устанавливает Chromium…"
    elif phase == "no_internet":
        cached_ok, _ = get_cached_internet()
        sys_net = cached_ok
        if sys_net is None:
            sys_net, _ = probe_internet()
        if sys_net:
            status_label = "Установка Chromium"
            detail = (
                inst_msg
                or "Интернет Windows есть — Jarvis повторит скачивание браузера."
            )
        else:
            status_label = "Нет интернета"
            detail = inst_msg or "Нужен интернет для скачивания Chromium."
    elif phase == "error":
        status_label = "Ошибка"
        detail = inst_msg or str(inst.get("error") or "Установка не удалась")
    elif not pw:
        status_label = "Установка…" if phase not in ("idle", "ready") else "Нет Playwright"
        detail = inst_msg or "Jarvis ставит playwright…"
    elif not exe:
        status_label = (
            f"Загрузка {progress}%"
            if phase == "downloading"
            else "Нужен Chromium"
        )
        detail = (
            inst_msg
            or "Jarvis скачивает Chromium (~180 МБ). Полоса на панели индикации."
        )
    elif pw and exe and launch_verified:
        status_label = "На связи"
        detail = "Готов — headless Chromium для fetch_url / посещения ссылок"
    elif pw and exe and not launch_verified:
        status_label = "Ошибка запуска"
        detail = (
            launch_error
            or "chrome.exe есть, но Playwright не смог запустить браузер. "
            "Запустите scripts/install-chromium.ps1 или перезапустите Jarvis."
        )
    elif phase == "ready" and inst_msg and not exe:
        status_label = "Нужен Chromium"
        detail = "Запускается установка Chromium…"
    elif phase == "ready" and inst_msg:
        detail = inst_msg

    exe_path = _CACHED_EXE_PATH if exe else _find_chromium_executable_path()

    cached_ok, cached_det = get_cached_internet()
    system_internet_ok = cached_ok
    if system_internet_ok is None:
        system_internet_ok, cached_det = probe_internet()

    result = {
        "embedded_in_jarvis": True,
        "playwright_installed": pw,
        "browser_installed": exe,
        "executable_path": exe_path,
        "browsers_dir": str(_canonical_ms_playwright_root()),
        "launch_verified": launch_verified,
        "launch_error": launch_error or inst.get("error"),
        "ready": ready,
        "status_label": status_label,
        "detail": detail,
        "engine": "playwright-chromium",
        "install_phase": phase,
        "install_progress": progress,
        "install_message": inst_msg,
        "install_in_progress": in_prog,
        "install_error": inst.get("error"),
        "system_internet_ok": bool(system_internet_ok),
        "system_internet_detail": str(cached_det or ""),
    }
    with _STATUS_LOCK:
        _STATUS_CACHE = dict(result)
        _STATUS_CACHE_AT = time.monotonic()
    return result


def probe_embedded_chromium() -> tuple[str, str]:
    """ok | warn | err + текст для отчёта «проверка систем»."""
    s = chromium_browser_status()
    if s["ready"]:
        return "ok", s["detail"]
    if s.get("install_in_progress"):
        return "warn", s.get("install_message") or s["detail"]
    if s.get("install_phase") == "no_internet":
        return "warn", s["detail"]
    if s["playwright_installed"]:
        return "warn", s["detail"]
    return "off", s["detail"] or "Jarvis установит Chromium при наличии интернета"


def _launch_playwright_browser(
    playwright,
    *,
    prefer_system_chrome: bool = False,
    windowed: bool = False,
):
    from modules.chromium_stealth import chromium_launch_kwargs

    if windowed:
        return playwright.chromium.launch(
            **chromium_launch_kwargs(windowed=True),
        )

    exe = _find_chromium_executable_path()
    if not exe and not prefer_system_chrome:
        raise RuntimeError(
            "chrome.exe не найден. Запустите install-chromium.bat или дождитесь автоустановки."
        )
    global _CACHED_EXE_PATH
    if exe:
        _CACHED_EXE_PATH = exe

    kw = chromium_launch_kwargs(prefer_system_chrome=prefer_system_chrome)
    if "channel" not in kw and exe:
        kw["executable_path"] = exe
    return playwright.chromium.launch(**kw)


def _get_browser():
    """Один headless Chromium на процесс (ленивый старт)."""
    global _PLAYWRIGHT, _BROWSER
    with _BROWSER_LOCK:
        if _BROWSER is not None:
            return _BROWSER
        from playwright.sync_api import sync_playwright

        prev_browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_canonical_ms_playwright_root())
        try:
            _PLAYWRIGHT = sync_playwright().start()
            _BROWSER = _launch_playwright_browser(_PLAYWRIGHT, prefer_system_chrome=False)
        finally:
            if prev_browsers_path is None:
                os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
            else:
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = prev_browsers_path
        return _BROWSER


def _browse_map_url(
    u: str,
    max_chars: int,
    wait_ms: int | None,
) -> str:
    from modules.jarvis_browsers import browse_page_best

    return browse_page_best(
        u,
        max_chars=max_chars,
        wait_ms=wait_ms,
        prefer_windowed_first=True,
    )


def shutdown_chromium_browser() -> None:
    global _PLAYWRIGHT, _BROWSER, _LAUNCH_OK, _INSTALL_THREAD
    _LAUNCH_OK = None
    _INSTALL_THREAD = None
    with _BROWSER_LOCK:
        if _BROWSER is not None:
            try:
                _BROWSER.close()
            except Exception:
                pass
            _BROWSER = None
        if _PLAYWRIGHT is not None:
            try:
                _PLAYWRIGHT.stop()
            except Exception:
                pass
            _PLAYWRIGHT = None


def _browse_url_sync(
    url: str,
    max_chars: int = 12_000,
    wait_ms: int | None = None,
) -> str:
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return "Ошибка: укажите полный URL (https://…)."

    if not _is_ready():
        start_auto_install_if_needed()
        st = chromium_browser_status(force_refresh=True)
        if not st.get("ready"):
            if st.get("install_in_progress"):
                return (
                    f"Chromium ещё скачивается ({st.get('install_progress', 0)}%). "
                    f"{st.get('install_message') or st['detail']}\n"
                    "Дождитесь готовности на панели индикации."
                )
            return f"Встроенный Chromium не готов: {st['detail']}"

    from modules.jarvis_browsers import browse_page_best
    from modules.page_extract import is_map_heavy_url

    if is_map_heavy_url(u):
        return _browse_map_url(u, max_chars, wait_ms)

    return browse_page_best(u, max_chars=max_chars, wait_ms=wait_ms)


def browse_url_text(url: str, max_chars: int = 12_000, wait_ms: int = 5_000) -> str:
    """Потокобезопасный вызов из FastAPI / Qwen tools."""
    timeout = 90 if "2gis" in (url or "").lower() else 70
    fut = _EXECUTOR.submit(_browse_url_sync, url, max_chars, wait_ms)
    return fut.result(timeout=timeout)
