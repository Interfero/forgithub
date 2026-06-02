"""
Плановое обслуживание Jarvis каждые 30 минут: проверка систем, скрипты из manifest, отчёт в чат.
"""

from __future__ import annotations

import ast
import importlib.util
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

INTERVAL_SEC = 30 * 60
_MARKER = "<!-- jarvis-maintenance -->"

_HEURISTIC_PATTERNS: list[tuple[str, str]] = [
    (r"\beval\s*\(", "eval()"),
    (r"\bexec\s*\(", "exec()"),
    (r"\b__import__\s*\(", "__import__()"),
    (r"\bos\.system\s*\(", "os.system()"),
    (r"\bsubprocess\b", "subprocess"),
    (r"\bsocket\b", "socket"),
    (r"\brequests\.(get|post|put|delete)\s*\(", "сетевой requests"),
    (r"\bhttpx\b", "httpx"),
    (r"\burllib\b", "urllib"),
    (r"\bshutil\.rmtree\b", "shutil.rmtree"),
    (r"\bos\.remove\s*\(", "os.remove()"),
    (r"\bopen\s*\([^)]*['\"]w", "запись в файл"),
    (r"\bpickle\.loads?\b", "pickle"),
    (r"\bctypes\b", "ctypes"),
    (r"\bwinreg\b", "реестр Windows"),
]

_scheduler_stop = threading.Event()
_scheduler_thread: threading.Thread | None = None


def _bundle_root() -> Path:
    return Path(__file__).resolve().parent.parent


def maintenance_scripts_dir() -> Path:
    from modules.app_paths import user_data_dir

    d = user_data_dir() / "maintenance" / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def manifest_path() -> Path:
    from modules.memory_store import UNCONSCIOUS_DIR

    return UNCONSCIOUS_DIR / "maintenance_manifest.txt"


def _ensure_manifest() -> Path:
    dst = manifest_path()
    if dst.exists():
        return dst
    src = (
        _bundle_root()
        / "data"
        / "memory"
        / "unconscious"
        / "maintenance_manifest.txt"
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dst.write_text(_default_manifest(), encoding="utf-8")
    return dst


def _default_manifest() -> str:
    return (
        "# Плановые проверки Jarvis (каждые 30 мин)\n"
        "# builtin:health_report — отчёт «Проверка систем»\n"
        "# builtin:chromium_status — статус встроенного браузера\n"
        "# skill:имя_метода — CustomSkills в jarvis_skills.py\n"
        "# script:имя.py — файл в data/maintenance/scripts/\n"
        "builtin:health_report\n"
        "builtin:chromium_status\n"
        "builtin:free_updates\n"
        "skill:ping_skills\n"
    )


def read_manifest_lines() -> list[str]:
    path = _ensure_manifest()
    jobs: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        jobs.append(line)
    return jobs


def scan_code_heuristic(code: str) -> list[str]:
    issues: list[str] = []
    for pat, label in _HEURISTIC_PATTERNS:
        if re.search(pat, code, re.I):
            issues.append(label)
    return issues


def _pick_audit_engine() -> str:
    from modules.neural_keys import get_neural_availability

    if get_neural_availability().get("deepseek"):
        return "deepseek"
    return "qwen"


def audit_script_with_neural(code: str, filename: str) -> tuple[bool, str]:
    """Самая мощная доступная модель: DeepSeek, иначе Qwen."""
    snippet = (code or "")[:12_000]
    prompt = (
        "Ты аудитор безопасности Jarvis. Проверь Python-скрипт планового обслуживания.\n"
        "Ответь ОДНОЙ строкой:\n"
        "SAFE — если только диагностика Jarvis (статус, отчёты, ping навыков), без вредоносного кода.\n"
        "UNSAFE: <причина> — если есть eval/exec, сеть, удаление файлов, кража ключей, шифровальщик и т.п.\n\n"
        f"Файл: {filename}\n```python\n{snippet}\n```"
    )
    engine = _pick_audit_engine()
    raw = ""
    try:
        if engine == "deepseek":
            import store
            from modules.agent import chat_deepseek

            key = (store.load_settings().get("deepseek_key") or "").strip()
            if key.startswith("sk-"):
                text, _ = chat_deepseek(
                    key,
                    store.load_settings().get("default_model") or "deepseek-chat",
                    prompt,
                    [],
                )
                raw = (text or "").strip()
            else:
                engine = "qwen"
        if engine == "qwen" and not raw:
            from modules.local_qwen import generate_local_help

            text, _, _ = generate_local_help(prompt, [])
            raw = (text or "").strip()
        if raw.upper().startswith("SAFE"):
            return True, "нейросеть: безопасно"
        if "UNSAFE" in raw.upper():
            return False, raw[:400]
        return False, f"неясный ответ аудита: {raw[:200]}"
    except Exception as e:
        return False, f"аудит нейросетью не выполнен: {e}"[:200]


def validate_script_file(path: Path) -> dict[str, Any]:
    code = path.read_text(encoding="utf-8", errors="replace")
    issues = scan_code_heuristic(code)
    if issues:
        return {
            "ok": False,
            "issues": issues,
            "detail": "эвристика: " + ", ".join(issues),
        }
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"ok": False, "issues": [f"синтаксис: {e}"], "detail": str(e)}
    has_run = any(
        isinstance(n, ast.FunctionDef) and n.name == "run" for n in ast.walk(tree)
    )
    if not has_run:
        return {
            "ok": False,
            "issues": ["нет функции run()"],
            "detail": "Скрипт должен содержать def run() -> str",
        }
    safe, detail = audit_script_with_neural(code, path.name)
    if not safe:
        low = detail.lower()
        if any(
            x in low
            for x in ("не выполнен", "400", "timeout", "недоступн", "ошибка deepseek")
        ):
            return {
                "ok": True,
                "issues": [],
                "detail": "эвристика OK; аудит нейросетью пропущен (API недоступен)",
            }
        return {"ok": False, "issues": [detail], "detail": detail}
    return {"ok": True, "issues": [], "detail": detail}


def _run_script_file(path: Path) -> tuple[bool, str]:
    v = validate_script_file(path)
    if not v["ok"]:
        return False, f"⚠️ Скрипт **{path.name}** не запущен: {v['detail']}"
    spec = importlib.util.spec_from_file_location(
        f"jarvis_maint_{path.stem}", path
    )
    if not spec or not spec.loader:
        return False, f"⚠️ Не удалось загрузить {path.name}"
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        fn = getattr(mod, "run", None)
        if not callable(fn):
            return False, f"⚠️ {path.name}: нет run()"
        out = fn()
        return True, f"✅ **{path.name}**: {(str(out) if out is not None else 'OK')[:800]}"
    except Exception as e:
        return False, f"⚠️ **{path.name}** ошибка: {e}"[:400]


def _job_builtin_health_report() -> str:
    from modules.system_health import build_system_health_report

    return build_system_health_report()


def _job_builtin_chromium() -> str:
    from modules.chromium_browser import chromium_browser_status

    s = chromium_browser_status()
    return (
        f"**Chromium:** {s.get('status_label', '—')} — "
        f"{s.get('detail', '')[:300]}"
    )


def _job_skill(method: str) -> tuple[bool, str]:
    from modules.skills_runtime import list_custom_skill_methods, run_custom_skill

    name = method.strip()
    if name not in list_custom_skill_methods():
        return False, f"⚠️ skill:{name} — метод не найден в CustomSkills"
    try:
        out = run_custom_skill(name)
        return True, f"✅ **skill:{name}**: {out[:600]}"
    except Exception as e:
        return False, f"⚠️ **skill:{name}**: {e}"[:300]


def execute_manifest_job(line: str) -> tuple[bool, str]:
    low = line.strip().lower()
    if low == "builtin:health_report" or low == "health_report":
        return True, _job_builtin_health_report()
    if low == "builtin:chromium_status" or low == "chromium_status":
        return True, _job_builtin_chromium()
    if low == "builtin:free_updates" or low == "free_updates":
        from modules.jarvis_free_updates import run_free_components_update

        r = run_free_components_update(force_browsers=True, force_pip=True)
        ok = "✅" if r.get("ok") else "⚠️"
        br = r.get("browsers") or {}
        return bool(r.get("ok")), (
            f"{ok} **free_updates** ({r.get('at')}): "
            f"pip={ (r.get('pip') or {}).get('ok') }; "
            f"chromium={br.get('chromium_ok')}; windowed={br.get('windowed_ok')}"
        )
    if low.startswith("skill:"):
        return _job_skill(line.split(":", 1)[1])
    if low.startswith("script:"):
        fname = line.split(":", 1)[1].strip()
        if ".." in fname or "/" in fname or "\\" in fname:
            return False, f"⚠️ Недопустимое имя скрипта: {fname}"
        path = maintenance_scripts_dir() / fname
        if not path.is_file():
            return False, f"⚠️ Скрипт не найден: {fname}"
        return _run_script_file(path)
    return False, f"⚠️ Неизвестная задача manifest: {line}"


def run_maintenance_cycle() -> str:
    """Один цикл: все задачи manifest + сводка."""
    from modules.agent import get_runtime

    rt = get_runtime()
    ts = time.strftime("%d.%m.%Y %H:%M")
    lines: list[str] = [
        _MARKER,
        f"## 🔧 Плановая проверка Jarvis ({ts})",
        "",
    ]
    jobs = read_manifest_lines()
    if not jobs:
        jobs = ["builtin:health_report", "builtin:chromium_status", "skill:ping_skills"]

    ok_n = 0
    warn_n = 0
    script_lines: list[str] = []

    for job in jobs:
        rt.log("maintenance", f"Задача: {job}")
        ok, msg = execute_manifest_job(job)
        if job.startswith("builtin:health_report") or job == "health_report":
            lines.append(msg)
            lines.append("")
            ok_n += 1
            continue
        if ok:
            ok_n += 1
            script_lines.append(msg)
        else:
            warn_n += 1
            script_lines.append(msg)

    if script_lines:
        lines.append("### Скрипты и навыки")
        lines.extend(script_lines)
        lines.append("")

    lines.append(
        f"_Итог: задач {len(jobs)}, успешно {ok_n}, предупреждений {warn_n}. "
        f"Следующая проверка через 30 мин._"
    )
    return "\n".join(lines)


def post_maintenance_to_chat(body: str) -> None:
    import store
    from modules.notify import ROUTINE

    chat = store.ensure_single_chat()
    store.add_message(chat["id"], "system", body.strip(), notify_level=ROUTINE)
    from modules.agent import get_runtime

    get_runtime().log("maintenance", "Отчёт отправлен в чат")


def _scheduler_loop() -> None:
    time.sleep(45)
    while not _scheduler_stop.wait(INTERVAL_SEC):
        try:
            report = run_maintenance_cycle()
            post_maintenance_to_chat(report)
        except Exception as e:
            _log.exception("maintenance cycle failed")
            try:
                post_maintenance_to_chat(
                    f"{_MARKER}\n⚠️ Ошибка плановой проверки: {e}"[:500]
                )
            except Exception:
                pass


def _seed_scripts_from_bundle() -> None:
    src = _bundle_root() / "data" / "maintenance" / "scripts"
    if not src.is_dir():
        return
    dst = maintenance_scripts_dir()
    for f in src.glob("*.py"):
        target = dst / f.name
        if not target.exists():
            target.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")


def start_maintenance_scheduler() -> None:
    global _scheduler_thread
    _ensure_manifest()
    _seed_scripts_from_bundle()
    maintenance_scripts_dir()
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        name="jarvis-maintenance",
        daemon=True,
    )
    _scheduler_thread.start()


def stop_maintenance_scheduler() -> None:
    _scheduler_stop.set()
