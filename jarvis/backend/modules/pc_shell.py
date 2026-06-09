"""
Консоль и PowerShell на ПК пользователя — запуск окна и выполнение команд по запросу Jarvis.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
SHELL_DIR = DATA_DIR / "shell"
LOG_FILE = SHELL_DIR / "shell.log"

_lock = threading.Lock()
_session: subprocess.Popen[str] | None = None
_session_shell = ""
_session_cwd = ""
_last_run: dict[str, Any] = {}


def _log(line: str) -> None:
    SHELL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {line}\n")
    except Exception:
        pass


def _default_cwd() -> str:
    home = Path.home()
    return str(home if home.is_dir() else Path.cwd())


def _normalize_shell(name: str) -> str:
    s = (name or "powershell").strip().lower()
    if s in ("cmd", "cmd.exe", "command", "командная"):
        return "cmd"
    return "powershell"


def _escape_ps_single(s: str) -> str:
    return (s or "").replace("'", "''")


def _proc_alive(proc: subprocess.Popen[str] | None) -> bool:
    return proc is not None and proc.poll() is None


def _read_available(proc: subprocess.Popen[str], timeout: float = 0.4) -> str:
    if proc.stdout is None:
        return ""
    chunks: list[str] = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            line = proc.stdout.readline()
        except Exception:
            break
        if not line:
            break
        chunks.append(line)
    return "".join(chunks)


def open_console(*, shell: str = "powershell", cwd: str | None = None) -> dict[str, Any]:
    """Открыть видимое окно CMD или PowerShell."""
    sh = _normalize_shell(shell)
    work = (cwd or _default_cwd()).strip() or _default_cwd()
    if not Path(work).is_dir():
        work = _default_cwd()

    if sys.platform != "win32":
        proc = subprocess.Popen(
            ["/bin/bash", "-l"],
            cwd=work,
        )
        _log(f"open bash pid={proc.pid} cwd={work}")
        return {
            "ok": True,
            "shell": "bash",
            "pid": proc.pid,
            "cwd": work,
            "message": f"Открыт bash (pid {proc.pid})",
        }

    if sh == "cmd":
        cmdline = f'cd /d "{work}"'
        args = ["cmd.exe", "/c", "start", "Jarvis CMD", "cmd.exe", "/K", cmdline]
    else:
        ps_open = (
            f"Set-Location -LiteralPath '{_escape_ps_single(work)}'; "
            "Write-Host 'Jarvis PowerShell' -ForegroundColor Cyan"
        )
        args = [
            "cmd.exe",
            "/c",
            "start",
            "Jarvis PowerShell",
            "powershell.exe",
            "-NoExit",
            "-NoLogo",
            "-Command",
            ps_open,
        ]

    subprocess.Popen(args, cwd=work)
    _log(f"open {sh} visible cwd={work}")
    return {
        "ok": True,
        "shell": sh,
        "cwd": work,
        "message": f"Открыто окно {sh.upper()} в {work}",
    }


def run_command(
    command: str,
    *,
    shell: str = "powershell",
    cwd: str | None = None,
    visible: bool = False,
    timeout: int = 120,
) -> dict[str, Any]:
    """Выполнить команду; visible=True — показать в новом окне PowerShell/CMD."""
    cmd = (command or "").strip()
    if not cmd:
        raise ValueError("Пустая команда")

    sh = _normalize_shell(shell)
    work = (cwd or _default_cwd()).strip() or _default_cwd()
    if not Path(work).is_dir():
        work = _default_cwd()

    global _last_run

    if visible and sys.platform == "win32":
        if sh == "cmd":
            inner = f'cd /d "{work}" && {cmd}'
            args = ["cmd.exe", "/c", "start", "Jarvis CMD", "cmd.exe", "/K", inner]
        else:
            inner = (
                f"Set-Location -LiteralPath '{_escape_ps_single(work)}'; "
                f"{cmd}"
            )
            args = [
                "cmd.exe",
                "/c",
                "start",
                "Jarvis PowerShell",
                "powershell.exe",
                "-NoExit",
                "-NoLogo",
                "-Command",
                inner,
            ]
        subprocess.Popen(args, cwd=work)
        _log(f"run visible {sh}: {cmd[:120]}")
        out = {
            "ok": True,
            "shell": sh,
            "visible": True,
            "command": cmd,
            "cwd": work,
            "stdout": "",
            "stderr": "",
            "exit_code": None,
            "message": f"Команда запущена в видимом окне {sh.upper()}",
        }
        _last_run = out
        return out

    if sh == "cmd":
        exe = ["cmd.exe", "/c", cmd]
    else:
        exe = [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            cmd,
        ]

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        proc = subprocess.run(
            exe,
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(5, min(int(timeout), 600)),
            creationflags=creationflags,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        code = proc.returncode
        ok = code == 0
        _log(f"run {sh} code={code}: {cmd[:120]}")
        out = {
            "ok": ok,
            "shell": sh,
            "visible": False,
            "command": cmd,
            "cwd": work,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": code,
            "message": "OK" if ok else f"Код выхода {code}",
        }
        _last_run = out
        return out
    except subprocess.TimeoutExpired as e:
        _log(f"timeout {sh}: {cmd[:80]}")
        out = {
            "ok": False,
            "shell": sh,
            "visible": False,
            "command": cmd,
            "cwd": work,
            "stdout": (e.stdout or "").strip() if e.stdout else "",
            "stderr": (e.stderr or "").strip() if e.stderr else "",
            "exit_code": None,
            "message": f"Таймаут ({timeout} с)",
        }
        _last_run = out
        return out


def start_session(*, shell: str = "powershell", cwd: str | None = None) -> dict[str, Any]:
    """Интерактивная сессия Jarvis: видимое окно + очередь команд через stdin."""
    global _session, _session_shell, _session_cwd

    sh = _normalize_shell(shell)
    work = (cwd or _default_cwd()).strip() or _default_cwd()

    with _lock:
        if _proc_alive(_session):
            return {
                "ok": True,
                "already_running": True,
                "shell": _session_shell,
                "cwd": _session_cwd,
                "pid": _session.pid if _session else None,
                "message": "Сессия уже запущена",
            }

        if sys.platform != "win32":
            proc = subprocess.Popen(
                ["/bin/bash", "-l"],
                cwd=work,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        elif sh == "cmd":
            proc = subprocess.Popen(
                ["cmd.exe"],
                cwd=work,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            proc = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    "-",
                ],
                cwd=work,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )

        _session = proc
        _session_shell = sh
        _session_cwd = work
        _log(f"session start {sh} pid={proc.pid} cwd={work}")

    return {
        "ok": True,
        "shell": sh,
        "cwd": work,
        "pid": proc.pid,
        "message": f"Сессия {sh.upper()} запущена (pid {proc.pid})",
    }


def send_session_command(command: str) -> dict[str, Any]:
    """Отправить команду в активную сессию shell."""
    cmd = (command or "").strip()
    if not cmd:
        raise ValueError("Пустая команда")

    with _lock:
        if not _proc_alive(_session):
            raise ValueError("Сессия не запущена. Сначала shell_session_start или shell_open.")

        assert _session is not None
        assert _session.stdin is not None
        line = cmd if _session_shell == "cmd" else cmd
        _session.stdin.write(line + "\n")
        _session.stdin.flush()
        if _session_shell == "powershell":
            _session.stdin.write("Write-Host '__JARVIS_END__'\n")
            _session.stdin.flush()

        collected: list[str] = []
        deadline = time.time() + 8.0
        while time.time() < deadline:
            chunk = _read_available(_session, timeout=0.5)
            if not chunk:
                if _session.poll() is not None:
                    break
                continue
            collected.append(chunk)
            if "__JARVIS_END__" in chunk or _session_shell == "cmd":
                if len("".join(collected)) > 20:
                    break

        text = "".join(collected).replace("__JARVIS_END__", "").strip()
        _log(f"session send: {cmd[:80]}")

    return {
        "ok": True,
        "command": cmd,
        "output": text[-8000:],
        "message": "Команда отправлена в сессию",
    }


def close_session() -> dict[str, Any]:
    global _session, _session_shell, _session_cwd
    with _lock:
        if not _proc_alive(_session):
            _session = None
            return {"ok": True, "message": "Сессия не была активна"}
        assert _session is not None
        try:
            _session.terminate()
            _session.wait(timeout=5)
        except Exception:
            try:
                _session.kill()
            except Exception:
                pass
        pid = _session.pid
        _session = None
        _session_shell = ""
        _session_cwd = ""
        _log(f"session closed pid={pid}")
    return {"ok": True, "message": "Сессия закрыта"}


def status_dict() -> dict[str, Any]:
    with _lock:
        alive = _proc_alive(_session)
        return {
            "platform": sys.platform,
            "session_active": alive,
            "session_shell": _session_shell if alive else "",
            "session_cwd": _session_cwd if alive else "",
            "session_pid": _session.pid if alive and _session else None,
            "last_run": _last_run or None,
        }


def format_run_result(result: dict[str, Any]) -> str:
    lines = [
        result.get("message") or "",
        f"shell: {result.get('shell')}",
        f"cwd: {result.get('cwd')}",
        f"command: {result.get('command')}",
    ]
    if result.get("visible"):
        lines.append("(видимое окно — вывод смотрите на экране)")
    else:
        code = result.get("exit_code")
        if code is not None:
            lines.append(f"exit_code: {code}")
        out = (result.get("stdout") or "").strip()
        err = (result.get("stderr") or "").strip()
        if out:
            lines.append("--- stdout ---")
            lines.append(out[-6000:])
        if err:
            lines.append("--- stderr ---")
            lines.append(err[-2000:])
    return "\n".join(lines)


def extract_shell_command(user_text: str) -> str | None:
    """Извлечь команду из фразы пользователя."""
    t = (user_text or "").strip()
    if not t:
        return None
    patterns = [
        r"(?:выполни|запусти|введи|напиши|run)\s+(?:в\s+)?(?:powershell|повершел|cmd|консоли|терминале)?\s*[:—-]?\s*(.+)",
        r"(?:команда|command)\s*[:—-]\s*(.+)",
        r"`([^`]+)`",
        r'"([^"]{2,})"',
    ]
    for pat in patterns:
        m = re.search(pat, t, re.I | re.S)
        if m:
            cand = m.group(1).strip()
            if len(cand) >= 2:
                return cand
    return None
