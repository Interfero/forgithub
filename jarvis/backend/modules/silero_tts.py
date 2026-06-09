"""
Silero TTS v5 (ru) — локальная озвучка Jarvis без облака.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
SILERO_DIR = DATA_DIR / "silero"
LEGACY_TTS_DIR = DATA_DIR / "tts"
LEGACY_XTTS_STATE = DATA_DIR / "voice" / "xtts_state.json"
PURGE_FLAG = SILERO_DIR / ".legacy_tts_purged"
SILERO_STATE_FILE = SILERO_DIR / "silero_state.json"
SILERO_MODEL_ID = "v5_ru"
SILERO_LANGUAGE = "ru"
SILERO_SAMPLE_RATE = 48_000
DEFAULT_SPEAKER = "aidar"
DEFAULT_TEMPO = 1.0
MIN_TEMPO = 0.75
MAX_TEMPO = 1.5

# Автоударения и ё в Silero v5 (см. snakers4/silero-models)
SILERO_STRESS_FLAGS: dict[str, bool] = {
    "put_accent": True,
    "put_yo": True,
    "put_stress_homo": True,
    "put_yo_homo": True,
    "stress_single_vowel": True,
}

SILERO_VOICES: list[dict[str, str]] = [
    {"id": "aidar", "label": "Aidar", "description": "Мужской голос"},
    {"id": "baya", "label": "Baya", "description": "Женский голос"},
    {"id": "kseniya", "label": "Kseniya", "description": "Женский голос"},
    {"id": "xenia", "label": "Xenia", "description": "Женский голос"},
    {"id": "eugene", "label": "Eugene", "description": "Мужской голос"},
]
VALID_SPEAKER_IDS = frozenset(v["id"] for v in SILERO_VOICES)

_model = None
_model_lock = threading.Lock()
_install_thread: threading.Thread | None = None
_STALE_SEC = 300


@dataclass
class SileroState:
    status: str = "idle"
    progress: int = 0
    message: str = "Silero не установлен"
    error: str | None = None
    updated_at: str | None = None


_state = SileroState()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_cache_dir() -> Path:
    SILERO_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(SILERO_DIR.resolve()))
    return SILERO_DIR


def purge_legacy_tts_models(force: bool = False) -> dict[str, Any]:
    """Удаляет XTTS/Coqui и старые кэши с диска (один раз или по force)."""
    if PURGE_FLAG.is_file() and not force:
        return {"skipped": True, "removed": []}

    removed: list[str] = []
    targets = [
        LEGACY_TTS_DIR,
        Path(os.environ.get("LOCALAPPDATA", "")) / "tts",
        Path(os.environ.get("LOCALAPPDATA", "")) / "coqui",
        Path.home() / ".local" / "share" / "tts",
    ]
    for path in targets:
        if path.is_dir():
            try:
                shutil.rmtree(path, ignore_errors=True)
                removed.append(str(path))
            except Exception:
                pass
    if LEGACY_XTTS_STATE.is_file():
        try:
            LEGACY_XTTS_STATE.unlink(missing_ok=True)
            removed.append(str(LEGACY_XTTS_STATE))
        except Exception:
            pass

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "TTS", "coqui-tts"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        pass

    _ensure_cache_dir()
    PURGE_FLAG.write_text(_now(), encoding="utf-8")
    return {"skipped": False, "removed": removed}


def _load_state() -> SileroState:
    global _state
    if SILERO_STATE_FILE.exists():
        try:
            raw = json.loads(SILERO_STATE_FILE.read_text(encoding="utf-8"))
            _state = SileroState(**raw)
        except Exception:
            pass
    return _state


def _save_state() -> None:
    _state.updated_at = _now()
    _ensure_cache_dir()
    SILERO_STATE_FILE.write_text(
        json.dumps(
            {
                "status": _state.status,
                "progress": _state.progress,
                "message": _state.message,
                "error": _state.error,
                "updated_at": _state.updated_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _clamp_tempo(value: float | str | None) -> float:
    try:
        t = float(value if value is not None else DEFAULT_TEMPO)
    except (TypeError, ValueError):
        t = DEFAULT_TEMPO
    return round(max(MIN_TEMPO, min(MAX_TEMPO, t)), 2)


def get_selected_speaker() -> str:
    from store import load_settings

    sp = str(load_settings().get("silero_speaker") or DEFAULT_SPEAKER).strip().lower()
    return sp if sp in VALID_SPEAKER_IDS else DEFAULT_SPEAKER


def get_tempo() -> float:
    from store import load_settings

    return _clamp_tempo(load_settings().get("silero_tempo"))


def set_voice_settings(
    speaker: str | None = None,
    tempo: float | None = None,
) -> dict[str, Any]:
    from store import save_settings

    patch: dict[str, Any] = {}
    if speaker is not None:
        sp = str(speaker).strip().lower()
        if sp not in VALID_SPEAKER_IDS:
            raise ValueError(f"Неизвестный голос: {speaker}")
        patch["silero_speaker"] = sp
    if tempo is not None:
        patch["silero_tempo"] = _clamp_tempo(tempo)
    if not patch:
        return get_voice_config()
    save_settings(patch)
    return get_voice_config()


def set_selected_speaker(speaker_id: str) -> str:
    return str(set_voice_settings(speaker=speaker_id)["selected"])


def get_voice_config() -> dict[str, Any]:
    return {
        "model": SILERO_MODEL_ID,
        "language": SILERO_LANGUAGE,
        "sample_rate": SILERO_SAMPLE_RATE,
        "selected": get_selected_speaker(),
        "tempo": get_tempo(),
        "tempo_min": MIN_TEMPO,
        "tempo_max": MAX_TEMPO,
        "tempo_default": DEFAULT_TEMPO,
        "stress_flags": SILERO_STRESS_FLAGS,
        "stress_lexicon": list_stress_lexicon(),
        "voices": SILERO_VOICES,
    }


def _normalize_plain(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower().replace("ё", "е"))


def plain_from_marked(marked: str) -> str:
    """Текст без «+» — ключ для поиска в фразе."""
    return re.sub(r"\s+", " ", marked.replace("+", "")).strip()


def parse_stress_line(line: str) -> tuple[str, str] | None:
    """Строка с «+» перед ударной гласной → (plain, marked)."""
    marked = (line or "").strip()
    if not marked or "+" not in marked:
        return None
    if marked.startswith("#"):
        return None
    plain = plain_from_marked(marked)
    if len(plain) < 2:
        return None
    return plain, marked


def get_stress_lexicon() -> dict[str, str]:
    """Словарь plain → marked для подстановки перед apply_tts."""
    from store import load_settings

    raw = load_settings().get("silero_stress_lexicon") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        plain = _normalize_plain(str(k))
        marked = str(v or "").strip()
        if plain and marked and "+" in marked:
            out[plain] = marked
    return out


def list_stress_lexicon() -> list[dict[str, str]]:
    return [
        {"plain": plain, "marked": marked}
        for plain, marked in sorted(get_stress_lexicon().items(), key=lambda x: x[0])
    ]


def save_stress_lexicon_lines(lines: str) -> list[dict[str, str]]:
    """Добавить/обновить записи из текста (по одной фразе на строку, с «+»)."""
    from store import load_settings, save_settings

    lex = get_stress_lexicon()
    added = 0
    for raw in (lines or "").splitlines():
        parsed = parse_stress_line(raw)
        if not parsed:
            continue
        plain, marked = parsed
        lex[_normalize_plain(plain)] = marked
        added += 1
    if added == 0 and not (lines or "").strip():
        return list_stress_lexicon()
    save_settings({"silero_stress_lexicon": lex})
    return list_stress_lexicon()


def delete_stress_lexicon_entry(plain: str) -> list[dict[str, str]]:
    from store import load_settings, save_settings

    lex = get_stress_lexicon()
    key = _normalize_plain(plain)
    if key in lex:
        del lex[key]
        save_settings({"silero_stress_lexicon": lex})
    return list_stress_lexicon()


def list_speakers() -> dict[str, Any]:
    return get_voice_config()


def _importable() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def _thread_alive() -> bool:
    return _install_thread is not None and _install_thread.is_alive()


def _job_stale() -> bool:
    if _state.status not in ("installing_deps", "downloading_model"):
        return False
    if _thread_alive():
        return False
    if not _state.updated_at:
        return True
    try:
        ts = datetime.fromisoformat(_state.updated_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return True
    return (time.time() - ts) > _STALE_SEC


def _reset_stale_job() -> None:
    _state.status = "idle"
    _state.progress = 0
    _state.message = "Установка прервана — нажмите «Установить Silero» снова"
    _state.error = None
    _save_state()


def _pip_install(packages: list[str], extra_args: list[str] | None = None) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools"]
    subprocess.run(cmd, capture_output=True, text=True, check=False)
    cmd = [sys.executable, "-m", "pip", "install", "--no-warn-script-location"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(packages)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "pip install failed")[-2500:]
        raise RuntimeError(tail.strip())


def _load_model(force: bool = False):
    global _model
    if _model is not None and not force:
        return _model
    with _model_lock:
        if _model is not None and not force:
            return _model
        import torch

        _ensure_cache_dir()
        device = torch.device("cpu")
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language=SILERO_LANGUAGE,
            speaker=SILERO_MODEL_ID,
            trust_repo=True,
        )
        model.to(device)
        _model = model
        return _model


def _run_install() -> None:
    global _install_thread, _state
    try:
        _state.status = "installing_deps"
        _state.progress = 12
        _state.message = "Установка torch (CPU)…"
        _state.error = None
        _save_state()

        if not _importable():
            _pip_install(
                ["torch"],
                extra_args=["--index-url", "https://download.pytorch.org/whl/cpu"],
            )
            _pip_install(["num2words"])

        _state.status = "downloading_model"
        _state.progress = 45
        _state.message = f"Загрузка Silero {SILERO_MODEL_ID}…"
        _save_state()

        _load_model(force=True)

        _state.status = "ready"
        _state.progress = 100
        _state.message = f"Silero {SILERO_MODEL_ID} готов (локально)"
        _save_state()
    except Exception as e:
        msg = str(e).strip()
        if len(msg) > 500:
            msg = msg[:500] + "…"
        _state.status = "error"
        _state.error = msg
        _state.message = f"Ошибка: {msg}"
        _save_state()
    finally:
        _install_thread = None


def start_install() -> dict[str, Any]:
    from modules.service_flags import silero_service_enabled

    global _install_thread
    _load_state()
    if not silero_service_enabled():
        _state.message = "Silero выключен в настройках"
        _save_state()
        return {**get_status(), "skipped": True, "service_disabled": True}
    if _job_stale():
        _reset_stale_job()
    if _state.status in ("installing_deps", "downloading_model") and _thread_alive():
        return {**get_status(), "already_installed": False, "skipped": True}
    if is_ready():
        _state.status = "ready"
        _state.progress = 100
        _state.message = "Silero уже установлен"
        _state.error = None
        _save_state()
        return {**get_status(), "already_installed": True, "skipped": True}

    _install_thread = threading.Thread(target=_run_install, daemon=True)
    _install_thread.start()
    _state.status = "installing_deps"
    _state.progress = 8
    _state.message = "Запуск установки Silero…"
    _save_state()
    return {**get_status(), "already_installed": False, "skipped": False}


def is_ready() -> bool:
    if not _importable():
        return False
    try:
        _load_model()
        return True
    except Exception:
        return False


def get_status() -> dict[str, Any]:
    _load_state()
    if _job_stale():
        _reset_stale_job()
    ready = is_ready()
    if ready and _state.status != "ready":
        _state.status = "ready"
        _state.progress = 100
        _state.message = f"Silero {SILERO_MODEL_ID} готов"
        _save_state()
    cfg = get_voice_config()
    return {
        "status": _state.status,
        "progress": _state.progress,
        "message": _state.message,
        "error": _state.error if _state.status == "error" else None,
        "importable": ready,
        "model": SILERO_MODEL_ID,
        "language": SILERO_LANGUAGE,
        "sample_rate": SILERO_SAMPLE_RATE,
        "engine": "silero",
        "selected_speaker": cfg["selected"],
        "tempo": cfg["tempo"],
        "stress_flags": SILERO_STRESS_FLAGS,
        "speakers": SILERO_VOICES,
        "cache_dir": "backend/data/silero",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def _adjust_tempo(audio, tempo: float):
    import numpy as np

    if abs(tempo - 1.0) < 0.02:
        return audio
    arr = np.squeeze(audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio))
    n = len(arr)
    if n < 2:
        return arr
    new_n = max(int(n / tempo), 2)
    x_old = np.linspace(0.0, 1.0, n)
    x_new = np.linspace(0.0, 1.0, new_n)
    return np.interp(x_new, x_old, arr).astype(np.float32)


def _save_wav(path: Path, audio, sample_rate: int) -> None:
    import numpy as np

    arr = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
    arr = np.squeeze(arr)
    arr = np.clip(arr, -1.0, 1.0)
    pcm = (arr * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


def synthesize(
    text: str,
    dest: Path,
    speaker: str | None = None,
    tempo: float | None = None,
) -> None:
    from modules.service_flags import silero_service_enabled

    if not silero_service_enabled():
        raise RuntimeError("Silero выключен в настройках")
    sp = (speaker or get_selected_speaker()).strip().lower()
    if sp not in VALID_SPEAKER_IDS:
        sp = DEFAULT_SPEAKER
    rate = _clamp_tempo(tempo if tempo is not None else get_tempo())
    model = _load_model()
    audio = model.apply_tts(
        text=text,
        speaker=sp,
        sample_rate=SILERO_SAMPLE_RATE,
        **SILERO_STRESS_FLAGS,
    )
    if abs(rate - 1.0) >= 0.02:
        audio = _adjust_tempo(audio, rate)
    _save_wav(dest, audio, SILERO_SAMPLE_RATE)


def preview_speaker(
    speaker: str,
    text: str = "Привет! Я Jarvis, ваш голосовой ассистент.",
    tempo: float | None = None,
) -> Path:
    from modules.speech_text import prepare_text_for_tts
    from modules.voice import TTS_CACHE_DIR

    sp = speaker.strip().lower()
    if sp not in VALID_SPEAKER_IDS:
        raise ValueError("Неизвестный голос")
    rate = _clamp_tempo(tempo if tempo is not None else get_tempo())
    spoken = prepare_text_for_tts(text)[:200]
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = TTS_CACHE_DIR / f"preview_{sp}_{int(rate * 100)}.wav"
    synthesize(spoken, dest, speaker=sp, tempo=rate)
    return dest


def bootstrap() -> None:
    purge_legacy_tts_models()
