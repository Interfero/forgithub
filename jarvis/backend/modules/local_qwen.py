"""
Локальная нейросеть Qwen 2.5 14B — встроенная GGUF в data/models (приоритет) или Ollama (запас).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import httpx

from modules import qwen_embedded as qe

MODEL_LABEL = qe.MODEL_LABEL
# Запасной Ollama, если встроенный llama-cpp не поднялся на этом CPU
USE_OLLAMA_FALLBACK = os.getenv("JARVIS_QWEN_USE_OLLAMA", "1").strip().lower() not in (
    "0",
    "false",
    "no",
)
OLLAMA_BASE = os.getenv("JARVIS_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("JARVIS_QWEN_OLLAMA_MODEL", "qwen2.5:14b")
OLLAMA_JARVIS_MODEL = os.getenv("JARVIS_QWEN_OLLAMA_LOCAL", "jarvis-qwen14b")
_ollama_gguf_register_lock = threading.Lock()
_ollama_gguf_register_done = False

_qwen_download_thread: threading.Thread | None = None
_qwen_download_proc: subprocess.Popen | None = None
_qwen_download_lock = threading.Lock()

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODEL_SEARCH_ROOTS = [
    _BACKEND_ROOT / "data" / "models",
    _BACKEND_ROOT / "models",
    Path(os.getenv("JARVIS_QWEN_MODEL_DIR", "")).expanduser(),
]

FILE_GLOBS = (
    "*qwen*2.5*14b*",
    "*Qwen*2.5*14B*",
    "*qwen2.5*14b*",
)
WEIGHT_SUFFIXES = {".gguf", ".safetensors", ".bin", ".pt"}

_QWEN_NAME_RE = re.compile(r"qwen\s*2\.?5.*14\s*b", re.I)


def _qwen_meta_without_file() -> bool:
    """Метаданные установки есть, но GGUF удалён или перемещён."""
    if qe.model_present():
        return False
    return qe.META_PATH.is_file()


def _qwen_download_thread_alive() -> bool:
    t = _qwen_download_thread
    return t is not None and t.is_alive()


def _qwen_download_proc_running() -> bool:
    global _qwen_download_proc
    proc = _qwen_download_proc
    if proc is None:
        return False
    if proc.poll() is None:
        return True
    _qwen_download_proc = None
    return False


def _qwen_download_job_active() -> bool:
    if _qwen_download_proc_running() or _qwen_download_thread_alive():
        return True
    return qe.get_download_status().get("phase") == "downloading"


def _qwen_download_log_path() -> Path:
    log_dir = _BACKEND_ROOT.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "qwen-ui-download.log"


def _watch_qwen_download_proc(proc: subprocess.Popen) -> None:
    """После завершения subprocess — обновить статус для UI."""
    global _qwen_download_proc
    try:
        code = proc.wait()
    except Exception:
        code = -1
    with _qwen_download_lock:
        if _qwen_download_proc is proc:
            _qwen_download_proc = None
    if code == 0 or qe.model_present():
        return
    tail = ""
    try:
        log = _qwen_download_log_path()
        if log.is_file():
            text = log.read_text(encoding="utf-8", errors="replace")
            tail = "\n".join(text.strip().splitlines()[-4:])[:200]
    except Exception:
        pass
    msg = f"Загрузка остановилась (код {code})."
    if tail:
        msg += f" {tail}"
    else:
        msg += " См. logs/qwen-ui-download.log или install-qwen.bat"
    qe.mark_download_error(msg)


def _spawn_qwen_download_subprocess() -> tuple[bool, str]:
    """Отдельный процесс Python — как install-qwen.bat."""
    venv_py = _BACKEND_ROOT / "venv" / "Scripts" / "python.exe"
    script = _BACKEND_ROOT / "scripts" / "download_qwen_model.py"
    if not venv_py.is_file():
        return False, "Нет backend\\venv\\Scripts\\python.exe — сначала start.bat"
    if not script.is_file():
        return False, "Не найден backend\\scripts\\download_qwen_model.py"

    global _qwen_download_proc
    log_path = _qwen_download_log_path()
    try:
        log_handle = log_path.open("a", encoding="utf-8")
        log_handle.write(
            f"\n=== UI download {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        )
        log_handle.flush()
    except OSError as e:
        return False, f"Не удалось открыть лог: {e}"

    popen_kw: dict = {
        "cwd": str(_BACKEND_ROOT),
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        _qwen_download_proc = subprocess.Popen(
            [str(venv_py), str(script)],
            **popen_kw,
        )
        threading.Thread(
            target=_watch_qwen_download_proc,
            args=(_qwen_download_proc,),
            name="jarvis-qwen-download-watch",
            daemon=True,
        ).start()
        return True, ""
    except OSError as e:
        _qwen_download_proc = None
        try:
            log_handle.close()
        except Exception:
            pass
        return False, str(e)[:200]


def _matches_qwen_name(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return False
    if _QWEN_NAME_RE.search(n):
        return True
    low = n.lower()
    return "qwen" in low and "2.5" in low and "14b" in low


def _scan_model_files() -> tuple[bool, str | None, int, list[str]]:
    """Ищет веса/каталоги Qwen 2.5 14B в типичных путях Jarvis."""
    found: list[Path] = []
    for root in MODEL_SEARCH_ROOTS:
        if not root or not root.is_dir():
            continue
        for pattern in FILE_GLOBS:
            for p in root.rglob(pattern):
                if p.is_file() and p.suffix.lower() in WEIGHT_SUFFIXES:
                    found.append(p)
                elif p.is_dir() and _matches_qwen_name(p.name):
                    for w in p.rglob("*"):
                        if w.is_file() and w.suffix.lower() in WEIGHT_SUFFIXES:
                            found.append(w)
                            if len(found) >= 8:
                                break
        if found:
            break

    if not found:
        return False, None, 0, []

    total = sum(p.stat().st_size for p in found)
    primary = found[0]
    rel = str(primary.relative_to(primary.anchor)) if primary.anchor else str(primary)
    names = sorted({p.name for p in found[:6]})
    return True, rel, total, names


def is_qwen_ram_enabled() -> bool:
    import store

    return bool(store.load_settings().get("qwen_ram_enabled", False))


def set_qwen_ram_enabled(enabled: bool) -> dict:
    import store
    from modules import poll_throttle

    store.save_settings({"qwen_ram_enabled": bool(enabled)})
    poll_throttle.invalidate_ollama_cache()
    if enabled:
        if qe.model_present() and qe.llama_importable():
            qe.start_ram_load_async()
    else:
        qe.unload_from_ram()
    return get_qwen_status()


def _check_ollama() -> tuple[bool, bool, str | None, str | None]:
    """(сервер доступен, модель в списке, имя модели, ошибка)."""
    try:
        with httpx.Client(timeout=3.0, trust_env=False) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code != 200:
                return False, False, None, f"Ollama HTTP {r.status_code}"
            models = r.json().get("models") or []
            names: list[str] = []
            for m in models:
                n = (m.get("name") or "").strip()
                if n:
                    names.append(n)
            for preferred in (OLLAMA_JARVIS_MODEL, OLLAMA_MODEL):
                if preferred in names or f"{preferred}:latest" in names:
                    return True, True, preferred, None
            for n in names:
                if _matches_qwen_name(n):
                    return True, True, n, None
            if names:
                return True, False, None, None
            return True, False, None, "В Ollama нет загруженных моделей"
    except httpx.ConnectError:
        return False, False, None, "Ollama не запущен (127.0.0.1:11434)"
    except Exception as e:
        return False, False, None, str(e)[:120]


def get_qwen_status() -> dict:
    embedded_file = qe.embedded_file_installed()
    embedded_path = str(qe.model_path()) if embedded_file else None
    embedded_bytes = qe.model_path().stat().st_size if embedded_file else 0
    llama_ok = qe.llama_importable()
    embedded_ready = qe.inference_ready()
    download = qe.get_download_status()
    ram = qe.get_ram_status()

    files_ok, files_path, files_bytes, file_names = _scan_model_files()
    if embedded_file:
        files_ok = True
        files_path = embedded_path
        files_bytes = embedded_bytes
        file_names = [qe.MODEL_FILENAME]

    from modules import poll_throttle

    ram_enabled = is_qwen_ram_enabled()
    # Индикатор: проверяем Ollama, если GGUF на диске (даже при выкл. «ОЗУ» — иначе «Выключено» при живом Ollama).
    ollama_probe = bool(embedded_file) or ram_enabled
    ollama_up, model_loaded, model_name, ollama_err = poll_throttle.get_cached_ollama_status(
        keys_configured=ollama_probe,
        probe=_check_ollama,
    )
    if (
        ram_enabled
        and embedded_file
        and USE_OLLAMA_FALLBACK
        and (qe.llama_cpu_blocked() or not model_loaded)
        and ollama_probe
    ):
        ensure_ollama_running()
        register_ollama_from_embedded_gguf()
        poll_throttle.invalidate_ollama_cache()
        ollama_up, model_loaded, model_name, ollama_err = poll_throttle.get_cached_ollama_status(
            keys_configured=True,
            probe=_check_ollama,
        )

    if (
        not ram_enabled
        and embedded_file
        and USE_OLLAMA_FALLBACK
        and not model_loaded
        and ollama_probe
    ):
        ensure_ollama_running()
        register_ollama_from_embedded_gguf()
        poll_throttle.invalidate_ollama_cache()
        ollama_up, model_loaded, model_name, ollama_err = poll_throttle.get_cached_ollama_status(
            keys_configured=True,
            probe=_check_ollama,
        )

    engine = "off"

    if download.get("phase") == "downloading":
        ready = False
        engine = "downloading"
        status = "downloading"
        pct = int(download.get("progress") or 0)
        status_label = f"Скачивание {pct}%"
        variant_hint = "warning"
        message = download.get("message") or "Скачивание модели внутрь Jarvis…"
        value = f"{pct}%"
    elif download.get("phase") == "error":
        ready = False
        engine = "need_download"
        status = "need_download"
        status_label = "Ошибка"
        variant_hint = "destructive"
        message = download.get("message") or "Не удалось скачать модель"
        value = "Ошибка"
    elif embedded_ready:
        engine = "embedded"
        ready = True
        status = "ready"
        status_label = "В Jarvis"
        variant_hint = "success"
        message = (
            f"{MODEL_LABEL} внутри Jarvis "
            f"({_format_size(embedded_bytes)}, папка backend/data/models приложения)"
        )
        value = MODEL_LABEL
    elif embedded_file and USE_OLLAMA_FALLBACK and model_loaded:
        engine = "ollama_runtime"
        ready = True
        status = "ready"
        status_label = "Jarvis+Ollama"
        variant_hint = "success"
        message = (
            f"{MODEL_LABEL} через Ollama ({model_name or OLLAMA_JARVIS_MODEL}). "
            f"Файл в Jarvis ({_format_size(embedded_bytes)})."
            + (
                " llama-cpp на этом CPU недоступен — это нормально."
                if qe.llama_cpu_blocked()
                else ""
            )
        )
        value = MODEL_LABEL
    elif ram.get("phase") == "loading":
        ready = False
        engine = "loading_ram"
        status = "loading_ram"
        status_label = "В ОЗУ…"
        variant_hint = "warning"
        message = ram.get("message") or "Загрузка модели в память ПК…"
        value = "В ОЗУ…"
    elif embedded_file and not llama_ok:
        ready = False
        engine = "need_llama"
        status = "need_llama"
        status_label = "Нет движка"
        variant_hint = "warning"
        message = (
            "Файл модели в Jarvis на диске, но не установлен llama-cpp-python. "
            "Запустите start.bat заново."
        )
        value = "Файл OK"
    elif embedded_file and ram.get("phase") in ("pending", "skipped") and not model_loaded:
        ready = False
        engine = "pending_ram"
        status = "pending_ram"
        status_label = "Ollama…"
        variant_hint = "warning"
        message = ram.get("message") or "Подключение Ollama к модели из Jarvis…"
        value = "Ollama…"
    elif embedded_file and ram.get("phase") == "error":
        ensure_ollama_running()
        if USE_OLLAMA_FALLBACK:
            register_ollama_from_embedded_gguf()
            ollama_up, model_loaded, model_name, ollama_err = _check_ollama()
        if USE_OLLAMA_FALLBACK and model_loaded:
            engine = "ollama_runtime"
            ready = True
            status = "ready"
            status_label = "Jarvis+Ollama"
            variant_hint = "success"
            err = qe.get_load_error() or "CPU"
            message = (
                f"GGUF в Jarvis ({_format_size(embedded_bytes)}). "
                f"llama-cpp недоступен ({err[:60]}), работает Ollama: {model_name}."
            )
            value = MODEL_LABEL
        else:
            ready = False
            engine = "ram_error"
            status = "ram_error"
            status_label = "Файл OK"
            variant_hint = "warning"
            message = ram.get("message") or (
                "Модель скачана в Jarvis. Для этого CPU: установите Ollama и выполните "
                "`ollama pull qwen2.5:14b` (или перезапустите Jarvis — попробуем привязать GGUF)."
            )
            value = "Нужен Ollama"
    elif not embedded_file:
        ready = False
        engine = "need_download"
        status = "need_download"
        status_label = "Не скачана"
        variant_hint = "warning"
        if download.get("phase") == "downloading":
            pct = int(download.get("progress") or 0)
            status_label = f"Скачивание {pct}%"
            message = download.get("message") or "Скачивание в Jarvis…"
            value = f"{pct}%"
            engine = "downloading"
            status = "downloading"
        else:
            if _qwen_meta_without_file():
                message = (
                    "Файл модели отсутствует на диске (раньше был установлен ~9 ГБ). "
                    "Нажмите «Скачать модель» в настройках или install-qwen.bat."
                )
                value = "Файл удалён"
            else:
                message = (
                    "Модель ещё не скачана внутрь Jarvis (~9 ГБ → backend/data/models). "
                    "Нажмите «Скачать модель» в настройках или install-qwen.bat."
                )
                value = "Нет модели"
        if USE_OLLAMA_FALLBACK and model_loaded:
            engine = "ollama"
            ready = True
            status = "ollama_only"
            status_label = "Ollama"
            variant_hint = "success"
            message = f"Внешний Ollama: {model_name or OLLAMA_MODEL} (встроенная не скачана)"
            value = "Ollama"
    elif USE_OLLAMA_FALLBACK and model_loaded:
        engine = "ollama"
        ready = True
        status = "ollama_only"
        status_label = "Ollama"
        variant_hint = "warning"
        message = f"Запасной режим Ollama: {model_name}"
        value = "Ollama"
    else:
        ready = bool(model_loaded and USE_OLLAMA_FALLBACK)
        status = "off"
        status_label = "Не подключена"
        variant_hint = "muted"
        message = (
            "Запустите install-qwen.bat — модель скачается внутрь Jarvis "
            "(backend/data/models), не отдельно на ПК"
        )
        value = "Нет Qwen"

    ram_usable = bool(
        ram_enabled
        and (
            embedded_ready
            or (ready and status in ("ready", "ollama_runtime", "ollama_only"))
        )
    )

    return {
        "label": MODEL_LABEL,
        "status": status,
        "status_label": status_label,
        "variant_hint": variant_hint,
        "message": message,
        "value": value,
        "ready": ready,
        "ram_usable": ram_usable,
        "engine": engine,
        "embedded_ready": embedded_ready,
        "files_present": files_ok or embedded_file,
        "files_path": files_path,
        "files_bytes": embedded_bytes or files_bytes,
        "file_names": file_names,
        "ollama_base_url": OLLAMA_BASE,
        "ollama_reachable": ollama_up,
        "ollama_model_loaded": model_loaded,
        "ollama_model_name": model_name,
        "ollama_expected_model": OLLAMA_MODEL,
        "ollama_error": ollama_err,
        "download_phase": download.get("phase"),
        "download_progress": int(download.get("progress") or 0),
        "download_message": download.get("message") or "",
        "download_bytes_done": int(download.get("bytes_done") or 0),
        "download_bytes_total": int(download.get("bytes_total") or 0),
        "model_meta_stale": _qwen_meta_without_file(),
        "expected_model_path": str(qe.model_path()),
        "ram_phase": ram.get("phase"),
        "ram_progress": int(ram.get("progress") or 0),
        "ram_message": ram.get("message") or "",
        "ram_enabled": ram_enabled,
    }


def _format_size(n: int) -> str:
    if n >= 1024**3:
        return f"{n / 1024**3:.1f} ГБ"
    if n >= 1024**2:
        return f"{n / 1024**2:.0f} МБ"
    return f"{n / 1024:.0f} КБ"


def active_model_display_name() -> str:
    st = get_qwen_status()
    if st.get("embedded_ready"):
        return MODEL_LABEL
    if st["ready"] or st["ollama_model_loaded"]:
        return st.get("ollama_model_name") or MODEL_LABEL
    if st["files_present"]:
        return f"{MODEL_LABEL} (файл)"
    return "заглушка"


def qwen_available() -> bool:
    if is_qwen_ram_enabled() and qe.inference_ready():
        return True
    if USE_OLLAMA_FALLBACK and ollama_available():
        return True
    if (
        is_qwen_ram_enabled()
        and qe.embedded_file_installed()
        and USE_OLLAMA_FALLBACK
    ):
        ensure_ollama_running()
        return ollama_available()
    return False


def qwen_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
    timeout_sec: float = 90.0,
) -> tuple[str, int]:
    """Чат: встроенная GGUF в Jarvis → запасной Ollama при сбое llama-cpp."""
    if is_qwen_ram_enabled() and qe.inference_ready():
        try:
            return qe.embedded_chat(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        except Exception:
            pass
    if is_qwen_ram_enabled() and qe.model_present() and qe.llama_importable():
        qe.start_ram_load_async()
    if USE_OLLAMA_FALLBACK:
        ensure_ollama_running()
        if ollama_available():
            return ollama_chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_sec=timeout_sec,
            )
    if qe.embedded_file_installed():
        raise RuntimeError(
            "Файл Qwen в Jarvis есть, но движок не запустился. "
            "Запустите Ollama и выполните: ollama pull qwen2.5:14b"
        )
    raise RuntimeError(
        f"{MODEL_LABEL} не установлена внутрь Jarvis. "
        "Запустите install-qwen.bat — файл попадёт в backend/data/models приложения (~9 ГБ)."
    )


# --- Роутер интентов и локальные ответы (Ollama) ---

from typing import Literal

IntentTag = Literal["LOCAL_HELP", "COMPLEX_TEXT", "GEN_IMAGE", "DOC_ACTION"]

INTENT_TAGS: tuple[str, ...] = (
    "LOCAL_HELP",
    "COMPLEX_TEXT",
    "GEN_IMAGE",
    "DOC_ACTION",
)

_TAG_RE = re.compile(
    r"\[(LOCAL_HELP|COMPLEX_TEXT|GEN_IMAGE|DOC_ACTION)\]",
    re.I,
)

ROUTER_SYSTEM = """Ты — микро-роутер Jarvis (локальная Qwen). Выбери ОДИН тег. Ответ — только тег в скобках, без слов.

Смотри «Доступные нейросети» и **режим чата** (уже выбран автоматически по задаче Шефа: standard / accountant / marketer / developer).
Правила из бессознательного dialog_routing_rules:

ЕСЛИ ОБЛАКО ДОСТУПНО (ДА в списке) — ставь облачный тег, когда задача это требует:
[COMPLEX_TEXT] — сложный текст, законы, налоги, код (DeepSeek; developer + Perplexity: ДА).
[GEN_IMAGE] — картинка или видео, если в блоке «Медиа-провайдеры» для нужного типа написано ДА (Nano Banana, OpenAI, xAI).
[DOC_ACTION] — выписка, ИНН, договор.

ЕСЛИ ОБЛАКА НЕТ (НЕТ в списке) — ТОЛЬКО [LOCAL_HELP]:
не ставь [COMPLEX_TEXT] и [GEN_IMAGE] без доступного медиа-провайдера.

[LOCAL_HELP] — привет, настройка Jarvis, ссылка/2ГИС/«посмотри URL», интернет (web_search, fetch_url), проверка систем. Ссылка НИКОГДА не [COMPLEX_TEXT].

Режим переключать в ответе не нужно — это делает backend до твоего тега.

Контекст — в сообщении пользователя."""

LOCAL_HELP_SYSTEM = """Ты — локальный помощник Jarvis (Qwen 2.5 14B). Работаешь офлайн на ПК пользователя.
Отвечай по-русски, **кратко** (1–3 предложения или до 4 пунктов списка). Без воды.
Не обрывай ответ на полуслове и не оставляй пустые пункты («2.» без текста). Начал список — допиши все пункты.
Не заканчивай ответ блоком «---» и не дописывай «Хочешь ли…» / «Могу также…» / «Как я могу помочь?».
**Запрещено** писать от имени Шефа и придумывать его следующий вопрос («Мне нужна помощь…»).
Развёрнуто — **только** если Шеф явно просит подробнее. На «привет» — 1–2 фразы. Эмодзи — не больше одного.
**Запрещено** писать «Представь информацию так, чтобы было понятно новичку» и подобные мета-инструкции — сразу отвечай по делу.
**Запрещены рассуждения вслух:** без «сначала мне нужно», «Продолжим?», «(Процесс анализа…)» и вопросов к себе — только готовый ответ. Рассуждения — только если Шеф явно просит объяснить ход мыслей.

**Интерфейс Jarvis:**
- **Сайдбар слева** — меню и настройки; чат справа.
- **Коннектор Авито** (⚙️ Настройки) — Client ID/Secret, синхронизация метрик в SQLite.
- **Центр** — чат Jarvis; скрепка для файлов; «Речь в текст».
- **Панель индикации** — DeepSeek, Qwen, голос, статусы Авито.
- **⚙️ Настройки** — ключи API, студия голоса, АТС, сознательное.
- **Режимы (авто):** Jarvis сам выбирает профиль по задаче — бухгалтерия/право, маркетинг/картинки, код, универсальный чат. Переключателя в UI нет.
- **Картинки и видео** — любой доступный провайдер (Nano Banana, OpenAI DALL·E, xAI Grok Imagine). Роутер выбирает сам.
- **Код** — профиль разработчика через **Perplexity** (лучше) или **DeepSeek** при наличии ключей.
- Ты управляешь коннектором Авито через JSON-инструменты (ui_*, get_stored_metrics).

**Настройка голоса:** Настройки → Голос → прикрепить аудио .ogg/.wav до 15 МБ ИЛИ записать в студии.
**Ключ DeepSeek:** вставить `sk-…` в чат или в Настройках — для сложных ответов облака.
**Сложные вопросы** (налоги, кодексы) уходят в DeepSeek автоматически — не выдумывай статьи закона.

Модель Qwen **ставится внутрь приложения Jarvis** — файл GGUF в `backend/data/models` в папке Jarvis
(это часть установки приложения, **не** «просто на компьютер» и **не** общий каталог Ollama).
При первом запуске: **install-qwen.bat** или **start.bat** (~9 ГБ).

**Маршрут ответа (бессознательное dialog_routing_rules):**
- Облако доступно (DeepSeek / Perplexity / Nano Banana в списке) → сложные задачи уходят в облако; интернет — web_search и fetch_url.
- Облака нет → отвечаешь только ты (Qwen) и JSON-инструменты; не выдумывай законы и код.

**Интернет:** `web_search` и **Chromium** (`fetch_url`). Ссылка в чате → всегда fetch_url; не отказывай без вызова инструмента.
- **Память:** SQLite `jarvis.db`, ячейки `memory_save_cell`, файлы сознательное/бессознательное/режима. **Один чат** — история сбрасывается при выключении; сознательное постоянно. **Техдокументация.txt** — в бессознательном, отдельный блок в промпте (§14 — что ты умеешь).
- **Авито:** метрики в SQLite (`get_stored_metrics`), синхронизация по запросу — не выдумывай цифры.
- Ты **и есть Jarvis** — ядро приложения на ПК Шефа, не абстрактный «чужой ИИ».

Если Шеф спрашивает про браузер/память/«ты Jarvis?» — отвечай по фактам выше.
Ссылка или «посети страницу» → **fetch_url** (встроенный Chromium), при необходимости **web_search**."""


def ollama_available() -> bool:
    if not USE_OLLAMA_FALLBACK:
        return False
    ollama_up, model_loaded, _, _ = _check_ollama()
    return bool(ollama_up and model_loaded)


def _resolve_ollama_model() -> str:
    st = get_qwen_status()
    return (st.get("ollama_model_name") or OLLAMA_MODEL).strip()


def ollama_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
    timeout_sec: float = 90.0,
) -> tuple[str, int]:
    """Синхронный запрос к Ollama /api/chat. Возвращает (текст, ~токены)."""
    if not ollama_available():
        raise RuntimeError(f"Ollama / {MODEL_LABEL} недоступны")

    model = _resolve_ollama_model()
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    with httpx.Client(timeout=timeout_sec, trust_env=False) as client:
        r = client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()

    msg = data.get("message") or {}
    text = (msg.get("content") or "").strip()
    eval_count = int((data.get("eval_count") or 0))
    tokens = eval_count or max(1, len(text) // 4)
    return text, tokens


_DOC_HARD_SIGNALS = (
    "выписк",
    "инн",
    "огрн",
    "контрагент",
    "1c_to_kl",
    "договор",
    "xlsx",
    "счет-фактур",
    "счёт",
    "реквизит",
    "банковск",
    "сформируй сч",
    "счет-фактур",
)


def _has_doc_intent(low: str) -> bool:
    if any(w in low for w in _DOC_HARD_SIGNALS):
        return True
    if re.search(r"\bсч[её]т\b", low) and "логик" not in low and "бот" not in low:
        return True
    return False


def is_neural_stack_question(text: str) -> bool:
    """«Какие нейросети / чем генерируешь текст / что подключено»."""
    low = (text or "").lower()
    if _has_doc_intent(low):
        return False
    ask = (
        "какие нейросет",
        "какие модел",
        "что доступн",
        "что подключ",
        "что у тебя",
        "с помощью чего",
        "чем ты генерир",
        "чем генерируешь",
        "как ты генерир",
        "на чём работаешь",
        "какая модель",
        "какой модель",
        "кто отвечает",
        "что за нейросет",
        "список api",
        "список ключ",
    )
    if any(p in low for p in ask):
        return True
    if is_api_or_app_meta_question(text) and any(
        w in low for w in ("нейросет", "модел", "генерир", "текст", "llm", "qwen", "deepseek")
    ):
        return True
    return False


def is_api_or_app_meta_question(text: str) -> bool:
    """Вопросы про API-ключи/доступность нейросетей — не бухгалтерские документы."""
    low = (text or "").lower()
    if _has_doc_intent(low):
        return False
    meta_signals = (
        "токен",
        "токены",
        "ключ",
        "api",
        "deepseek",
        "дипсик",
        "дип сик",
        "qwen",
        "nano",
        "banana",
        "нейросет",
        "доступн",
        "подключ",
        "работаешь",
        "видишь",
        "sk-",
        "настройк",
        "индикатор",
    )
    return any(m in low for m in meta_signals)


def is_local_setup_intent(text: str) -> bool:
    """Настройка UI, Авито, файлы — не DOC_ACTION / не выписки."""
    if is_api_or_app_meta_question(text):
        return True
    low = (text or "").lower()
    if _has_doc_intent(low):
        return False
    setup_signals = (
        "коннектор",
        "авито",
        "avito",
        "сайдбар",
        "записать",
        "загрузить",
        "вставить",
        "сохранить",
        "текстовый файл",
        "файл с кодом",
        "файл с текстом",
        "json",
        "прокси",
        "коннектор авито",
    )
    return any(s in low for s in setup_signals)


IMAGE_GENERATION_WORDS = (
    "нарисуй",
    "нарисовать",
    "сгенерируй картин",
    "сгенерировать картин",
    "сгенерируй изображ",
    "можешь сгенерировать картин",
    "сделай картин",
    "изображен",
    "картинк",
    "баннер",
    "логотип",
    "концепт",
    "иллюстрац",
    "poster",
    "generate image",
    "draw ",
)


def user_requests_live_web_action(text: str) -> bool:
    """Конкретное действие в сети (ссылка, «открой», «посети») — не подменять шаблоном про возможности."""
    import re

    low = (text or "").lower()
    if re.search(r"https?://", low):
        return True
    action_words = (
        "посети",
        "открой",
        "зайди",
        "перейди",
        "прочитай страниц",
        "загрузи страниц",
        "сколько организац",
        "посчитай",
        "в этом здании",
        "по ссылке",
        "go.2gis",
        "2gis.com",
    )
    return any(w in low for w in action_words)


def is_jarvis_capability_question(text: str) -> bool:
    """Вопросы «есть ли браузер/память/ты Jarvis» — не отрицать возможности приложения."""
    if user_requests_live_web_action(text):
        return False
    low = (text or "").lower()
    signals = (
        "браузер",
        "встроенн",
        "умеешь ли",
        "можешь ли",
        "есть ли у тебя",
        "есть у тебя",
        "открыть сайт",
        "доступ к интернет",
        "нет интернет",
        "в сети",
        "duckduckgo",
        "web_search",
        "запомн",
        "вспомн",
        "другом чат",
        "другой чат",
        "между чат",
        "следующем чат",
        "новом чат",
        "память",
        "jarvis.db",
        "база данных",
        "sqlite",
        "ты и есть",
        "ты jarvis",
        "ты — jarvis",
        "эта нейронка",
        "частично jarvis",
        "кто ты",
        "ты кто",
        "что умеешь",
        "что ты умеешь",
        "чем можешь",
        "что ты можешь",
        "твои возможност",
        "куда став",
        "куда скач",
        "где лежит модел",
        "где модель",
        "install-qwen",
        "data/models",
        "на компьютер",
        "ollama pull",
    )
    return any(s in low for s in signals)


def jarvis_capability_reply(text: str) -> str | None:
    """Короткий фактический ответ про возможности Jarvis (без философии)."""
    try:
        from modules.jarvis_capabilities import (
            is_general_capabilities_question,
            jarvis_capabilities_summary_for_user,
        )

        if is_general_capabilities_question(text):
            return jarvis_capabilities_summary_for_user()
    except Exception:
        pass

    low = (text or "").lower()
    parts: list[str] = []

    if any(
        w in low
        for w in (
            "браузер",
            "встроенн",
            "интернет",
            "в сети",
            "duckduckgo",
            "web_search",
            "web_research",
            "гугл",
            "google",
            "стереотип",
            "научился",
            "научишься",
            "поиск в сет",
        )
    ) and not user_requests_live_web_action(text):
        from modules.chromium_browser import chromium_browser_status
        from modules.web_stereotypes import stereotypes_status

        ch = chromium_browser_status()
        st = stereotypes_status()
        ch_line = (
            "• **fetch_url** / **web_research** — **встроенный Chromium** (headless).\n"
            if ch.get("ready")
            else "• **fetch_url** / **web_research** — нужен **install-chromium.bat** "
            "(Chromium ещё не установлен).\n"
        )
        stereo_line = (
            f"• **Стереотипы** — {st.get('count', 0)} приоритетных сайтов "
            f"(`Стереотипы.txt` в бессознательном).\n"
        )
        parts.append(
            "**Поиск в интернете — да, умею.**\n"
            "• **web_research** — сначала **Стереотипы.txt**, затем Google, выжимка фактов; "
            "ссылки — отдельно внизу.\n"
            "• **web_search** — быстрые сниппеты DuckDuckGo.\n"
            f"{stereo_line}"
            f"{ch_line}"
            "Примеры: «найди в интернете …», «загугли …», «курс доллара».\n"
            "Дайте точную ссылку — открою страницу и отвечу по тексту."
        )

    if any(
        w in low
        for w in (
            "запомн",
            "вспомн",
            "другом чат",
            "другой чат",
            "между чат",
            "следующем чат",
            "новом чат",
            "память",
            "база данных",
            "jarvis.db",
            "sqlite",
        )
    ):
        parts.append(
            "**Память между чатами**\n"
            "Да. На вашем ПК работает **jarvis.db** (SQLite) и файлы памяти:\n"
            "• **Ячейки памяти** — сохраняю факты (`memory_save_cell`), они подмешиваются во **все чаты** режима.\n"
            "• **Сознательное / бессознательное** — в ⚙️ Настройках (файлы .txt/.md/.json).\n"
            "• **Авито** — метрики кэшируются в SQLite, чтобы не дёргать API каждый раз.\n"
            "Список чатов слева — отдельные диалоги, но долговременные факты — в БД и файлах. "
            "Напишите: **«запомни: …»** — сохраню в ячейку."
        )

    if any(
        w in low
        for w in (
            "ты и есть",
            "ты jarvis",
            "эта нейронка",
            "частично",
            "кто ты",
            "что умеешь",
            "твои возможност",
        )
    ):
        parts.append(
            "**Кто я**\n"
            "Да — я **Jarvis**, ядро этого приложения на вашем ПК: локальная Qwen 2.5 14B плюс "
            "инструменты (БД, web_search, Авито). Не «чужой сайт в браузере»."
        )

    _model_place = (
        "куда став",
        "куда скач",
        "где лежит",
        "где модель",
        "куда попад",
        "install-qwen",
        "data/models",
        "на компьютер",
        "внутри jarvis",
        "в папке jarvis",
    )
    _model_words = ("модел", "qwen", "14b", "gguf", "ollama")
    if any(w in low for w in _model_place) or (
        any(w in low for w in ("скач", "установ", "install")) and any(w in low for w in _model_words)
    ):
        from modules import qwen_embedded as _qe

        path = _qe.model_path().resolve()
        parts.append(
            "**Где модель Qwen**\n"
            f"Файл **внутри Jarvis**, не отдельная установка «на весь ПК»:\n"
            f"`{path}`\n"
            "Каталог `backend/data/models` — часть папки приложения. "
            "Скачать: **install-qwen.bat** или **start.bat** (~9 ГБ). "
            "Ollama — только запасной движок, если llama-cpp не поднялся; основной путь — файл в Jarvis."
        )

    if not parts:
        return None
    return "\n\n".join(parts)


def wants_image_generation(text: str) -> bool:
    from modules.media_generation import wants_image_generation as _w

    return _w(text)


def wants_media_generation(text: str) -> bool:
    from modules.media_generation import wants_media_generation as _w

    return _w(text)


def image_capability_reply(mode_hint: str, availability: dict[str, bool] | None = None) -> str:
    """Обратная совместимость → media_capability_reply."""
    from modules.media_generation import media_capability_reply

    del mode_hint
    avail = availability or {}
    if avail.get("media_image") or avail.get("media_video"):
        return ""
    return media_capability_reply("image")


def parse_intent_tag(raw: str) -> IntentTag | None:
    m = _TAG_RE.search(raw or "")
    if not m:
        return None
    tag = m.group(1).upper()
    if tag in INTENT_TAGS:
        return tag  # type: ignore[return-value]
    return None


def keyword_classify_intent(
    user_text: str,
    mode_hint: str = "standard",
    *,
    availability: dict[str, bool] | None = None,
) -> IntentTag:
    """Резервная классификация без Ollama (ключевые слова)."""
    from modules.neural_keys import get_neural_availability

    low = (user_text or "").lower()
    mode = (mode_hint or "standard").lower()
    avail = availability if availability is not None else get_neural_availability()
    has_deepseek = bool(avail.get("deepseek"))
    has_perplexity = bool(avail.get("perplexity"))

    has_media_image = bool(avail.get("media_image"))
    has_media_video = bool(avail.get("media_video"))

    if mode == "accountant" and not has_deepseek:
        return "LOCAL_HELP"
    if mode == "developer" and not has_perplexity:
        return "LOCAL_HELP"

    from modules.media_generation import detect_media_kind, has_media_provider

    if wants_media_generation(user_text):
        kind = detect_media_kind(user_text) or "image"
        if has_media_provider(kind):
            return "GEN_IMAGE"
        return "LOCAL_HELP"

    doc_words = (
        "выписк",
        "контрагент",
        "инн ",
        "инн:",
        "огрн",
        "бик ",
        "р/с",
        "расчётн",
        "1c_to_kl",
        "банковск",
        "договор",
        "счёт",
        "счет-фактур",
        "invoice",
        "xlsx",
        "реквизит",
    )
    if is_local_setup_intent(user_text):
        return "LOCAL_HELP"

    if user_requests_live_web_action(user_text):
        return "LOCAL_HELP"

    if any(w in low for w in doc_words):
        if mode == "accountant" and not has_deepseek:
            return "LOCAL_HELP"
        return "DOC_ACTION"

    complex_words = (
        "ст.",
        "статья",
        "нк рф",
        "гк рф",
        "ук рф",
        "кодекс",
        "консультант",
        "судебн",
        "исков",
        "претенз",
        "ликвидац",
        "налогов",
        "юридическ",
        "проанализируй закон",
        "разбор статьи",
    )
    if any(w in low for w in complex_words):
        return "COMPLEX_TEXT" if has_deepseek else "LOCAL_HELP"

    help_words = (
        "привет",
        "здравств",
        "как настро",
        "где найти",
        "как включ",
        "помощь",
        "интерфейс",
        "сайдбар",
        "голос",
        "озвуч",
        "студия",
        "ollama",
        "deepseek",
        "дипсик",
        "токен",
        "токены",
        "доступн",
        "настройк",
        "что умеешь",
        "кто ты",
    )
    if is_creative_story_request(user_text):
        return "LOCAL_HELP"
    try:
        from modules.dialog_handlers import (
            is_acknowledgment_utterance,
            is_ambiguous_short_task,
        )

        if is_ambiguous_short_task(user_text) or is_acknowledgment_utterance(user_text):
            return "LOCAL_HELP"
    except Exception:
        pass

    if any(w in low for w in help_words) or (
        len(low) < 40 and not is_creative_story_request(user_text)
    ):
        return "LOCAL_HELP"

    if mode == "accountant":
        return "COMPLEX_TEXT" if has_deepseek else "LOCAL_HELP"
    if mode == "developer":
        return "COMPLEX_TEXT" if has_perplexity else "LOCAL_HELP"

    from modules.avito_overview_handler import (
        wants_avito_listing_success,
        wants_avito_overview,
    )

    if wants_avito_overview(user_text) or wants_avito_listing_success(user_text):
        return "LOCAL_HELP"

    if mode == "marketer" and not wants_image_generation(user_text):
        return "COMPLEX_TEXT" if has_deepseek else "LOCAL_HELP"

    return "LOCAL_HELP"


def classify_intent(user_text: str, mode_hint: str = "standard") -> tuple[IntentTag, str]:
    """Классификация через Qwen. Возвращает (тег, engine: qwen|keywords)."""
    from modules.neural_keys import format_availability_for_router, get_neural_availability

    from modules import jarvis_db
    from modules.agent import get_mode

    avail = get_neural_availability()
    if not qwen_available():
        return keyword_classify_intent(user_text, mode_hint, availability=avail), "keywords"

    jarvis_db.init_db()
    mode_val = mode_hint or get_mode().value
    training_note = jarvis_db.training_context_for_router(mode_val)

    user_block = (
        f"Доступные нейросети:\n{format_availability_for_router()}\n\n"
        f"Режим чата: {mode_val}\n"
        f"{training_note}\n\n"
        f"Запрос пользователя:\n{user_text.strip()[:2000]}"
    )
    if is_local_setup_intent(user_text):
        return "LOCAL_HELP", "setup"
    if is_jarvis_capability_question(user_text):
        return "LOCAL_HELP", "capabilities"
    if user_requests_live_web_action(user_text):
        return "LOCAL_HELP", "url_action"

    from modules.avito_overview_handler import (
        wants_avito_listing_success,
        wants_avito_overview,
    )

    if wants_avito_overview(user_text) or wants_avito_listing_success(user_text):
        return "LOCAL_HELP", "avito_local"

    try:
        raw, _ = qwen_chat(
            [
                {"role": "system", "content": ROUTER_SYSTEM},
                {"role": "user", "content": user_block},
            ],
            temperature=0.05,
            max_tokens=24,
            timeout_sec=45.0,
        )
        tag = parse_intent_tag(raw)
        if tag:
            if tag == "DOC_ACTION" and is_local_setup_intent(user_text):
                return "LOCAL_HELP", "qwen+setup_override"
            if tag == "COMPLEX_TEXT" and (
                wants_avito_overview(user_text) or wants_avito_listing_success(user_text)
            ):
                return "LOCAL_HELP", "qwen+avito_override"
            return tag, "qwen"
    except Exception:
        pass
    return keyword_classify_intent(user_text, mode_hint, availability=avail), "keywords"


def _greeting_task_blockers(low: str) -> bool:
    task_signals = (
        "сказ",
        "расскаж",
        "нарисуй",
        "сгенерир",
        "сделай",
        "помог",
        "объясн",
        "напиш",
        "посчит",
        "открой",
        "авито",
        "http",
        "абзац",
    )
    return any(w in low for w in task_signals)


def _is_greeting_typo(text: str) -> bool:
    """Опечатки вроде «првиет» → привет (без вызова длинной модели)."""
    from difflib import SequenceMatcher

    low = (text or "").lower().strip()
    if not low or len(low) > 20 or _greeting_task_blockers(low):
        return False
    compact = re.sub(r"[^\wа-яё]+", "", low, flags=re.I)
    if not compact or len(compact) < 3:
        return False
    refs = ("привет", "здравствуй", "здарова", "здаров", "салют", "hello", "hi", "hey")
    for ref in refs:
        if SequenceMatcher(None, compact, ref).ratio() >= 0.78:
            return True
    return False


def _is_short_greeting(text: str) -> bool:
    """Только явное приветствие. Не матчить «ку» внутри «сказку» и т.п."""
    low = (text or "").lower().strip()
    if not low or len(low) > 48:
        return False
    if _greeting_task_blockers(low):
        return False
    compact = re.sub(r"[^\w\s]+", " ", low).strip()
    tokens = compact.split()
    if len(tokens) > 5:
        return False
    exact = {
        "привет",
        "здарова",
        "здаров",
        "салют",
        "хай",
        "hello",
        "hi",
        "ку",
        "hey",
        "ты как",
        "как ты",
        "как дела",
    }
    if compact in exact:
        return True
    if len(tokens) <= 3 and tokens and tokens[0] in exact:
        return True
    if compact.startswith(("привет", "здравств", "добрый", "доброе")) and len(compact) < 32:
        return True
    return False


def is_greeting_like(text: str) -> bool:
    try:
        from modules.dialog_handlers import is_casual_smalltalk

        if is_casual_smalltalk(text):
            return True
    except Exception:
        pass
    return _is_short_greeting(text) or _is_greeting_typo(text)


def greeting_reply_text(user_text: str) -> str:
    """Короткий ответ на привет / как дела — без исправления опечаток."""
    try:
        from modules.dialog_handlers import casual_smalltalk_reply

        return casual_smalltalk_reply(user_text)
    except Exception:
        pass
    return "Привет, Шеф.\n\n**Jarvis** на связи — чем помочь?"


def is_creative_story_request(text: str) -> bool:
    low = (text or "").lower()
    return any(
        w in low
        for w in (
            "сказк",
            "сказоч",
            "быль",
            "истори",
            "расскаж",
            "повест",
            "принц",
            "принцесс",
            "золушк",
            "cinderella",
            "fairy tale",
        )
    )


def requested_paragraph_count(text: str) -> int | None:
    m = re.search(r"(\d+)\s*абзац", (text or "").lower())
    if m:
        n = int(m.group(1))
        return max(1, min(n, 12))
    return None


def generate_local_help(
    user_text: str,
    history: list[dict],
    *,
    extra_system: str = "",
) -> tuple[str, int, str]:
    """Локальный ответ Qwen для [LOCAL_HELP] с tool-calling. engine: qwen|qwen+tools|fallback."""
    from modules.agent import (
        append_notifications_to_system,
        build_context,
        build_qwen_system_message,
        get_runtime,
        sanitize_history,
    )
    from modules.qwen_tools import execute_tool, maybe_auto_tools, run_qwen_tool_loop

    if is_greeting_like(user_text):
        text = greeting_reply_text(user_text)
        return text, max(24, len(text) // 4), "greeting"

    if is_creative_story_request(user_text):
        n_para = requested_paragraph_count(user_text) or 3
        system_story = (
            build_qwen_system_message()
            + "\n\n[Сказка для Шефа]\n"
            f"Напиши **оригинальную или классическую** сказку на русском ровно в **{n_para} абзаца** "
            "(между абзацами — пустая строка). "
            "Сюжет целиком: начало, середина, **конец с развязкой**. "
            "Запрещено: вопросы к Шефу, английский, имитация реплик Шефа («давай расскажи…»), "
            "диалог «Шеф — Jarvis». Только текст сказки от Jarvis.\n"
        )
        history_clean = sanitize_history(history)
        msgs: list[dict[str, str]] = [
            {"role": "system", "content": append_notifications_to_system(system_story, history_clean)},
            *[
                {"role": m["role"], "content": m.get("content", "")}
                for m in build_context(history_clean, window=6)
            ],
            {"role": "user", "content": user_text.strip()},
        ]
        try:
            from modules.text_sanitize import polish_assistant_reply

            raw, tok = qwen_chat(
                msgs,
                temperature=0.55,
                max_tokens=2200,
                timeout_sec=120.0,
            )
            if (raw or "").strip():
                text = polish_assistant_reply(raw, user_text, skip_brevity=True)
                return text, max(tok, len(text) // 4), "story"
        except Exception:
            pass

    low_cap = (user_text or "").lower()
    if any(w in low_cap for w in ("авито", "avito")) and any(
        w in low_cap
        for w in (
            "что доступн",
            "что тебе",
            "что теперь",
            "по api",
            "по апи",
            "возможност",
            "что умеешь",
        )
    ):
        from modules.avito_messenger import capabilities_summary_text
        from modules.text_sanitize import polish_assistant_reply

        text = polish_assistant_reply(capabilities_summary_text(), user_text)
        return text, max(24, len(text) // 4), "avito_caps"

    if not qwen_available():
        from modules.agent import local_help_fallback

        text, tokens = local_help_fallback(user_text, history)
        return text, tokens, "fallback"

    from modules.text_sanitize import (
        followup_brevity_hint,
        length_instruction_for_prompt,
        reply_max_tokens,
        user_question_is_short,
        wants_sandbox_write,
    )

    system = build_qwen_system_message()
    try:
        from modules.listing_generation import listing_system_extra

        listing_extra = listing_system_extra(user_text)
        if listing_extra:
            system += f"\n\n{listing_extra}"
    except Exception:
        pass
    system += (
        "\n\n[Напоминание Qwen]\n"
        "Панель «коннектор Авито» — в ⚙️ Настройках. "
        "Любое действие с полями/кнопками = одна строка JSON {\"tool\":..., \"arguments\":...} "
        "(см. блок UI CONTROL). Не пиши «готово», пока не вызвал инструмент.\n"
        "Не обрывай ответ на полуслове — закончи предложение.\n"
        "Структурируй ответ **абзацами** (пустая строка между блоками), не сплошным текстом.\n"
        "**Запрещено** писать bash-команды (sync_avito_chats, login_avito_oauth и т.п.) — "
        "действия только через JSON-инструменты из блока [Инструменты].\n"
    )
    system += length_instruction_for_prompt(user_text)
    if wants_sandbox_write(user_text):
        system += (
            "\n[ПЕСОЧНИЦА — обязательно]\n"
            "Код для modules/jarvis_skills.py — только через save_jarvis_skill_code "
            "(полный файл с class CustomSkills). Не вставляй длинные ```python блоки в чат.\n"
            "После сохранения: 1–3 предложения — что добавлено и как вызвать "
            "run_jarvis_skill('имя_метода').\n"
        )
    if extra_system.strip():
        system += f"\n\n{extra_system.strip()}"
    history = sanitize_history(history)
    system = append_notifications_to_system(system, history)

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for m in build_context(history, window=12):
        messages.append({"role": m["role"], "content": m.get("content", "")})

    # Явные запросы про Авито/интернет — подмешиваем реальные данные до ответа модели
    prelude: list[str] = []
    for call in maybe_auto_tools(user_text, history):
        try:
            get_runtime().log("qwen.tool", f"Авто `{call['tool']}`")
            prelude.append(
                f"[Результат инструмента {call['tool']} (авто)]\n"
                + execute_tool(call)
            )
        except Exception as e:
            prelude.append(f"[Ошибка {call['tool']}: {e}]")
    user_block = user_text.strip()
    if prelude:
        tail = (
            "Ответь по данным инструментов выше; не выдумывай цифры и адреса. "
            "Если есть fetch_url — только факты из текста страницы, без «зайдите сами»."
        )
        if wants_sandbox_write(user_text):
            tail += (
                " Для кода — save_jarvis_skill_code (полный файл), "
                "в чат только краткий итог."
            )
        if user_question_is_short(user_text):
            tail += (
                " Ответ короткий: 1–3 предложения или до 4 пунктов списка с текстом в каждом; "
                "допиши список до конца. Без реплик от имени Шефа."
            )
        user_block = (
            "\n\n".join(prelude)
            + "\n\n[Вопрос пользователя]\n"
            + user_block
            + f"\n\n{tail}"
        )
    messages.append({"role": "user", "content": user_block})

    gen_tokens = reply_max_tokens(user_text, cloud=False)

    try:
        text, tokens, engine = run_qwen_tool_loop(
            messages,
            user_text=user_text,
            chat_fn=lambda msgs: qwen_chat(
                msgs, temperature=0.35, max_tokens=gen_tokens
            ),
        )
        if text:
            from modules.text_sanitize import polish_assistant_reply

            text = polish_assistant_reply(text, user_text)
            return text, tokens, engine
    except Exception:
        pass

    from modules.agent import local_help_fallback

    text, tokens = local_help_fallback(user_text, history)
    from modules.text_sanitize import polish_assistant_reply

    return polish_assistant_reply(text, user_text), tokens, "fallback"


def register_ollama_from_embedded_gguf() -> tuple[bool, str]:
    """
    Создать модель в Ollama из GGUF в backend/data/models (если llama-cpp не поднялся).
  """
    global _ollama_gguf_register_done
    if not USE_OLLAMA_FALLBACK or not qe.model_present():
        return False, "нет файла или Ollama отключён"
    with _ollama_gguf_register_lock:
        if _ollama_gguf_register_done:
            up, loaded, name, _ = _check_ollama()
            return bool(loaded), name or "уже пробовали"
        _ollama_gguf_register_done = True

    if not ensure_ollama_running(45):
        return False, "Ollama не запущен"

    up, loaded, name, _ = _check_ollama()
    if loaded and name:
        return True, name

    exe = _find_ollama_exe()
    if not exe:
        return False, "ollama.exe не найден"

    modelfile = qe.MODELS_DIR / "Modelfile.jarvis-qwen"
    gguf = qe.model_path().resolve()
    modelfile.write_text(
        f"FROM {gguf.as_posix()}\n\nPARAMETER temperature 0.4\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [exe, "create", OLLAMA_JARVIS_MODEL, "-f", str(modelfile)],
            capture_output=True,
            text=True,
            timeout=900,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-300:]
            return False, tail or f"ollama create exit {proc.returncode}"
    except subprocess.TimeoutExpired:
        return False, "ollama create: таймаут"
    except Exception as e:
        return False, str(e)[:200]

    _, loaded, name, _ = _check_ollama()
    return bool(loaded), name or OLLAMA_JARVIS_MODEL


def _find_ollama_exe() -> str | None:
    exe = shutil.which("ollama")
    if exe:
        return exe
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if local.is_file():
        return str(local)
    return None


def ensure_ollama_running(wait_sec: float = 4.0) -> bool:
    """Запускает `ollama serve`, если демон не отвечает (Windows / PATH)."""
    ollama_up, _, _, _ = _check_ollama()
    if ollama_up:
        return True
    exe = _find_ollama_exe()
    if not exe:
        return False
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return False
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        time.sleep(0.6)
        up, _, _, _ = _check_ollama()
        if up:
            return True
    return False


def warmup_qwen_async() -> None:
    """Фоновая загрузка Qwen в RAM — только если включено в настройках."""

    if not is_qwen_ram_enabled():
        return

    def _run() -> None:
        if qe.model_present():
            qe.start_ram_load_async()
            if qe.embedded_inference_ready():
                qe.warmup_async()
                return
            if USE_OLLAMA_FALLBACK and qe.get_load_error():
                register_ollama_from_embedded_gguf()
        if USE_OLLAMA_FALLBACK:
            ensure_ollama_running()
            if ollama_available():
                try:
                    ollama_chat(
                        [{"role": "user", "content": "ok"}],
                        max_tokens=4,
                        temperature=0.0,
                        timeout_sec=120.0,
                    )
                except Exception:
                    pass

    threading.Thread(target=_run, name="jarvis-qwen-warmup", daemon=True).start()


def ensure_qwen_installed() -> dict:
    """Скачать встроенную модель, если её нет (вызов из start.bat)."""
    if not qe.llama_importable():
        return {"ok": False, "message": "llama-cpp-python не установлен"}
    return qe.download_model()


def download_qwen_model(**kwargs) -> dict:
    return qe.download_model(**kwargs)


def get_qwen_download_progress() -> dict:
    """Лёгкий статус только для полосы загрузки (опрос UI)."""
    dl = qe.get_download_status()
    phase = dl.get("phase") or "idle"
    # Зависший «downloading» без процесса и без .part — сбросить
    if (
        phase == "downloading"
        and not _qwen_download_job_active()
        and not qe.model_present()
        and not qe.PART_PATH.is_file()
    ):
        qe.mark_download_error(
            "Загрузка не запустилась. Перезапустите Jarvis (restart.bat) "
            "или запустите install-qwen.bat. Лог: logs/qwen-ui-download.log"
        )
        dl = qe.get_download_status()
        phase = dl.get("phase") or "idle"
    return {
        "phase": phase,
        "progress": int(dl.get("progress") or 0),
        "message": dl.get("message") or "",
        "bytes_done": int(dl.get("bytes_done") or 0),
        "bytes_total": int(dl.get("bytes_total") or 0),
        "files_present": qe.model_present(),
        "job_active": _qwen_download_job_active(),
    }


def start_qwen_download(*, force: bool = False) -> dict:
    """Фоновое скачивание GGUF в backend/data/models (как install-qwen.bat)."""
    global _qwen_download_thread

    if qe.model_present() and not force:
        return {
            **get_qwen_status(),
            "ok": True,
            "skipped": True,
            "already_installed": True,
            "started": False,
        }

    with _qwen_download_lock:
        if _qwen_download_job_active():
            return {
                **get_qwen_status(),
                "ok": True,
                "skipped": True,
                "already_installed": False,
                "started": False,
                "in_progress": True,
            }

        qe.mark_download_starting()

        def _run_in_thread() -> None:
            try:
                result = download_qwen_model(force=force)
                if not result.get("ok") and not qe.model_present():
                    qe.mark_download_error(
                        (result.get("message") or "Ошибка загрузки")[:240]
                    )
            except Exception as e:
                qe.mark_download_error(f"Ошибка загрузки: {str(e)[:200]}")

        # Основной путь — поток в том же процессе (статус и .part сразу видны UI)
        global _qwen_download_thread
        _qwen_download_thread = threading.Thread(
            target=_run_in_thread,
            name="jarvis-qwen-download",
            daemon=True,
        )
        _qwen_download_thread.start()

    return {
        **get_qwen_status(),
        "ok": True,
        "skipped": False,
        "already_installed": False,
        "started": True,
    }
