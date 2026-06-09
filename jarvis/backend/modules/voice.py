"""
Голос Jarvis: базовый сэмпл, студия, XTTS-v2 (фоновая загрузка).
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import wave
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from modules.app_paths import bundle_root, user_data_dir

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = user_data_dir()
ASSETS_VOICE_DIR = bundle_root() / "assets" / "voice"
VOICE_DIR = DATA_DIR / "voice"
# Coqui TTS / XTTS-v2 — только внутри Jarvis (не %LOCALAPPDATA%)
COQUI_DATA_ROOT = DATA_DIR
JARVIS_TTS_DATA_DIR = DATA_DIR / "tts"
VOICE_SAMPLES_DIR = DATA_DIR / "voice_samples"
TTS_CACHE_DIR = VOICE_DIR / "generated"
BASE_VOICE_PATH = VOICE_DIR / "jarvis_base.ogg"
BASE_VOICE_META = VOICE_DIR / "jarvis_base.json"
BUNDLED_KOSCHEY = ASSETS_VOICE_DIR / "koschey_silero.ogg"
XTTS_STATE_FILE = VOICE_DIR / "xtts_state.json"
AUDIO_EXTS = {
    ".ogg",
    ".wav",
    ".wave",
    ".mp3",
    ".mpeg",
    ".webm",
    ".m4a",
    ".mp4",
    ".flac",
    ".aac",
    ".opus",
}
MAX_BASE_VOICE_BYTES = 15 * 1024 * 1024  # 15 МБ
MAX_SLOT_AUDIO_BYTES = 10 * 1024 * 1024  # 10 МБ
MIN_AUDIO_BYTES = 800
KOSCHEY_META_FILENAME = "Кощей_silero.ogg"

OPTIMAL_SEC_MIN = 12
TARGET_RATE = 24000
TTS_MAX_CHARS = 4000

_synth_lock = threading.Lock()


def ensure_coqui_inside_jarvis() -> Path:
    """Перенаправляет кэш Coqui TTS в backend/data/tts (до import TTS)."""
    JARVIS_TTS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["XDG_DATA_HOME"] = str(COQUI_DATA_ROOT.resolve())
    return JARVIS_TTS_DATA_DIR


def get_jarvis_tts_models_dir() -> Path:
    return JARVIS_TTS_DATA_DIR / "tts_models"


def xtts_weights_in_jarvis() -> tuple[bool, str | None]:
    """Есть ли файлы весов XTTS в папке Jarvis."""
    root = JARVIS_TTS_DATA_DIR
    if not root.is_dir():
        return False, None
    for p in root.rglob("*.pth"):
        if p.stat().st_size > 30_000_000 and "xtts" in str(p).lower():
            try:
                rel = p.parent.relative_to(_BACKEND_ROOT)
            except ValueError:
                rel = p.parent
            return True, str(rel).replace("\\", "/")
    for p in root.rglob("config.json"):
        if "xtts" in str(p).lower():
            try:
                rel = p.parent.relative_to(_BACKEND_ROOT)
            except ValueError:
                rel = p.parent
            return True, str(rel).replace("\\", "/")
    return False, None


def _migrate_legacy_coqui_cache() -> None:
    """Один раз копирует модель из старого %LOCALAPPDATA%\\tts, если в Jarvis пусто."""
    if xtts_weights_in_jarvis()[0]:
        return
    legacy = Path(os.environ.get("LOCALAPPDATA", "")) / "tts"
    if not legacy.is_dir():
        return
    dest = JARVIS_TTS_DATA_DIR
    try:
        if not any(dest.iterdir()):
            shutil.copytree(legacy, dest, dirs_exist_ok=True)
    except Exception:
        pass


def _xtts_status_extra() -> dict:
    weights, hint = xtts_weights_in_jarvis()
    return {
        "embedded_in_jarvis": True,
        "tts_data_dir": "backend/data/tts",
        "model_weights_present": weights,
        "model_path_hint": hint,
        "koschey_bundled": BUNDLED_KOSCHEY.is_file(),
        "koschey_path": "backend/assets/voice/koschey_silero.ogg"
        if BUNDLED_KOSCHEY.is_file()
        else None,
    }


# При импорте — Silero bootstrap вызывается из main.py (purge legacy XTTS).


class VoiceSlotStatus(str, Enum):
    EMPTY = "empty"
    CHECKING = "checking"
    READY = "ready"
    ERROR = "error"


@dataclass
class SlotState:
    slot: int
    status: VoiceSlotStatus = VoiceSlotStatus.EMPTY
    message: str = "Пусто"
    duration_sec: float | None = None
    filename: str | None = None


@dataclass
class XttsDownloadState:
    status: str = "idle"  # idle | installing_deps | downloading_model | ready | error
    progress: int = 0
    message: str = "Не загружено"
    error: str | None = None
    updated_at: str | None = None


_slots: dict[int, SlotState] = {1: SlotState(1), 2: SlotState(2), 3: SlotState(3)}
_slots_synced_from_disk = False
_xtts_state = XttsDownloadState()
_xtts_lock = threading.Lock()
_tts_instance = None
_xtts_download_thread: threading.Thread | None = None
_XTTS_STALE_SEC = 300
_xtts_importable_cache: bool | None = None


def _load_xtts_state() -> XttsDownloadState:
    global _xtts_state
    if XTTS_STATE_FILE.exists():
        try:
            raw = json.loads(XTTS_STATE_FILE.read_text(encoding="utf-8"))
            _xtts_state = XttsDownloadState(**raw)
        except Exception:
            pass
    return _xtts_state


def _touch_xtts_state() -> None:
    _xtts_state.updated_at = datetime.now(timezone.utc).isoformat()


def _save_xtts_state() -> None:
    _touch_xtts_state()
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    XTTS_STATE_FILE.write_text(
        json.dumps(
            {
                "status": _xtts_state.status,
                "progress": _xtts_state.progress,
                "message": _xtts_state.message,
                "error": _xtts_state.error,
                "updated_at": _xtts_state.updated_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _xtts_thread_alive() -> bool:
    t = _xtts_download_thread
    return t is not None and t.is_alive()


def _parse_updated_at(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _xtts_job_stale() -> bool:
    if _xtts_state.status not in ("installing_deps", "downloading_model"):
        return False
    if _xtts_thread_alive():
        return False
    ts = _parse_updated_at(_xtts_state.updated_at)
    if ts is None:
        return True
    return (time.time() - ts) > _XTTS_STALE_SEC


def _reset_stale_xtts_job() -> None:
    _xtts_state.status = "idle"
    _xtts_state.progress = 0
    _xtts_state.message = "Прервано — нажмите «Докачать библиотеки» снова"
    _xtts_state.error = None
    _save_xtts_state()


def _start_xtts_heartbeat(stop: threading.Event, progress_cap: int = 38) -> threading.Thread:
    messages = [
        "Установка torch (CPU) — может занять 10–20 мин…",
        "Скачивание пакетов pip…",
        "Установка Coqui TTS…",
        "Ожидание завершения pip…",
    ]

    def loop() -> None:
        tick = 0
        while not stop.wait(12):
            tick += 1
            with _xtts_lock:
                if _xtts_state.status != "installing_deps":
                    break
                base = max(_xtts_state.progress, 8)
                _xtts_state.progress = min(progress_cap, base + 1)
                _xtts_state.message = messages[tick % len(messages)]
                _save_xtts_state()

    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th


def get_xtts_status() -> dict:
    """Статус Silero TTS (поле xtts — совместимость со старым UI)."""
    from modules import silero_tts

    st = silero_tts.get_status()
    st.setdefault("python_ok_for_xtts", True)
    return st


def _check_xtts_importable() -> bool:
    """Совместимость: готовность Silero TTS."""
    try:
        from modules import silero_tts

        return silero_tts.is_ready()
    except Exception:
        return False


def _list_base_audio_files() -> list[Path]:
    """Все файлы базового/пользовательского голоса в каталоге voice."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    found: list[Path] = []
    for pattern in ("user_base.*", "jarvis_base.*"):
        for p in VOICE_DIR.glob(pattern):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
                found.append(p)
    return found


def _migrate_base_meta() -> None:
    """Старые meta без file_path — привязать к актуальному файлу на диске."""
    meta = _load_base_meta()
    if meta.get("file_path"):
        p = VOICE_DIR / Path(meta["file_path"]).name
        if p.is_file():
            return
    audio = _list_base_audio_files()
    if not audio:
        return
    chosen = max(audio, key=lambda p: p.stat().st_mtime)
    _write_base_meta(
        meta.get("filename") or chosen.name,
        meta.get("source") or "migrated",
        chosen.name,
    )


def _is_user_uploaded(meta: dict) -> bool:
    return meta.get("source") == "dev_panel_upload" or bool(meta.get("file_path"))


def _find_koschey_in_downloads() -> Path | None:
    downloads = Path.home() / "Downloads"
    if not downloads.is_dir():
        return None
    cands = [
        p
        for p in downloads.iterdir()
        if p.is_file() and p.suffix.lower() == ".ogg" and "silero" in p.name.lower()
    ]
    if not cands:
        return None
    for p in cands:
        low = p.name.lower()
        if "kosche" in low or "кощ" in low or "koshch" in low:
            return p
    non_adidas = [
        p
        for p in cands
        if "adidas" not in p.name.lower() and "адидас" not in p.name.lower()
    ]
    pool = non_adidas or cands
    return min(pool, key=lambda p: p.stat().st_size)


def _install_bundled_koschey() -> Path | None:
    """Базовый голос Джарвис — Кощей_silero.ogg в assets и data/voice."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_VOICE_DIR.mkdir(parents=True, exist_ok=True)
    src = BUNDLED_KOSCHEY if BUNDLED_KOSCHEY.is_file() else _find_koschey_in_downloads()
    if not src:
        return None
    if not BUNDLED_KOSCHEY.is_file():
        shutil.copy2(src, BUNDLED_KOSCHEY)
    if not BASE_VOICE_PATH.is_file() or BASE_VOICE_PATH.stat().st_size != src.stat().st_size:
        shutil.copy2(src, BASE_VOICE_PATH)
    _write_base_meta(KOSCHEY_META_FILENAME, "bundled_koschey", BASE_VOICE_PATH.name)
    return BASE_VOICE_PATH


def ensure_default_base_voice() -> Path | None:
    """Кощей_silero.ogg — базовый голос; не перезаписывает загрузку из dev-панели."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    _migrate_base_meta()
    meta = _load_base_meta()
    if _is_user_uploaded(meta):
        return _resolve_base_voice_file()

    if BASE_VOICE_PATH.is_file():
        if meta.get("source") != "bundled_koschey":
            _write_base_meta(
                meta.get("filename") or KOSCHEY_META_FILENAME,
                meta.get("source") or "default_existing",
                BASE_VOICE_PATH.name,
            )
        return BASE_VOICE_PATH

    return _install_bundled_koschey()


def _write_base_meta(filename: str, source: str, file_path: str) -> None:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    BASE_VOICE_META.write_text(
        json.dumps(
            {"filename": filename, "source": source, "file_path": file_path},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _load_base_meta() -> dict:
    if BASE_VOICE_META.exists():
        try:
            return json.loads(BASE_VOICE_META.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _resolve_base_voice_file() -> Path | None:
    """Файл, который должен играть по кнопке «Голос (Джарвис)»."""
    _migrate_base_meta()
    meta = _load_base_meta()

    if meta.get("file_path"):
        p = VOICE_DIR / Path(meta["file_path"]).name
        if p.is_file():
            return p

    if _is_user_uploaded(meta):
        audio = _list_base_audio_files()
        if audio:
            chosen = max(audio, key=lambda p: p.stat().st_mtime)
            _write_base_meta(
                meta.get("filename") or chosen.name,
                meta.get("source") or "dev_panel_upload",
                chosen.name,
            )
            return chosen
        return None

    ensure_default_base_voice()
    if BASE_VOICE_PATH.is_file():
        return BASE_VOICE_PATH
    return None


def get_base_voice_info() -> dict:
    path = _resolve_base_voice_file()
    meta = _load_base_meta()
    active_slot = _get_active_studio_slot()
    return {
        "exists": path is not None,
        "path": str(path) if path else None,
        "filename": meta.get("filename", path.name if path else None),
        "source": meta.get("source", "unknown"),
        "file_path": meta.get("file_path"),
        "active_studio_slot": active_slot,
        "size_bytes": path.stat().st_size if path else 0,
        "version": int(path.stat().st_mtime) if path else 0,
    }


def is_audio_filename(filename: str) -> bool:
    return Path(filename).suffix.lower() in AUDIO_EXTS


def check_audio_size(data: bytes, limit: int = MAX_BASE_VOICE_BYTES) -> str | None:
    if len(data) < MIN_AUDIO_BYTES:
        return "Файл слишком маленький или пустой."
    if len(data) > limit:
        cap = limit / (1024 * 1024)
        got = len(data) / (1024 * 1024)
        return f"Слишком большой файл ({got:.1f} МБ). Лимит: {cap:.0f} МБ."
    return None


def set_base_voice(data: bytes, filename: str) -> dict:
    """Сохраняет загрузку пользователя в user_base.* — отдельно от дефолтного jarvis_base.ogg."""
    err = check_audio_size(data, MAX_BASE_VOICE_BYTES)
    if err:
        raise ValueError(err)

    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    for old in _list_base_audio_files():
        old.unlink(missing_ok=True)

    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXTS:
        ext = ".ogg"
    dest_name = f"user_base{ext}"
    dest = VOICE_DIR / dest_name
    dest.write_bytes(data)
    _write_base_meta(filename, "dev_panel_upload", dest_name)
    return get_base_voice_info()


def get_preview_path() -> Path | None:
    """Только базовый голос пользователя / дефолт — без слотов студии."""
    return _resolve_base_voice_file()


def _sync_slots_from_disk() -> None:
    """После перезапуска сервера — подхватить загруженные образцы из voice_samples/."""
    global _slots_synced_from_disk
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for n in (1, 2, 3):
        state = _slots[n]
        if state.status == VoiceSlotStatus.CHECKING:
            continue
        found: Path | None = None
        for ext in AUDIO_EXTS:
            p = VOICE_SAMPLES_DIR / f"slot_{n}{ext}"
            if p.is_file():
                found = p
                break
        if not found:
            if _slots_synced_from_disk and state.status == VoiceSlotStatus.READY:
                state.status = VoiceSlotStatus.EMPTY
                state.message = "Пусто"
                state.duration_sec = None
                state.filename = None
            continue
        data = found.read_bytes()
        dur = _read_wav_duration(data) or _estimate_duration(len(data), found.suffix.lower())
        state.status = VoiceSlotStatus.READY
        state.message = "Готово (Звук валиден)"
        state.filename = state.filename or found.name
        state.duration_sec = round(dur, 1)
    _slots_synced_from_disk = True


def _get_active_studio_slot() -> int | None:
    _sync_slots_from_disk()
    for n in (1, 2, 3):
        if _slots[n].status == VoiceSlotStatus.READY:
            return n
    return None


def get_slots() -> list[dict]:
    _sync_slots_from_disk()
    return [_slot_dict(s) for s in _slots.values()]


def _read_wav_duration(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            return w.getnframes() / w.getframerate() if w.getframerate() else None
    except Exception:
        return None


def _estimate_duration(size: int, fmt: str) -> float:
    if fmt in (".wav", ".wave"):
        return size / (TARGET_RATE * 2)
    return size / 16000


def validate_audio(slot: int, data: bytes, filename: str) -> dict:
    if slot not in (1, 2, 3):
        return {"slot": slot, "status": "error", "message": "Неверный слот"}

    state = _slots[slot]
    state.status = VoiceSlotStatus.CHECKING
    state.message = "Проверка..."

    size_err = check_audio_size(data, MAX_SLOT_AUDIO_BYTES)
    if size_err:
        state.status = VoiceSlotStatus.ERROR
        state.message = size_err[:80]
        return _slot_dict(state)

    if len(data) < 1000:
        state.status = VoiceSlotStatus.ERROR
        state.message = "Ошибка (Короткий)"
        return _slot_dict(state)

    ext = Path(filename).suffix.lower()
    if ext not in AUDIO_EXTS:
        state.status = VoiceSlotStatus.ERROR
        state.message = "Неподдерживаемый формат"
        return _slot_dict(state)
    duration = _read_wav_duration(data) or _estimate_duration(len(data), ext)

    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VOICE_SAMPLES_DIR / f"slot_{slot}{ext if ext else '.wav'}"
    out_path.write_bytes(data)

    state.duration_sec = round(duration, 1)
    state.filename = filename

    if duration < 5:
        state.status, state.message = VoiceSlotStatus.ERROR, "Ошибка (Короткий)"
    elif duration < OPTIMAL_SEC_MIN:
        state.status = VoiceSlotStatus.ERROR
        state.message = f"Ошибка (Короткий: {state.duration_sec}с, нужно 15–20)"
    elif duration > 45:
        state.status, state.message = VoiceSlotStatus.ERROR, "Ошибка (Слишком длинный)"
    elif len(data) < 8000 and ext not in (".wav", ".wave", ".ogg"):
        state.status, state.message = VoiceSlotStatus.ERROR, "Ошибка (Шум/Качество)"
    else:
        state.status, state.message = VoiceSlotStatus.READY, "Готово (Звук валиден)"

    return _slot_dict(state)


def _slot_dict(state: SlotState) -> dict:
    return {
        "slot": state.slot,
        "status": state.status.value,
        "message": state.message,
        "duration_sec": state.duration_sec,
        "filename": state.filename,
    }


def _python_version_label() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _python_ok_for_xtts() -> tuple[bool, str]:
    """Coqui TTS поддерживает только Python 3.9–3.11 (не 3.12+)."""
    minor = sys.version_info.minor
    if sys.version_info.major == 3 and 9 <= minor <= 11:
        return True, ""
    return (
        False,
        f"XTTS-v2 (библиотека TTS) не поддерживает Python {_python_version_label()}. "
        "Нужен Python 3.9, 3.10 или 3.11. Установите Python 3.11 с python.org, "
        "удалите папку backend\\venv и перезапустите start.bat. "
        "Базовый голос (загрузка .ogg) и студия слотов работают без XTTS.",
    )


def _pip_install(packages: list[str], extra_args: list[str] | None = None) -> None:
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
        "wheel",
        "setuptools",
    ]
    subprocess.run(cmd, capture_output=True, text=True, check=False)

    cmd = [sys.executable, "-m", "pip", "install", "--no-warn-script-location"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(packages)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "pip install failed")[-2500:]
        raise RuntimeError(tail.strip())


def _install_pysocks_if_present() -> None:
    wheel = Path(__file__).resolve().parent.parent / "wheels" / "PySocks-1.7.1-py3-none-any.whl"
    if wheel.is_file():
        _pip_install([str(wheel)])


def _install_xtts_dependencies() -> None:
    stop = threading.Event()
    heartbeat = _start_xtts_heartbeat(stop)
    try:
        _install_pysocks_if_present()
        _xtts_state.progress = 15
        _xtts_state.message = "Установка torch, torchaudio (CPU)…"
        _save_xtts_state()
        _pip_install(
            ["torch", "torchaudio"],
            extra_args=["--index-url", "https://download.pytorch.org/whl/cpu"],
        )
        _xtts_state.progress = 28
        _xtts_state.message = "Установка Coqui TTS…"
        _save_xtts_state()
        _pip_install(["TTS>=0.22.0", "transformers>=4.33.0", "einops"])
    finally:
        stop.set()
        heartbeat.join(timeout=1)


def _run_xtts_download() -> None:
    global _xtts_state, _tts_instance, _xtts_download_thread
    with _xtts_lock:
        try:
            ok, err = _python_ok_for_xtts()
            if not ok:
                raise RuntimeError(err)

            _xtts_state.status = "installing_deps"
            _xtts_state.progress = 10
            _xtts_state.message = "Установка TTS, torch, torchaudio…"
            _xtts_state.error = None
            _save_xtts_state()

            if not _check_xtts_importable():
                _install_xtts_dependencies()

            ensure_coqui_inside_jarvis()
            _xtts_state.status = "downloading_model"
            _xtts_state.progress = 40
            _xtts_state.message = (
                "Загрузка XTTS-v2 в Jarvis (backend/data/tts, ~1.8 ГБ)…"
            )
            _save_xtts_state()

            from TTS.api import TTS

            _tts_instance = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=True,
            )

            _xtts_state.status = "ready"
            _xtts_state.progress = 100
            _xtts_state.message = "XTTS-v2 в Jarvis (backend/data/tts)"
            _save_xtts_state()
        except Exception as e:
            _xtts_state.status = "error"
            msg = str(e).strip()
            if len(msg) > 500:
                msg = msg[:500] + "…"
            _xtts_state.error = msg
            _xtts_state.message = f"Ошибка: {msg}"
            _save_xtts_state()
        finally:
            _xtts_download_thread = None


def start_xtts_download() -> dict:
    """Установка Silero TTS (раньше XTTS)."""
    from modules import silero_tts

    return silero_tts.start_install()


def _tts_state_ready() -> bool:
    return _xtts_state.status == "ready"


def _plain_text_for_tts(text: str) -> str:
    from modules.speech_text import prepare_text_for_tts

    t = prepare_text_for_tts(text)
    try:
        from modules.icq_smileys import strip_icq_tokens_for_tts

        t = strip_icq_tokens_for_tts(t)
    except Exception:
        pass
    return t[:TTS_MAX_CHARS]


def get_silero_status() -> dict:
    from modules import silero_tts

    return silero_tts.get_status()


def start_silero_install() -> dict:
    from modules import silero_tts

    return silero_tts.start_install()


def _resolve_speaker_reference() -> tuple[Path | None, str]:
    """Голос Jarvis — Кощей (базовый файл); слоты студии только если базы нет."""
    ensure_default_base_voice()
    base = _resolve_base_voice_file()
    if base and base.is_file():
        return base, "koschey_base"
    _sync_slots_from_disk()
    VOICE_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for n in (1, 2, 3):
        if _slots[n].status != VoiceSlotStatus.READY:
            continue
        for ext in (".wav", ".ogg", ".mp3", ".webm", ".m4a"):
            p = VOICE_SAMPLES_DIR / f"slot_{n}{ext}"
            if p.is_file():
                return p, f"studio_slot_{n}_fallback"
    installed = _install_bundled_koschey()
    if installed:
        return installed, "koschey_bundled"
    return None, "none"


def _get_xtts_model():
    global _tts_instance
    ensure_coqui_inside_jarvis()
    if _tts_instance is not None:
        return _tts_instance
    with _xtts_lock:
        if _tts_instance is not None:
            return _tts_instance
        from TTS.api import TTS

        _tts_instance = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=False,
        )
        return _tts_instance


def _synthesize_xtts(text: str, speaker: Path, dest: Path) -> None:
    tts = _get_xtts_model()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tts.tts_to_file(
        text=text,
        file_path=str(dest),
        speaker_wav=str(speaker),
        language="ru",
    )


def _synthesize_edge_tts(
    text: str,
    dest: Path,
    *,
    rate: str = "+0%",
    pitch: str = "+0Hz",
) -> None:
    import asyncio

    import edge_tts

    async def run() -> None:
        communicate = edge_tts.Communicate(
            text,
            "ru-RU-DmitryNeural",
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(str(dest))

    dest.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(run())


def synthesize_chat_speech(text: str) -> dict:
    """Озвучка текста чата через Silero TTS v5 (ru)."""
    import hashlib

    from modules import silero_tts

    plain = _plain_text_for_tts(text)
    if not plain:
        return {"ok": False, "error": "empty", "message": "Пустой текст"}

    speaker = silero_tts.get_selected_speaker()
    tempo = silero_tts.get_tempo()
    model_id = silero_tts.SILERO_MODEL_ID
    stress_lex = silero_tts.get_stress_lexicon()
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(
        f"{plain}|{speaker}|{model_id}|{tempo}|{json.dumps(stress_lex, sort_keys=True, ensure_ascii=False)}".encode()
    ).hexdigest()[:20]
    out_wav = TTS_CACHE_DIR / f"{key}.wav"

    if out_wav.is_file():
        return {
            "ok": True,
            "audio_url": f"/api/voice/generated/{out_wav.name}",
            "engine": "silero_cache",
            "speaker": speaker,
            "model": model_id,
        }

    with _synth_lock:
        if out_wav.is_file():
            return {
                "ok": True,
                "audio_url": f"/api/voice/generated/{out_wav.name}",
                "engine": "silero_cache",
                "speaker": speaker,
                "model": model_id,
            }
        try:
            silero_tts.synthesize(plain, out_wav, speaker=speaker, tempo=tempo)
        except Exception as e:
            msg = str(e).strip()
            if len(msg) > 400:
                msg = msg[:400] + "…"
            hint = "Установите Silero: Настройки → Голос и озвучка → «Установить Silero»."
            if "torch" in msg.lower() or "silero" in msg.lower():
                hint = "Нажмите «Установить Silero» в настройках голоса."
            return {
                "ok": False,
                "error": "synthesis_failed",
                "message": msg,
                "detail": hint,
            }

    return {
        "ok": True,
        "audio_url": f"/api/voice/generated/{out_wav.name}",
        "engine": "silero",
        "speaker": speaker,
        "tempo": tempo,
        "message": f"Озвучено (Silero {model_id}, {speaker}, темп {tempo}×)",
    }


def get_generated_audio_path(filename: str) -> Path | None:
    if ".." in filename or "/" in filename or "\\" in filename:
        return None
    p = TTS_CACHE_DIR / filename
    if p.is_file() and p.suffix.lower() in (".wav", ".mp3"):
        return p
    return None


def get_chat_voice_readiness() -> dict:
    """Готовность озвучки ответов в чате (Silero TTS v5)."""
    from modules import silero_tts
    from modules.service_flags import silero_service_enabled

    speaker = silero_tts.get_selected_speaker()
    tempo = silero_tts.get_tempo()
    model_id = silero_tts.SILERO_MODEL_ID
    silero_ready = bool(silero_service_enabled() and silero_tts.is_ready())
    if silero_ready:
        message = f"Silero {model_id} · {speaker} · темп {tempo}×"
    elif not silero_service_enabled():
        message = "Silero выключен в настройках сервисов"
    elif not silero_tts._importable():
        message = "Установите Silero: Настройки → Голос и озвучка"
    else:
        message = "Нажмите «Установить Silero» в настройках голоса"

    return {
        "ready": silero_ready,
        "engine": "silero",
        "model": model_id,
        "speaker": speaker,
        "tempo": tempo,
        "silero_ready": silero_ready,
        "xtts_ready": silero_ready,
        "edge_tts": False,
        "edge_tts_error": None,
        "speaker_source": f"silero:{speaker}",
        "speaker_path": None,
        "message": message,
    }


def mock_tts_speak(text: str, slot: int = 1) -> dict:
    result = synthesize_chat_speech(text)
    if result.get("ok"):
        return {
            "spoken": True,
            "message": result.get("message", "Озвучено"),
            "audio_url": result.get("audio_url"),
            "text_preview": text[:80],
            "engine": result.get("engine"),
        }
    return {
        "spoken": False,
        "message": result.get("message", "Не удалось озвучить"),
        "text_preview": text[:80],
    }
