"""
OpenConnect VPN — управление туннелем через CLI openconnect (Windows).
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
VPN_DIR = DATA_DIR / "vpn"
CONFIG_FILE = VPN_DIR / "openconnect_config.json"
LOG_FILE = VPN_DIR / "openconnect.log"
PID_FILE = VPN_DIR / "openconnect.pid"

# Публичные параметры пресета (без пароля).
JARVIS_OCSERV_PRESET: dict[str, Any] = {
    "id": "jarvis-paris",
    "label": "Сервер Jarvis за границей (Париж)",
    "server": "82.40.49.176",
    "port": 443,
    "username": "vpn",
    "protocol": "anyconnect",
    "server_cert_pin": "pin-sha256:n7djC4LShZy9LsYEI8y343iMjgM9Xc6/sT90pqkl8x4=",
    "hint": "OpenConnect (ocserv). Пароль задаётся вами — не хранится в репозитории.",
}

_OPENCONNECT_CANDIDATES = [
    Path(r"C:\Program Files\OpenConnect-GUI\openconnect.exe"),
    Path(r"C:\Program Files (x86)\OpenConnect-GUI\openconnect.exe"),
]
_VPNC_SCRIPT_CANDIDATES = [
    Path(r"C:\Program Files\OpenConnect-GUI\vpnc-script-win.js"),
    Path(r"C:\Program Files (x86)\OpenConnect-GUI\vpnc-script-win.js"),
]

_lock = threading.Lock()
_proc: subprocess.Popen[str] | None = None
_log_lines: deque[str] = deque(maxlen=200)
_reader_thread: threading.Thread | None = None


class VpnStatus(str, Enum):
    OFF = "off"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class VpnRuntime:
    status: VpnStatus = VpnStatus.OFF
    message: str = "Отключено"
    error: str | None = None
    server: str = ""
    managed: bool = False
    external_gui: bool = False
    since: float | None = None


_runtime = VpnRuntime()


def _default_config() -> dict[str, Any]:
    return {
        "server": "",
        "port": 443,
        "username": "",
        "password": "",
        "use_jarvis_preset": False,
        "openconnect_path": "",
        "server_cert_pin": JARVIS_OCSERV_PRESET["server_cert_pin"],
    }


def _load_config() -> dict[str, Any]:
    VPN_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            return {**_default_config(), **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return _default_config()


def _save_config(data: dict[str, Any]) -> None:
    VPN_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({**_default_config(), **data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _find_openconnect_exe(cfg: dict[str, Any] | None = None) -> str | None:
    custom = ((cfg or _load_config()).get("openconnect_path") or "").strip()
    if custom and Path(custom).is_file():
        return custom
    for p in _OPENCONNECT_CANDIDATES:
        if p.is_file():
            return str(p)
    found = shutil.which("openconnect")
    return found


def _find_vpnc_script() -> str | None:
    for p in _VPNC_SCRIPT_CANDIDATES:
        if p.is_file():
            return str(p)
    return None


def _effective_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    out = {
        "server": (cfg.get("server") or "").strip(),
        "port": int(cfg.get("port") or 443),
        "username": (cfg.get("username") or "").strip(),
        "password": (cfg.get("password") or "").strip(),
        "server_cert_pin": (cfg.get("server_cert_pin") or "").strip(),
    }
    if cfg.get("use_jarvis_preset"):
        preset = JARVIS_OCSERV_PRESET
        if not out["server"]:
            out["server"] = preset["server"]
        if not out["username"]:
            out["username"] = preset["username"]
        if out["port"] == 443:
            out["port"] = int(preset["port"])
        if not out["server_cert_pin"]:
            out["server_cert_pin"] = preset["server_cert_pin"]
    return out


def _mask_password(value: str) -> bool:
    return bool((value or "").strip())


def get_preset() -> dict[str, Any]:
    p = JARVIS_OCSERV_PRESET
    return {
        "id": p["id"],
        "label": p["label"],
        "server": p["server"],
        "port": p["port"],
        "username": p["username"],
        "protocol": p["protocol"],
        "hint": p["hint"],
        "has_cert_pin": bool(p.get("server_cert_pin")),
    }


def get_config() -> dict[str, Any]:
    cfg = _load_config()
    eff = _effective_settings(cfg)
    exe = _find_openconnect_exe(cfg)
    return {
        "server": eff["server"],
        "port": eff["port"],
        "username": eff["username"],
        "password_configured": _mask_password(cfg.get("password") or ""),
        "use_jarvis_preset": bool(cfg.get("use_jarvis_preset")),
        "openconnect_path": (cfg.get("openconnect_path") or "").strip(),
        "openconnect_found": bool(exe),
        "openconnect_exe": exe or "",
        "server_cert_pin_configured": bool(eff["server_cert_pin"]),
        "preset": get_preset(),
        "ready": bool(eff["server"] and eff["username"] and exe),
    }


def save_config(
    *,
    server: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    use_jarvis_preset: bool | None = None,
    openconnect_path: str | None = None,
    server_cert_pin: str | None = None,
) -> dict[str, Any]:
    cfg = _load_config()
    if server is not None:
        cfg["server"] = server.strip()
    if port is not None:
        cfg["port"] = max(1, min(65535, int(port)))
    if username is not None:
        cfg["username"] = username.strip()
    if password is not None and password.strip():
        cfg["password"] = password
    if use_jarvis_preset is not None:
        cfg["use_jarvis_preset"] = bool(use_jarvis_preset)
    if openconnect_path is not None:
        cfg["openconnect_path"] = openconnect_path.strip()
    if server_cert_pin is not None:
        cfg["server_cert_pin"] = server_cert_pin.strip()
    _save_config(cfg)
    out = get_config()
    return {**out, "save_ok": True, "message": "Настройки VPN сохранены"}


def _append_log(line: str) -> None:
    line = (line or "").rstrip()
    if not line:
        return
    _log_lines.append(line)
    try:
        VPN_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _read_process_output(proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for raw in proc.stdout:
        _append_log(raw.rstrip())
        low = raw.lower()
        with _lock:
            if "established dtls" in low or ("configured" in low and "interface" in low):
                _runtime.status = VpnStatus.CONNECTED
                _runtime.message = "Подключено"
                _runtime.error = None
            elif "authentication error" in low or "cannot obtain cookie" in low:
                _runtime.status = VpnStatus.ERROR
                _runtime.error = "Ошибка авторизации — проверьте логин и пароль"
            elif "failed" in low or "error" in low:
                if _runtime.status == VpnStatus.CONNECTING:
                    _runtime.error = raw.strip()[:240]


def _proc_alive(proc: subprocess.Popen[str] | None) -> bool:
    return proc is not None and proc.poll() is None


def _detect_external_openconnect(server: str) -> bool:
    """VPN поднят через OpenConnect GUI или другой процесс."""
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Process openconnect*,OpenConnect* -ErrorAction SilentlyContinue | "
                    "Select-Object -ExpandProperty ProcessName",
                ],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            names = (r.stdout or "").lower()
            if "openconnect" in names:
                return True
            if server:
                r2 = subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"Get-NetAdapter -ErrorAction SilentlyContinue | "
                        f"Where-Object {{ $_.InterfaceDescription -match 'Wintun|OpenConnect' "
                        f"-or $_.Name -like '*{server.replace('.', '_')}*' }} | "
                        f"Select-Object -First 1 -ExpandProperty Status",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                st = (r2.stdout or "").strip().lower()
                return st == "up"
        else:
            r = subprocess.run(["pgrep", "-f", "openconnect"], capture_output=True, timeout=5)
            return r.returncode == 0
    except Exception:
        return False
    return False


def _refresh_runtime() -> VpnRuntime:
    global _proc
    with _lock:
        cfg = _load_config()
        eff = _effective_settings(cfg)
        server = eff["server"]

        if _proc_alive(_proc):
            _runtime.managed = True
            _runtime.server = server
            if _runtime.status != VpnStatus.CONNECTED:
                _runtime.status = VpnStatus.CONNECTING
                _runtime.message = "Подключение…"
            return _runtime

        if _proc and _proc.poll() is not None:
            code = _proc.returncode
            _proc = None
            try:
                PID_FILE.unlink(missing_ok=True)
            except Exception:
                pass
            if _runtime.status in (VpnStatus.CONNECTING, VpnStatus.CONNECTED):
                _runtime.status = VpnStatus.ERROR
                _runtime.error = _runtime.error or f"OpenConnect завершился (код {code})"
                _runtime.message = "Отключено"
            _runtime.managed = False

        ext = _detect_external_openconnect(server)
        _runtime.external_gui = ext and not _runtime.managed
        if ext and not _runtime.managed:
            # Системный VPN (OpenConnect GUI) — не смешиваем со статусом Jarvis.
            _runtime.status = VpnStatus.OFF
            _runtime.message = "На ПК активен внешний OpenConnect (Jarvis не управляет)"
            _runtime.managed = False
            _runtime.error = None
            return _runtime

        if _runtime.status != VpnStatus.CONNECTING:
            _runtime.status = VpnStatus.OFF
            _runtime.message = ""
            _runtime.managed = False
            _runtime.external_gui = False
            _runtime.since = None
        return _runtime


def status_dict() -> dict[str, Any]:
    rt = _refresh_runtime()
    cfg = get_config()
    return {
        "status": rt.status.value,
        "status_label": {
            VpnStatus.OFF: "Выключен",
            VpnStatus.CONNECTING: "Подключение…",
            VpnStatus.CONNECTED: "Подключено",
            VpnStatus.ERROR: "Ошибка",
        }.get(rt.status, rt.status.value),
        "message": rt.message,
        "error": rt.error,
        "server": rt.server or cfg.get("server") or "",
        "managed": rt.managed,
        "external_gui": rt.external_gui,
        "system_vpn_active": rt.external_gui,
        "openconnect_found": cfg.get("openconnect_found"),
        "ready": cfg.get("ready"),
        "use_jarvis_preset": cfg.get("use_jarvis_preset"),
        "preset": cfg.get("preset"),
    }


def get_log_tail(limit: int = 80) -> list[str]:
    lines = list(_log_lines)
    if len(lines) < limit and LOG_FILE.exists():
        try:
            text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
            file_lines = [ln for ln in text.splitlines() if ln.strip()]
            lines = file_lines[-limit:]
        except Exception:
            pass
    return lines[-max(1, min(limit, 200)) :]


def _build_connect_args(cfg: dict[str, Any], eff: dict[str, Any], exe: str) -> list[str]:
    server = eff["server"]
    port = eff["port"]
    host = server if port == 443 else f"{server}:{port}"
    args = [
        exe,
        "--protocol=anyconnect",
        f"--user={eff['username']}",
        "--passwd-on-stdin",
        "--non-inter",
        "--no-dtls",
        f"--server={host}",
    ]
    pin = eff.get("server_cert_pin") or ""
    if pin:
        args.append(f"--servercert={pin}")
    script = _find_vpnc_script()
    if script:
        args.append(f"--script={script}")
    args.append(host)
    return args


def connect() -> dict[str, Any]:
    global _proc, _reader_thread
    with _lock:
        rt = _refresh_runtime()
        if rt.status == VpnStatus.CONNECTED:
            return status_dict()

        cfg = _load_config()
        eff = _effective_settings(cfg)
        exe = _find_openconnect_exe(cfg)
        if not exe:
            raise ValueError(
                "openconnect.exe не найден. Установите OpenConnect GUI: "
                "https://github.com/openconnect/openconnect-gui/releases"
            )
        if not eff["server"] or not eff["username"]:
            raise ValueError("Укажите сервер и логин (или включите пресет Jarvis).")
        password = eff["password"]
        if not password:
            raise ValueError("Укажите пароль VPN в настройках (не сохраняется в репозитории).")

        if _proc_alive(_proc):
            _proc.terminate()
            _proc = None

        VPN_DIR.mkdir(parents=True, exist_ok=True)
        try:
            LOG_FILE.write_text("", encoding="utf-8")
        except Exception:
            pass
        _log_lines.clear()

        args = _build_connect_args(cfg, eff, exe)
        _append_log(f"Jarvis: запуск OpenConnect → {eff['server']}")

        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as e:
            raise ValueError(
                f"Не удалось запустить OpenConnect: {e}. "
                "На Windows может потребоваться запуск Jarvis от имени администратора."
            ) from e

        assert proc.stdin is not None
        proc.stdin.write(password + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        _proc = proc
        try:
            PID_FILE.write_text(str(proc.pid), encoding="utf-8")
        except Exception:
            pass

        _runtime.status = VpnStatus.CONNECTING
        _runtime.message = "Подключение…"
        _runtime.error = None
        _runtime.server = eff["server"]
        _runtime.managed = True
        _runtime.since = time.time()

        _reader_thread = threading.Thread(target=_read_process_output, args=(proc,), daemon=True)
        _reader_thread.start()

        # Короткая пауза — дать процессу стартовать
        time.sleep(1.2)
        if proc.poll() is not None and proc.returncode != 0:
            _runtime.status = VpnStatus.ERROR
            _runtime.error = _runtime.error or "OpenConnect завершился сразу после старта"
            tail = get_log_tail(12)
            if tail:
                _runtime.error += " — " + tail[-1][:120]

    return status_dict()


def disconnect() -> dict[str, Any]:
    global _proc
    with _lock:
        if _proc_alive(_proc):
            assert _proc is not None
            try:
                _proc.terminate()
                _proc.wait(timeout=8)
            except Exception:
                try:
                    _proc.kill()
                except Exception:
                    pass
            _proc = None
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        _runtime.status = VpnStatus.OFF
        _runtime.message = "Отключено"
        _runtime.error = None
        _runtime.managed = False
        _runtime.external_gui = False
        _runtime.since = None
        _append_log("Jarvis: отключение VPN")
    return status_dict()


def fetch_server_cert_pin(host: str, port: int = 443) -> str:
    """Публичный отпечаток TLS — не секрет."""
    with socket.create_connection((host, port), timeout=8) as sock:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert(binary_form=True)
    digest = hashlib.sha256(cert).digest()
    return "pin-sha256:" + base64.b64encode(digest).decode("ascii")


def resolve_server_cert_pin(host: str, port: int = 443) -> dict[str, Any]:
    host = (host or "").strip()
    if not host:
        raise ValueError("Укажите адрес сервера")
    pin = fetch_server_cert_pin(host, port)
    return {"server": host, "port": port, "server_cert_pin": pin}
