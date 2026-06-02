"""
Техдокументация Jarvis, периодическое перечитывание, сохранение сессии в сознательное.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import signal
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

TECH_DOC_FILENAME = "Техдокументация.txt"
SESSION_MEMORY_FILENAME = "Память_сессий.md"
DOC_READ_INTERVAL_SEC = 600  # 10 минут

_bundle_doc = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "memory"
    / "conscious"
    / TECH_DOC_FILENAME
)

_last_doc_read_at: str | None = None
_last_doc_read_lock = threading.Lock()
_scheduler_stop = threading.Event()
_scheduler_thread: threading.Thread | None = None
_shutdown_hooks_registered = False

_boot_state: dict = {
    "messages_cleared_on_boot": 0,
    "recovered_unclean_shutdown": False,
    "boot_id": "",
}


def _runtime_marker_path() -> Path:
    from modules.app_paths import user_data_dir

    return user_data_dir() / "server_runtime.json"


def _read_runtime_marker() -> dict:
    path = _runtime_marker_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_runtime_marker(**fields) -> None:
    path = _runtime_marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_runtime_marker()
    data.update(fields)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_shutdown_hooks() -> None:
    """Пометить корректное завершение (atexit / сигналы) для get_startup_info."""
    global _shutdown_hooks_registered
    if _shutdown_hooks_registered:
        return
    _shutdown_hooks_registered = True

    def _mark_clean_exit() -> None:
        try:
            _write_runtime_marker(clean_shutdown=True, running=False)
        except Exception:
            pass

    atexit.register(_mark_clean_exit)

    def _on_signal(_signum: int, _frame) -> None:
        _mark_clean_exit()

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is None:
            continue
        try:
            signal.signal(sig, _on_signal)
        except Exception:
            pass
    if hasattr(signal, "SIGBREAK"):
        try:
            signal.signal(signal.SIGBREAK, _on_signal)
        except Exception:
            pass


def on_app_startup() -> dict:
    """
    При запуске сервера: сохранить важное из чата в сознательное и очистить диалог.
    F5 в браузере чат не трогает — только рестарт backend.
    """
    global _boot_state
    prev = _read_runtime_marker()
    unclean = bool(prev.get("running")) and not bool(prev.get("clean_shutdown", True))

    import store

    chat = store.ensure_single_chat()
    messages = list(chat.get("messages") or [])
    n_before = len(messages)
    if messages:
        append_session_memory_to_conscious(messages)
        store.reset_chats_storage()
        clear_ephemeral_cache()

    boot_id = str(uuid.uuid4())
    _boot_state = {
        "messages_cleared_on_boot": n_before,
        "recovered_unclean_shutdown": unclean,
        "boot_id": boot_id,
    }
    _write_runtime_marker(
        pid=os.getpid(),
        boot_id=boot_id,
        clean_shutdown=False,
        running=True,
        started_at=_now_local(),
    )
    return dict(_boot_state)


def get_startup_info() -> dict:
    return dict(_boot_state)


def _now_local() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")


def ensure_tech_documentation() -> Path:
    """Создать/обновить Техдокументация.txt в сознательном из bundle."""
    from modules.memory_store import CONSCIOUS_DIR, add_file, is_protected

    CONSCIOUS_DIR.mkdir(parents=True, exist_ok=True)
    dst = CONSCIOUS_DIR / TECH_DOC_FILENAME
    src = _bundle_doc
    if src.is_file():
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)
    elif not dst.exists():
        add_file("conscious", TECH_DOC_FILENAME, _minimal_tech_doc().encode("utf-8"))
    try:
        from modules import jarvis_db

        jarvis_db.sync_all_from_disk()
    except Exception:
        pass
    return dst


def read_tech_documentation(max_chars: int = 24000) -> str:
    ensure_tech_documentation()
    from modules.memory_store import read_file

    row = read_file("conscious", TECH_DOC_FILENAME)
    if row and row.get("content"):
        text = row["content"]
        if len(text) > max_chars:
            return text[:max_chars] + "\n…"
        return text
    if _bundle_doc.is_file():
        return _bundle_doc.read_text(encoding="utf-8", errors="replace")[:max_chars]
    return ""


def mark_tech_doc_read() -> str:
    global _last_doc_read_at
    with _last_doc_read_lock:
        _last_doc_read_at = _now_local()
        ts = _last_doc_read_at
    from modules.agent import get_runtime

    get_runtime().log("docs", f"Перечитана {TECH_DOC_FILENAME}")
    try:
        from modules import jarvis_db

        jarvis_db.set_cell(
            mode_code=None,
            cell_key="tech_doc_last_read",
            content=ts,
            namespace="system",
        )
    except Exception:
        pass
    return ts


def get_tech_doc_prompt_hint() -> str:
    """Краткая отсылка для системного промпта."""
    with _last_doc_read_lock:
        ts = _last_doc_read_at
    doc = read_tech_documentation(max_chars=16000)
    if not doc.strip():
        return ""
    hint = (
        "\n\n---\n[Техдокументация Jarvis — обязательно знай возможности системы]\n"
        "Файл «Техдокументация.txt» в **Сознательном** описывает, из чего состоит Jarvis "
        "и что ты умеешь (§14). На «что ты умеешь» — факты из документации и "
        "`jarvis_capabilities_summary_for_user`, без выдуманного календаря/погоды/умного дома. "
        "Не выдумывай bash-команды.\n"
        "Ответы в чате — **абзацы** (пустая строка между блоками), списки с переносами строк.\n"
    )
    if ts:
        hint += f"Последнее перечитывание документации: {ts}.\n"
    hint += f"\n{doc}\n"
    return hint


def _doc_scheduler_loop() -> None:
    while not _scheduler_stop.wait(DOC_READ_INTERVAL_SEC):
        try:
            read_tech_documentation(max_chars=8000)
            mark_tech_doc_read()
        except Exception:
            pass


def start_doc_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    mark_tech_doc_read()
    _scheduler_thread = threading.Thread(
        target=_doc_scheduler_loop,
        name="jarvis-doc-reader",
        daemon=True,
    )
    _scheduler_thread.start()


def stop_doc_scheduler() -> None:
    _scheduler_stop.set()


def clear_ephemeral_cache() -> None:
    """Временные файлы и RAM-кеш сессии (не трогает сознательное и бизнес-БД)."""
    from modules.agent import get_runtime
    from modules.app_paths import user_data_dir

    rt = get_runtime()
    rt.uploaded_docs.clear()
    rt.tool_logs.clear()
    rt.session_tokens = 0

    data = user_data_dir()
    for sub in ("files", "voice/generated", "telephony/cache"):
        d = data / sub.replace("/", "\\").replace("\\", "/")
        if not d.exists():
            d = data / Path(sub)
        if d.is_dir():
            for p in d.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                except OSError:
                    pass


def _format_messages_for_llm(messages: list[dict], limit: int = 40) -> str:
    lines: list[str] = []
    for m in messages[-limit:]:
        role = m.get("role") or "?"
        text = (m.get("content") or "").strip().replace("\n", " ")
        if not text:
            continue
        if len(text) > 500:
            text = text[:497] + "…"
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def _extract_facts_heuristic(messages: list[dict]) -> str:
    bullets: list[str] = []
    seen: set[str] = set()
    for m in messages:
        if m.get("role") != "user":
            continue
        t = (m.get("content") or "").strip()
        if not t or len(t) < 8:
            continue
        low = t.lower()
        if any(
            w in low
            for w in (
                "запомни",
                "важно",
                "настрой",
                "предпочита",
                "всегда",
                "никогда",
                "инн",
                "авито",
                "телеграм",
            )
        ):
            key = t[:80]
            if key in seen:
                continue
            seen.add(key)
            bullets.append(f"- {t[:400]}")
        if len(bullets) >= 12:
            break
    if not bullets:
        for m in messages[-6:]:
            if m.get("role") == "user":
                t = (m.get("content") or "").strip()
                if t:
                    bullets.append(f"- {t[:200]}")
    return "\n".join(bullets[:12])


def _extract_facts_llm(messages: list[dict]) -> str | None:
    body = _format_messages_for_llm(messages)
    if not body.strip():
        return None
    prompt = (
        "Из переписки пользователя (Шеф) с Jarvis выдели 5–12 кратких фактов для долгой памяти: "
        "предпочтения, настройки, важные договорённости, контакты, задачи. "
        "Только маркированный список на русском, без вступлений.\n\n"
        f"{body}"
    )
    try:
        import store
        from modules.agent import chat_deepseek, get_mode
        from modules.local_qwen import generate_local_help

        settings = store.load_settings()
        key = (settings.get("deepseek_key") or "").strip()
        if key.startswith("sk-"):
            reply, _ = chat_deepseek(
                key,
                settings.get("default_model") or "deepseek-chat",
                prompt,
                [],
            )
            if reply and reply.strip():
                return reply.strip()[:4000]
        text, _, _ = generate_local_help(prompt, history=None)
        if text and text.strip():
            return text.strip()[:4000]
    except Exception:
        return None
    return None


def append_session_memory_to_conscious(messages: list[dict]) -> None:
    """Сохранить важное из чата в сознательное перед сбросом."""
    if not messages:
        return
    facts = _extract_facts_llm(messages) or _extract_facts_heuristic(messages)
    if not facts.strip():
        return
    from modules.memory_store import CONSCIOUS_DIR

    CONSCIOUS_DIR.mkdir(parents=True, exist_ok=True)
    path = CONSCIOUS_DIR / SESSION_MEMORY_FILENAME
    block = f"\n\n## Сессия {_now_local()}\n{facts.strip()}\n"
    if path.exists():
        old = path.read_text(encoding="utf-8", errors="replace")
        if len(old) > 120_000:
            old = old[-80_000:]
        path.write_text(old + block, encoding="utf-8")
    else:
        path.write_text(
            "# Память сессий Jarvis\n"
            "Автоматически сохранённые факты перед выключением (не удалять вручную без нужды).\n"
            + block,
            encoding="utf-8",
        )
    try:
        from modules import jarvis_db

        jarvis_db.sync_all_from_disk()
    except Exception:
        pass


def on_app_shutdown() -> None:
    """Перед остановкой сервера: анализ чата → сознательное → сброс чата и кеша."""
    try:
        _write_runtime_marker(clean_shutdown=True, running=False)
    except Exception:
        pass
    import store

    try:
        chat = store.ensure_single_chat()
        messages = list(chat.get("messages") or [])
        append_session_memory_to_conscious(messages)
    except Exception:
        pass
    try:
        store.reset_chats_storage()
    except Exception:
        pass
    clear_ephemeral_cache()


def probe_web_search() -> tuple[str, str]:
    """
    Устаревший общий вызов — для совместимости.
    Используйте probe_web_stack_parts() в отчёте «Проверка систем».
    """
    parts = probe_web_stack_parts()
    if not parts:
        return "warn", "Проверка веб-модулей не выполнена"
    levels = [p[0] for p in parts]
    if "err" in levels:
        level = "err"
    elif all(lv == "ok" for lv in levels):
        level = "ok"
    else:
        level = "warn"
    detail = " · ".join(p[2] for p in parts)
    return level, detail[:140]


def probe_web_stack_parts() -> list[tuple[str, str, str]]:
    """
    Отдельные строки отчёта: (level, название компонента, деталь).
    Поиск и браузеры не смешиваются — без обрезанных URL и «Chromium OK» при падении DDG.
    """
    from modules.web_search import probe_duckduckgo_search, probe_jarvis_browsers

    ddg_lv, ddg_det = probe_duckduckgo_search()
    br_lv, br_det = probe_jarvis_browsers()
    return [
        (ddg_lv, "DuckDuckGo (поиск)", ddg_det),
        (br_lv, "Браузеры Jarvis", br_det),
    ]


def _minimal_tech_doc() -> str:
    return (
        "# Техдокументация Jarvis\n"
        "Полная версия создаётся при установке. Запустите start.bat или положите файл "
        "Техдокументация.txt в папку memory/conscious.\n"
    )
