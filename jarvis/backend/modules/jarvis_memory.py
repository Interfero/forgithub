"""
ОЗУ: процессы Jarvis (бэкенд, дочерние, Ollama при локальной Qwen) относительно RAM ПК.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import psutil

_SERVER_STARTED_AT = time.monotonic()
_LAUNCH_GRACE_SEC = 12.0
_MIN_RSS_LAUNCHED_BYTES = 60 * 1024 * 1024  # ~60 МБ — бэкенд уже поднялся

_load_baseline_rss: int | None = None


def _backend_root_marker() -> str:
    return str(Path(__file__).resolve().parent.parent).lower()


def _process_rss(proc: psutil.Process) -> int:
    try:
        return int(proc.memory_info().rss)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0


def _cmdline_text(proc: psutil.Process) -> str:
    try:
        return " ".join(proc.cmdline() or []).lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return ""


def _process_name(proc: psutil.Process) -> str:
    try:
        return (proc.name() or "process").lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "process"


def _process_role(name: str, cmd: str, *, is_root: bool, is_child: bool) -> str:
    if is_root:
        return "Сервер Jarvis"
    if name.startswith("ollama"):
        return "Ollama (Qwen в ОЗУ)"
    if "download_qwen" in cmd or "qwen" in cmd and "model" in cmd:
        return "Загрузка Qwen"
    if "uvicorn" in cmd or "main:app" in cmd:
        return "API Jarvis"
    if is_child:
        return "Сервис Jarvis"
    if "python" in name:
        return "Python · Jarvis"
    return name or "Процесс"


def _is_jarvis_python(proc: psutil.Process, root: psutil.Process) -> bool:
    try:
        if proc.pid == root.pid:
            return True
        if root.pid in {p.pid for p in proc.parents()}:
            return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    cmd = _cmdline_text(proc)
    marker = _backend_root_marker()
    if marker and marker in cmd:
        return True
    if "jarvis" in cmd and ("uvicorn" in cmd or "main:app" in cmd or "backend" in cmd):
        return True
    return False


def _should_count_ollama() -> bool:
    try:
        from modules import local_qwen as lq

        if not lq.is_qwen_ram_enabled():
            return False
        st = lq.get_qwen_status()
        if st.get("ollama_model_loaded") or st.get("ollama_reachable"):
            return True
        if st.get("ram_phase") in ("loading", "ready", "pending"):
            return True
    except Exception:
        pass
    return False


def _qwen_ram_load_active() -> bool:
    try:
        from modules import local_qwen as lq
        from modules import qwen_embedded as qe

        if not lq.is_qwen_ram_enabled():
            return False
        if qe.inference_ready():
            return False
        st = lq.get_qwen_status()
        if st.get("embedded_ready"):
            return False
        ram = st.get("ram_phase") or ""
        if ram in ("loading", "pending"):
            return True
        if st.get("status") in ("loading_ram", "pending_ram"):
            return True
        if ram == "skipped" and st.get("ollama_reachable") and not st.get("ready"):
            return True
    except Exception:
        pass
    return False


def _expected_qwen_rss_bytes() -> int:
    try:
        from modules import qwen_embedded as qe

        if qe.model_present():
            return int(qe.model_path().stat().st_size * 0.88)
    except Exception:
        pass
    return 8_500_000_000


def list_jarvis_processes() -> list[dict[str, Any]]:
    """Список процессов, связанных с Jarvis (для UI и отладки)."""
    root = psutil.Process(os.getpid())
    seen: dict[int, dict[str, Any]] = {}

    def add(proc: psutil.Process, *, is_root: bool = False, is_child: bool = False) -> None:
        try:
            pid = proc.pid
            if pid in seen:
                return
            rss = _process_rss(proc)
            if rss <= 0:
                return
            name = _process_name(proc)
            cmd = _cmdline_text(proc)
            seen[pid] = {
                "pid": pid,
                "name": name,
                "role": _process_role(name, cmd, is_root=is_root, is_child=is_child),
                "rss_bytes": rss,
                "rss_mb": round(rss / (1024 * 1024), 1),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return

    add(root, is_root=True)
    for child in root.children(recursive=True):
        add(child, is_child=True)

    if _should_count_ollama():
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if not name.startswith("ollama"):
                    continue
                add(psutil.Process(int(proc.info["pid"])))
            except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, ValueError):
                continue

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = int(proc.info["pid"])
            if pid in seen:
                continue
            name = (proc.info.get("name") or "").lower()
            if not name.startswith("python"):
                continue
            p = psutil.Process(pid)
            if _is_jarvis_python(p, root):
                add(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied, KeyError, ValueError):
            continue

    return sorted(seen.values(), key=lambda x: x["rss_bytes"], reverse=True)


def get_ram_snapshot() -> dict[str, Any]:
    global _load_baseline_rss

    vm = psutil.virtual_memory()
    total = int(vm.total)
    processes = list_jarvis_processes()
    jarvis_rss = sum(int(p["rss_bytes"]) for p in processes)
    pids = {int(p["pid"]) for p in processes}

    loading_active = _qwen_ram_load_active()
    if loading_active:
        if _load_baseline_rss is None:
            _load_baseline_rss = max(jarvis_rss, _MIN_RSS_LAUNCHED_BYTES)
    else:
        _load_baseline_rss = None

    load_target_bytes = _expected_qwen_rss_bytes() if loading_active else 0
    load_progress = 0
    if loading_active and _load_baseline_rss is not None and load_target_bytes > 0:
        span = max(50 * 1024 * 1024, load_target_bytes - _load_baseline_rss)
        load_progress = min(
            99,
            max(0, int((jarvis_rss - _load_baseline_rss) * 100 / span)),
        )

    elapsed = time.monotonic() - _SERVER_STARTED_AT
    launching = elapsed < _LAUNCH_GRACE_SEC and jarvis_rss < _MIN_RSS_LAUNCHED_BYTES

    percent = 0
    if total > 0 and not launching:
        percent = max(0, min(100, int(round(jarvis_rss * 100 / total))))

    mb = 1024 * 1024
    return {
        "jarvis_rss_bytes": jarvis_rss,
        "jarvis_rss_mb": round(jarvis_rss / mb, 1),
        "total_ram_bytes": total,
        "total_ram_mb": round(total / mb),
        "jarvis_percent_of_total": percent,
        "system_used_percent": int(vm.percent),
        "system_used_mb": round(int(vm.used) / mb),
        "process_count": len(pids),
        "launching": launching,
        "services_active": not launching and jarvis_rss > 0,
        "processes": processes[:10],
        "qwen_ram_loading": loading_active,
        "load_target_mb": round(load_target_bytes / mb) if load_target_bytes else 0,
        "load_progress_percent": load_progress,
        "load_baseline_mb": round((_load_baseline_rss or 0) / mb, 1),
    }
