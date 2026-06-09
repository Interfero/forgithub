"""
Доступ Jarvis к хосту: файловая система (Проводник), реестр Windows, аналоги в Linux.
Данные только локально на ПК пользователя.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

_MAX_LIST = 300
_MAX_READ_BYTES = 512_000


def platform_info() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "node": platform.node(),
        "python": platform.python_version(),
    }


def _resolve_path(path: str) -> Path:
    raw = (path or "").strip() or str(Path.home())
    p = Path(raw).expanduser()
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def fs_list(path: str = "", *, max_entries: int = _MAX_LIST) -> dict[str, Any]:
    root = _resolve_path(path)
    if not root.exists():
        raise FileNotFoundError(f"Путь не найден: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Не каталог: {root}")

    entries: list[dict[str, Any]] = []
    try:
        for i, child in enumerate(sorted(root.iterdir(), key=lambda x: x.name.lower())):
            if i >= max(1, min(max_entries, _MAX_LIST)):
                break
            try:
                st = child.stat()
                entries.append(
                    {
                        "name": child.name,
                        "path": str(child),
                        "dir": child.is_dir(),
                        "size": st.st_size if child.is_file() else None,
                        "modified": int(st.st_mtime),
                    }
                )
            except OSError:
                entries.append({"name": child.name, "path": str(child), "dir": None, "error": "access"})
    except PermissionError as e:
        raise PermissionError(f"Нет доступа к {root}") from e

    return {
        "path": str(root),
        "count": len(entries),
        "truncated": len(entries) >= max_entries,
        "entries": entries,
    }


def fs_stat(path: str) -> dict[str, Any]:
    p = _resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Путь не найден: {p}")
    st = p.stat()
    return {
        "path": str(p),
        "exists": True,
        "is_dir": p.is_dir(),
        "is_file": p.is_file(),
        "size": st.st_size,
        "modified": int(st.st_mtime),
        "created": int(getattr(st, "st_ctime", st.st_mtime)),
    }


def fs_read(path: str, *, max_bytes: int = _MAX_READ_BYTES, encoding: str = "utf-8") -> dict[str, Any]:
    p = _resolve_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл не найден: {p}")
    doc_suffixes = {
        ".pdf",
        ".docx",
        ".doc",
        ".pptx",
        ".ppt",
        ".xlsx",
        ".xls",
        ".epub",
        ".html",
        ".htm",
        ".csv",
    }
    if p.suffix.lower() in doc_suffixes:
        from modules.document_tools import read_document

        max_chars = max(1024, min(int(max_bytes), _MAX_READ_BYTES))
        data = read_document(str(p), max_chars=max_chars)
        content = data.get("content") or ""
        return {
            "path": str(p),
            "binary": False,
            "size": p.stat().st_size,
            "truncated": len(content) >= max_chars,
            "content": content,
            "pages": data.get("pages"),
            "format": data.get("format") or p.suffix.lstrip("."),
            "engine": data.get("engine"),
            "hint": "Документ прочитан через doc_read/MarkItDown (без токенов LLM).",
        }
    limit = max(1024, min(int(max_bytes), _MAX_READ_BYTES))
    size = p.stat().st_size
    with p.open("rb") as f:
        data = f.read(limit + 1)
    truncated = len(data) > limit
    if truncated:
        data = data[:limit]
    try:
        text = data.decode(encoding, errors="replace")
        binary = False
    except Exception:
        text = ""
        binary = True
    if binary or "\x00" in text[:2000]:
        return {
            "path": str(p),
            "binary": True,
            "size": size,
            "message": "Бинарный файл — чтение как текст недоступно",
        }
    return {
        "path": str(p),
        "binary": False,
        "size": size,
        "truncated": truncated or size > limit,
        "content": text,
    }


def explorer_open(path: str = "") -> dict[str, Any]:
    """Открыть папку в Проводнике Windows или файловом менеджере Linux."""
    p = _resolve_path(path or str(Path.home()))
    target = p if p.exists() else p.parent
    if not target.exists():
        target = Path.home()

    if sys.platform == "win32":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return {"ok": True, "path": str(target), "message": f"Проводник: {target}"}

    for cmd in (
        ["xdg-open", str(target)],
        ["gio", "open", str(target)],
        ["nautilus", str(target)],
    ):
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"ok": True, "path": str(target), "message": f"Открыто: {target}"}
        except FileNotFoundError:
            continue
    raise RuntimeError("Не найден xdg-open / gio / nautilus")


def _parse_hive(name: str) -> int:
    if sys.platform != "win32":
        raise RuntimeError("Реестр Windows доступен только на Windows")
    import winreg

    hives = {
        "hkcu": winreg.HKEY_CURRENT_USER,
        "hkey_current_user": winreg.HKEY_CURRENT_USER,
        "hklm": winreg.HKEY_LOCAL_MACHINE,
        "hkey_local_machine": winreg.HKEY_LOCAL_MACHINE,
        "hkcr": winreg.HKEY_CLASSES_ROOT,
        "hkey_classes_root": winreg.HKEY_CLASSES_ROOT,
        "hku": winreg.HKEY_USERS,
        "hkcc": winreg.HKEY_CURRENT_CONFIG,
    }
    key = hives.get((name or "hkcu").strip().lower().replace("\\", ""))
    if key is None:
        raise ValueError(f"Неизвестный корень реестра: {name}")
    return key


def registry_read(hive: str, subkey: str, value_name: str = "") -> dict[str, Any]:
    if sys.platform != "win32":
        return linux_config_read(subkey or value_name or hive)

    import winreg

    root = _parse_hive(hive)
    sk = (subkey or "").strip().strip("\\")
    vn = (value_name or "").strip()
    with winreg.OpenKey(root, sk) as key:
        if vn:
            val, typ = winreg.QueryValueEx(key, vn)
            return {
                "hive": hive,
                "subkey": sk,
                "value": vn,
                "type": int(typ),
                "data": _registry_value_to_str(val),
            }
        default, typ = winreg.QueryValueEx(key, "")
        return {
            "hive": hive,
            "subkey": sk,
            "value": "(Default)",
            "type": int(typ),
            "data": _registry_value_to_str(default),
        }


def _registry_value_to_str(val: Any) -> str:
    if isinstance(val, bytes):
        try:
            return val.decode("utf-16-le").rstrip("\x00")
        except Exception:
            return val.hex()[:200]
    if isinstance(val, (list, tuple)):
        return "; ".join(str(x) for x in val)
    return str(val)


def registry_list(hive: str, subkey: str = "", *, max_items: int = 120) -> dict[str, Any]:
    if sys.platform != "win32":
        p = _resolve_path(subkey or "/etc")
        return fs_list(str(p), max_entries=max_items)

    import winreg

    root = _parse_hive(hive)
    sk = (subkey or "").strip().strip("\\")
    values: list[dict[str, str]] = []
    subkeys: list[str] = []
    with winreg.OpenKey(root, sk) as key:
        i = 0
        while i < max_items:
            try:
                name, data, typ = winreg.EnumValue(key, i)
                values.append({"name": name or "(Default)", "data": _registry_value_to_str(data)[:200]})
                i += 1
            except OSError:
                break
        j = 0
        while j < max_items:
            try:
                subkeys.append(winreg.EnumKey(key, j))
                j += 1
            except OSError:
                break
    return {"hive": hive, "subkey": sk, "values": values, "subkeys": subkeys}


def linux_config_read(path: str) -> dict[str, Any]:
    """Linux/macOS: чтение конфигурационного файла вместо реестра."""
    candidates = [
        path,
        f"/etc/{path.lstrip('/')}" if path and not path.startswith("/") else path,
        str(Path.home() / ".config" / path),
    ]
    for c in candidates:
        if not c:
            continue
        p = _resolve_path(c)
        if p.is_file():
            return fs_read(str(p))
    raise FileNotFoundError(f"Конфиг не найден: {path}")
