"""Перезапуск Jarvis — dev: restart.bat; exe: повторный запуск Jarvis.exe."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from modules.app_paths import bundle_root, is_frozen


def install_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_root().parent


def _win_no_window_flags() -> int:
    if sys.platform != "win32":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def trigger_restart() -> dict:
    if is_frozen():
        exe = Path(sys.executable).resolve()
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            creationflags=_win_no_window_flags(),
            close_fds=True,
        )
        message = "Перезапуск Jarvis.exe…"
    else:
        root = install_root()
        vbs = root / "run-restart.vbs"
        bat = root / "restart.bat"
        if vbs.is_file():
            cmd = ["wscript.exe", "//nologo", str(vbs)]
            cwd = str(root)
        elif bat.is_file():
            cmd = ["cmd.exe", "/c", str(bat)]
            cwd = str(root)
        else:
            raise FileNotFoundError(f"Не найден run-restart.vbs в {root}")
        subprocess.Popen(
            cmd,
            cwd=cwd,
            creationflags=_win_no_window_flags(),
            close_fds=True,
        )
        message = "Перезапуск Jarvis (сборка + сервер)…"

    def _exit_later() -> None:
        time.sleep(0.6)
        os._exit(0)

    threading.Thread(target=_exit_later, daemon=True).start()
    return {"ok": True, "message": message, "frozen": is_frozen()}
