"""
Сеть Jarvis: те же прокси/VPN, что и у Windows (trust_env).
Поиск DuckDuckGo + встроенный headless Chromium (Playwright) для страниц.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

_INTERNET_CACHE: dict = {"ok": None, "detail": "", "at": 0.0}
_WEB_PROBE_CACHE: dict = {"level": None, "detail": "", "at": 0.0}
_INTERNET_CACHE_TTL = 25.0
_WEB_PROBE_CACHE_TTL = 90.0

_PROBE_URLS = (
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://www.msftconnecttest.com/connecttest.txt",
    "http://captive.apple.com/hotspot-detect.html",
)


def _chromium_paths() -> list[Path]:
    local = os.getenv("LOCALAPPDATA", "")
    prog = os.getenv("ProgramFiles", r"C:\Program Files")
    prog86 = os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")
    names = (
        Path(prog) / "Google/Chrome/Application/chrome.exe",
        Path(prog86) / "Google/Chrome/Application/chrome.exe",
        Path(prog) / "Chromium/Application/chrome.exe",
        Path(local) / "Chromium/Application/chrome.exe",
    )
    return [p for p in names if p.is_file()]


def chromium_on_pc() -> dict:
    from modules.chromium_browser import chromium_browser_status
    from modules.system_google_chrome import find_google_chrome_exe, google_chrome_installed

    embedded = chromium_browser_status()
    gchrome = find_google_chrome_exe()
    from modules.jarvis_browsers import jarvis_browsers_dir

    uses = (
        "DuckDuckGo + оба Chrome внутри Jarvis (headless + окно); лучший ответ из двух"
        if embedded.get("ready") and google_chrome_installed()
        else (
            "web_search + Chromium Jarvis (install-chromium.bat)"
            if embedded.get("ready")
            else f"браузеры: {jarvis_browsers_dir()}"
        )
    )
    return {
        "embedded_in_jarvis": bool(embedded.get("ready")),
        "embedded_status": embedded.get("status_label"),
        "embedded_detail": embedded.get("detail"),
        "google_chrome_on_pc": google_chrome_installed(),
        "google_chrome_path": gchrome,
        "chrome_exe_on_pc": bool(gchrome),
        "paths": [gchrome] if gchrome else [],
        "jarvis_uses": uses,
    }


def _probe_single_url(url: str, *, trust_env: bool) -> tuple[bool, str]:
    import httpx

    with httpx.Client(
        timeout=6.0,
        trust_env=trust_env,
        follow_redirects=True,
    ) as client:
        r = client.get(url)
        if r.status_code in (200, 204):
            label = "прокси Windows" if trust_env else "напрямую"
            return True, f"Интернет OK ({label}, HTTP {r.status_code})"
        return False, f"HTTP {r.status_code} для {url[:40]}"


def _probe_url(trust_env: bool) -> tuple[bool, str]:
    last_err = ""
    for url in _PROBE_URLS:
        try:
            return _probe_single_url(url, trust_env=trust_env)
        except Exception as e:
            last_err = str(e)[:120]
    return False, last_err or "нет ответа"


def _set_internet_cache(ok: bool, detail: str) -> None:
    _INTERNET_CACHE["ok"] = ok
    _INTERNET_CACHE["detail"] = detail
    _INTERNET_CACHE["at"] = time.monotonic()


def get_cached_internet() -> tuple[bool | None, str]:
    """Последний результат probe_internet (может быть None, если ещё не проверяли)."""
    if _INTERNET_CACHE["ok"] is None:
        return None, ""
    age = time.monotonic() - float(_INTERNET_CACHE["at"] or 0)
    if age > _INTERNET_CACHE_TTL * 3:
        return None, ""
    return bool(_INTERNET_CACHE["ok"]), str(_INTERNET_CACHE["detail"] or "")


def probe_internet(*, force: bool = False) -> tuple[bool, str]:
    """
    Проверка выхода в интернет.
    Сначала без прокси (битый SOCKS в env не ломает результат), затем с trust_env.
    """
    now = time.monotonic()
    if (
        not force
        and _INTERNET_CACHE["ok"] is not None
        and (now - float(_INTERNET_CACHE["at"] or 0)) < _INTERNET_CACHE_TTL
    ):
        return bool(_INTERNET_CACHE["ok"]), str(_INTERNET_CACHE["detail"] or "")

    errors: list[str] = []
    for trust_env in (False, True):
        try:
            ok, detail = _probe_url(trust_env)
            if ok:
                _set_internet_cache(True, detail)
                return True, detail
            errors.append(detail)
        except Exception as e:
            err = str(e)[:100]
            errors.append(err)
            if "proxy" not in err.lower() and "scheme" not in err.lower():
                break

    detail = "; ".join(errors)[:160] or "нет соединения"
    _set_internet_cache(False, detail)
    return False, detail


def get_network_summary(*, include_web_probe: bool = True) -> dict:
    net_ok, net_detail = probe_internet()

    web_lv, web_detail = "ok", "не проверялся"
    web_ok = net_ok
    if include_web_probe:
        now = time.monotonic()
        if (
            _WEB_PROBE_CACHE["level"] is not None
            and (now - float(_WEB_PROBE_CACHE["at"] or 0)) < _WEB_PROBE_CACHE_TTL
        ):
            web_lv = str(_WEB_PROBE_CACHE["level"])
            web_detail = str(_WEB_PROBE_CACHE["detail"])
        else:
            from modules.web_search import probe_duckduckgo_search

            web_lv, web_detail = probe_duckduckgo_search()
            _WEB_PROBE_CACHE["level"] = web_lv
            _WEB_PROBE_CACHE["detail"] = web_detail
            _WEB_PROBE_CACHE["at"] = now
        web_ok = web_lv == "ok"

    chrome = chromium_on_pc()
    return {
        "internet_ok": net_ok,
        "internet_detail": net_detail,
        "web_search_ok": web_ok,
        "web_search_detail": web_detail,
        "uses_system_proxy": True,
        "chromium": chrome,
        # «Готов» = интернет Windows, не «Chromium уже скачан»
        "ready": net_ok,
    }


def internet_status_payload() -> dict:
    """Лёгкий блок для /api/status — без DuckDuckGo и без лишнего chromium."""
    net_ok, net_detail = probe_internet()
    return {
        "internet_ok": net_ok,
        "internet_detail": net_detail,
    }
