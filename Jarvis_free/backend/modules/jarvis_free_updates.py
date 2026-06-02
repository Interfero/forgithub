"""
Автообновление бесплатных компонентов Jarvis (pip + браузеры Playwright).
Платные API (DeepSeek, OpenAI…) не трогаем.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_UPDATE_LOCK = threading.Lock()
_LAST_RUN_AT = 0.0
_MIN_INTERVAL_SEC = 24 * 3600  # раз в сутки фоном

# Только бесплатные зависимости из requirements / инфраструктура
FREE_PIP_PACKAGES = [
    "playwright>=1.49.0",
    "duckduckgo-search>=7.0.0",
    "httpx>=0.28.0",
    "edge-tts>=6.1.0",
    "psutil>=6.0.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "python-multipart>=0.0.12",
    "pydantic>=2.10.0",
    "aiofiles>=24.1.0",
    "openpyxl>=3.1.0",
    "python-docx>=1.1.0",
    "pandas>=2.2.0",
    "watchdog>=6.0.0",
    "socksio>=1.0.0",
    "pyyaml>=6.0.2",
    "cachetools>=5.5.0",
    "python-dotenv>=1.0.1",
]


def _state_path() -> Path:
    from modules.app_paths import user_data_dir

    return user_data_dir() / "jarvis_free_updates.json"


def _load_state() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(data: dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_free_components_update(
    *,
    force_browsers: bool = False,
    force_pip: bool = False,
) -> dict[str, Any]:
    """
    Обновить pip-пакеты и переустановить браузеры в Jarvis/browsers.
    """
    from modules.jarvis_browsers import install_jarvis_browsers, jarvis_browsers_dir

    result: dict[str, Any] = {
        "ok": True,
        "pip": {},
        "browsers": {},
        "browsers_dir": str(jarvis_browsers_dir()),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    pip_args = [sys.executable, "-m", "pip", "install"]
    if force_pip:
        pip_args.append("-U")
    pip_args.extend(FREE_PIP_PACKAGES)

    try:
        r = subprocess.run(
            pip_args,
            capture_output=True,
            text=True,
            timeout=900,
            encoding="utf-8",
            errors="replace",
        )
        result["pip"] = {
            "ok": r.returncode == 0,
            "code": r.returncode,
            "tail": ((r.stdout or "") + (r.stderr or ""))[-500:],
        }
        if r.returncode != 0:
            result["ok"] = False
    except Exception as e:
        result["pip"] = {"ok": False, "error": str(e)[:200]}
        result["ok"] = False

    def on_msg(msg: str) -> None:
        result.setdefault("browser_log", []).append(msg[:200])

    try:
        ch_ok, chrome_ok = install_jarvis_browsers(
            on_message=on_msg,
            force=force_browsers,
        )
        result["browsers"] = {
            "chromium_ok": ch_ok,
            "windowed_ok": chrome_ok,
        }
        if not (ch_ok and chrome_ok):
            result["ok"] = False
    except Exception as e:
        result["browsers"] = {"ok": False, "error": str(e)[:200]}
        result["ok"] = False

    _save_state(
        {
            "last_run": result["at"],
            "last_ok": result["ok"],
            "force_browsers": force_browsers,
        }
    )
    return result


def maybe_run_free_updates_async(*, force: bool = False) -> bool:
    """Фоновое обновление не чаще раза в сутки (или сразу при force)."""
    global _LAST_RUN_AT

    now = time.monotonic()
    state = _load_state()
    last_str = state.get("last_run") or ""
    if not force and last_str:
        try:
            from datetime import datetime

            last_dt = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
            age = time.time() - last_dt.timestamp()
            if age < _MIN_INTERVAL_SEC:
                return False
        except Exception:
            pass

    if not force and (now - _LAST_RUN_AT) < 60:
        return False

    def _work() -> None:
        global _LAST_RUN_AT
        with _UPDATE_LOCK:
            _LAST_RUN_AT = time.monotonic()
            try:
                from modules.network_env import probe_internet

                if not probe_internet()[0]:
                    return
                run_free_components_update(force_browsers=force, force_pip=True)
            except Exception as e:
                _log.warning("free components update: %s", e)

    threading.Thread(
        target=_work,
        daemon=True,
        name="jarvis-free-updates",
    ).start()
    return True


def free_updates_status() -> dict[str, Any]:
    state = _load_state()
    from modules.jarvis_browsers import (
        find_headless_chromium_exe,
        find_windowed_chrome_exe,
        jarvis_browsers_dir,
    )

    return {
        "last_run": state.get("last_run"),
        "last_ok": state.get("last_ok"),
        "interval_hours": _MIN_INTERVAL_SEC / 3600,
        "browsers_dir": str(jarvis_browsers_dir()),
        "headless_exe": find_headless_chromium_exe(),
        "windowed_exe": find_windowed_chrome_exe(),
    }
