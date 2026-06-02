"""
Встроенная Qwen 2.5 14B (GGUF) — внутри приложения Jarvis (backend/data/models).
Не отдельная установка «на компьютер» и не каталог Ollama по умолчанию.
Скачивается при установке Jarvis (start.bat / install-qwen.bat).
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from modules.app_paths import models_dir

MODELS_DIR = models_dir()
MODEL_LABEL = "Qwen 2.5 14B"
MODEL_FILENAME = os.getenv(
    "JARVIS_QWEN_GGUF_FILE",
    "Qwen2.5-14B-Instruct-Q4_K_M.gguf",
)
MODEL_PATH = MODELS_DIR / MODEL_FILENAME
META_PATH = MODELS_DIR / "qwen2.5-14b.embedded.json"
DOWNLOAD_STATUS_PATH = MODELS_DIR / "qwen2.5-14b.download.json"
CPU_BLOCK_FLAG = MODELS_DIR / "llama-cpp.cpu-blocked"
PART_PATH = MODEL_PATH.with_suffix(MODEL_PATH.suffix + ".part")

# Типичный размер Q4_K_M (~9 ГБ) — для процента по файлу .part
EXPECTED_DOWNLOAD_BYTES = 8_900_000_000

DEFAULT_DOWNLOAD_URL = os.getenv(
    "JARVIS_QWEN_GGUF_URL",
    "https://huggingface.co/second-state/Qwen2.5-14B-Instruct-GGUF/resolve/main/Qwen2.5-14B-Instruct-Q4_K_M.gguf",
)

# ~9 ГБ на диске (Q4_K_M)
MIN_BYTES = 7_000_000_000

_llama = None
_llama_lock = threading.Lock()
_importable: bool | None = None
_load_attempted = False
_inference_ready = False
_load_error: str | None = None
_loading_ram = False


def llama_importable() -> bool:
    global _importable
    if _importable is not None:
        return _importable
    try:
        from llama_cpp import Llama  # noqa: F401

        _importable = True
    except Exception:
        _importable = False
    return _importable


def model_path() -> Path:
    return MODEL_PATH


def model_present() -> bool:
    p = MODEL_PATH
    return p.is_file() and p.stat().st_size >= MIN_BYTES


def inference_ready() -> bool:
    """Модель уже в ОЗУ (без попытки загрузки)."""
    return _inference_ready


def is_loading_into_ram() -> bool:
    return _loading_ram


def _write_download_status(
    *,
    phase: str,
    progress: int,
    message: str,
    bytes_done: int = 0,
    bytes_total: int = 0,
) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "phase": phase,
        "progress": progress,
        "message": message,
        "bytes_done": bytes_done,
        "bytes_total": bytes_total or EXPECTED_DOWNLOAD_BYTES,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    DOWNLOAD_STATUS_PATH.write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def _clear_download_status() -> None:
    DOWNLOAD_STATUS_PATH.unlink(missing_ok=True)


def mark_download_starting(message: str = "Запуск загрузки модели в Jarvis…") -> None:
    """Сразу выставить фазу downloading (UI /api/status до первого байта)."""
    done = PART_PATH.stat().st_size if PART_PATH.is_file() else 0
    total = EXPECTED_DOWNLOAD_BYTES
    pct = min(99, int(done * 100 / total)) if done and total else 0
    _write_download_status(
        phase="downloading",
        progress=pct,
        message=message,
        bytes_done=done,
        bytes_total=total,
    )


def mark_download_error(message: str) -> None:
    _write_download_status(
        phase="error",
        progress=0,
        message=message[:240],
        bytes_done=PART_PATH.stat().st_size if PART_PATH.is_file() else 0,
        bytes_total=EXPECTED_DOWNLOAD_BYTES,
    )


def get_download_status() -> dict:
    """Прогресс скачивания GGUF внутрь Jarvis (по .part и файлу статуса)."""
    if model_present():
        _clear_download_status()
        sz = MODEL_PATH.stat().st_size
        return {
            "phase": "complete",
            "progress": 100,
            "message": "Файл модели в Jarvis (backend/data/models)",
            "bytes_done": sz,
            "bytes_total": sz,
        }

    meta: dict = {}
    if DOWNLOAD_STATUS_PATH.is_file():
        try:
            meta = json.loads(DOWNLOAD_STATUS_PATH.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    if PART_PATH.is_file():
        done = PART_PATH.stat().st_size
        total = int(meta.get("bytes_total") or 0) or EXPECTED_DOWNLOAD_BYTES
        pct = min(99, int(done * 100 / total)) if total > 0 else 0
        msg = (meta.get("message") or "").strip() or (
            f"Скачивание в Jarvis… {pct}% ({_fmt_mb(done)} / {_fmt_mb(total)})"
        )
        return {
            "phase": "downloading",
            "progress": pct,
            "message": msg,
            "bytes_done": done,
            "bytes_total": total,
        }

    if meta.get("phase") == "downloading":
        return {
            "phase": "downloading",
            "progress": int(meta.get("progress") or 0),
            "message": meta.get("message") or "Скачивание…",
            "bytes_done": int(meta.get("bytes_done") or 0),
            "bytes_total": int(meta.get("bytes_total") or EXPECTED_DOWNLOAD_BYTES),
        }

    if meta.get("phase") == "error":
        return {
            "phase": "error",
            "progress": 0,
            "message": meta.get("message") or "Ошибка загрузки",
            "bytes_done": int(meta.get("bytes_done") or 0),
            "bytes_total": int(meta.get("bytes_total") or EXPECTED_DOWNLOAD_BYTES),
        }

    return {
        "phase": "idle",
        "progress": 0,
        "message": "",
        "bytes_done": 0,
        "bytes_total": EXPECTED_DOWNLOAD_BYTES,
    }


def _is_cpu_block_error(err: str | None) -> bool:
    low = (err or "").lower()
    return "c000001d" in low or "illegal instruction" in low or "0xc000001d" in low


def llama_cpu_blocked() -> bool:
    """llama-cpp на этом CPU не работает — не повторять загрузку в ОЗУ."""
    if CPU_BLOCK_FLAG.is_file():
        return True
    return bool(_load_attempted and _load_error and _is_cpu_block_error(_load_error))


def mark_llama_cpu_blocked() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    CPU_BLOCK_FLAG.write_text(_load_error or "cpu_blocked", encoding="utf-8")


def get_ram_status() -> dict:
    """Статус загрузки весов в ОЗУ ПК (llama-cpp)."""
    if llama_cpu_blocked():
        return {
            "phase": "skipped",
            "progress": 0,
            "message": "llama-cpp не поддерживается этим CPU — используется Ollama",
        }
    if _inference_ready:
        return {
            "phase": "ready",
            "progress": 100,
            "message": "Модель в ОЗУ ПК — готова к ответам",
        }
    if _loading_ram:
        return {
            "phase": "loading",
            "progress": -1,
            "message": "Загрузка Qwen в память ПК…",
        }
    if _load_attempted and _load_error:
        err = (_load_error or "Ошибка загрузки в ОЗУ")[:200]
        if _is_cpu_block_error(err):
            mark_llama_cpu_blocked()
            return {
                "phase": "skipped",
                "progress": 0,
                "message": "llama-cpp не поддерживается этим CPU — используется Ollama",
            }
        return {"phase": "error", "progress": 0, "message": f"Не удалось загрузить в ОЗУ: {err}"}
    if model_present():
        return {
            "phase": "pending",
            "progress": 0,
            "message": "Файл в Jarvis — ожидает загрузки в ОЗУ",
        }
    return {"phase": "idle", "progress": 0, "message": ""}


def _fmt_mb(n: int) -> str:
    return f"{n // (1024 * 1024)} МБ"


def _write_meta(extra: dict | None = None) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "filename": MODEL_FILENAME,
        "path": str(MODEL_PATH),
        "bytes": MODEL_PATH.stat().st_size if MODEL_PATH.is_file() else 0,
        "source": "huggingface_gguf",
        "url": DEFAULT_DOWNLOAD_URL,
        "label": MODEL_LABEL,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        data.update(extra)
    META_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def download_model(
    *,
    force: bool = False,
    on_progress: Callable[[int, str], None] | None = None,
) -> dict:
    """
    Скачивает GGUF в backend/data/models/.
    on_progress(percent: int, message: str) — опционально.
    """
    if model_present() and not force:
        return {
            "ok": True,
            "skipped": True,
            "path": str(MODEL_PATH),
            "bytes": MODEL_PATH.stat().st_size,
            "message": f"Модель {MODEL_LABEL} уже внутри Jarvis (backend/data/models)",
        }

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    part = PART_PATH
    max_retries = 100

    def _safe_unlink_part() -> bool:
        if not part.exists():
            return True
        try:
            part.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    if force:
        _safe_unlink_part()

    last_err = ""
    for attempt in range(max_retries):
        resume_at = part.stat().st_size if part.is_file() else 0
        try:
            headers: dict[str, str] = {}
            if resume_at > 0:
                headers["Range"] = f"bytes={resume_at}-"

            with httpx.stream(
                "GET",
                DEFAULT_DOWNLOAD_URL,
                headers=headers,
                follow_redirects=True,
                timeout=httpx.Timeout(connect=60.0, read=None, write=60.0, pool=60.0),
                trust_env=False,
            ) as resp:
                if resume_at > 0 and resp.status_code == 416:
                    if not _safe_unlink_part():
                        return {
                            "ok": False,
                            "error": "download_in_progress",
                            "message": "Файл загрузки занят — дождитесь завершения.",
                        }
                    resp.close()
                    return download_model(force=force, on_progress=on_progress)

                resp.raise_for_status()
                append = resume_at > 0 and resp.status_code == 206
                if resume_at > 0 and not append:
                    if not _safe_unlink_part():
                        return {
                            "ok": False,
                            "error": "download_in_progress",
                            "message": "Не удалось продолжить — файл .part занят.",
                        }
                    resume_at = 0

                chunk_len = int(resp.headers.get("content-length") or 0)
                total = (resume_at + chunk_len) if append else chunk_len
                if not total:
                    total = EXPECTED_DOWNLOAD_BYTES
                done = resume_at
                _write_download_status(
                    phase="downloading",
                    progress=min(99, int(done * 100 / total)) if total else 0,
                    message=f"Скачивание {MODEL_LABEL} в Jarvis…",
                    bytes_done=done,
                    bytes_total=total,
                )
                mode = "ab" if append else "wb"
                if mode == "wb" and part.exists() and not _safe_unlink_part():
                    return {
                        "ok": False,
                        "error": "download_in_progress",
                        "message": "Загрузка уже идёт (файл .part занят).",
                    }

                with part.open(mode) as f:
                    for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        if total > 0:
                            pct = min(99, int(done * 100 / total))
                            _write_download_status(
                                phase="downloading",
                                progress=pct,
                                message=(
                                    f"Скачивание в Jarvis… {pct}% "
                                    f"({_fmt_mb(done)} / {_fmt_mb(total)})"
                                ),
                                bytes_done=done,
                                bytes_total=total,
                            )
                            if on_progress:
                                on_progress(
                                    pct,
                                    f"Загрузка {MODEL_LABEL}… "
                                    f"{done // (1024 * 1024)} / {total // (1024 * 1024)} МБ",
                                )

            if part.stat().st_size < MIN_BYTES:
                raise RuntimeError("download_incomplete")

            part.replace(MODEL_PATH)
            _clear_download_status()
            _write_meta()
            if on_progress:
                on_progress(100, f"{MODEL_LABEL} установлена в Jarvis")
            return {
                "ok": True,
                "skipped": False,
                "path": str(MODEL_PATH),
                "bytes": MODEL_PATH.stat().st_size,
                "message": f"Модель {MODEL_LABEL} загружена внутрь Jarvis (backend/data/models)",
            }
        except Exception as e:
            last_err = str(e)[:300]
            wait = min(60, 5 + attempt * 2)
            done = part.stat().st_size if part.is_file() else 0
            pct = min(99, int(done * 100 / EXPECTED_DOWNLOAD_BYTES)) if done else 0
            _write_download_status(
                phase="downloading",
                progress=pct,
                message=(
                    f"Обрыв связи ({attempt + 1}/{max_retries}), "
                    f"повтор через {wait} с… ({_fmt_mb(done)} уже в Jarvis)"
                ),
                bytes_done=done,
                bytes_total=EXPECTED_DOWNLOAD_BYTES,
            )
            if on_progress:
                on_progress(pct, f"Пауза {wait} с, затем продолжение…")
            if attempt + 1 >= max_retries:
                break
            time.sleep(wait)

    return {
        "ok": False,
        "error": "download_failed",
        "message": last_err or "Загрузка прервана",
    }


def _get_llama():
    global _llama, _load_error, _inference_ready, _loading_ram
    if _llama is not None:
        return _llama
    if not model_present() or not llama_importable():
        raise RuntimeError(f"Встроенная {MODEL_LABEL} не готова (нет файла или llama-cpp)")

    from llama_cpp import Llama

    with _llama_lock:
        if _llama is not None:
            return _llama
        cores = os.cpu_count() or 4
        n_threads = max(4, cores)
        _loading_ram = True
        try:
            _llama = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=8192,
                n_threads=n_threads,
                n_batch=512,
                verbose=False,
            )
            _inference_ready = True
            _load_error = None
            return _llama
        except Exception as e:
            _load_error = str(e)[:200]
            _inference_ready = False
            if _is_cpu_block_error(_load_error):
                mark_llama_cpu_blocked()
            raise
        finally:
            _loading_ram = False


def embedded_inference_ready() -> bool:
    """Файл на диске и llama-cpp смогли загрузить модель в RAM."""
    global _load_attempted, _inference_ready
    if _inference_ready:
        return True
    if llama_cpu_blocked():
        return False
    if not model_present() or not llama_importable():
        return False
    if _load_attempted and not _inference_ready:
        return False
    _load_attempted = True
    try:
        _get_llama()
        return True
    except Exception:
        return False


def unload_from_ram() -> None:
    """Выгрузить GGUF из ОЗУ (переключатель в сайдбаре)."""
    global _llama, _inference_ready, _load_attempted, _loading_ram, _load_error
    with _llama_lock:
        _llama = None
        _inference_ready = False
        _load_attempted = False
        _loading_ram = False
        _load_error = None


def start_ram_load_async() -> None:
    """Фоновая загрузка GGUF в ОЗУ (только если пользователь включил Qwen в RAM)."""
    from modules.local_qwen import is_qwen_ram_enabled

    if not is_qwen_ram_enabled() or llama_cpu_blocked():
        return

    def _run() -> None:
        try:
            embedded_inference_ready()
        except Exception:
            pass

    if _inference_ready or _loading_ram:
        return
    threading.Thread(
        target=_run, name="jarvis-qwen-ram-load", daemon=True
    ).start()


def embedded_available() -> bool:
    return embedded_inference_ready()


def embedded_file_installed() -> bool:
    return model_present()


def get_load_error() -> str | None:
    return _load_error


def embedded_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
    max_tokens: int = 1024,
) -> tuple[str, int]:
    llm = _get_llama()
    with _llama_lock:
        out = llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    choice = (out.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = (msg.get("content") or "").strip()
    usage = out.get("usage") or {}
    tokens = int(usage.get("total_tokens") or max(1, len(text) // 4))
    return text, tokens


def warmup_async() -> None:
    def _run() -> None:
        try:
            if embedded_available():
                embedded_chat(
                    [{"role": "user", "content": "ok"}],
                    temperature=0.0,
                    max_tokens=4,
                )
        except Exception:
            pass

    threading.Thread(target=_run, name="jarvis-qwen-embedded-warmup", daemon=True).start()
