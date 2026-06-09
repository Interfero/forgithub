"""
Локальное распознавание речи (STT) внутри Jarvis.

Основной движок: GigaAM-v3 (e2e_rnnt) — русская речь, в т.ч. невнятная.
Резерв: faster-whisper (JARVIS_STT_ENGINE=whisper).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from modules.app_paths import models_dir, user_data_dir

STT_DIR = user_data_dir() / "stt"
STT_BIN_DIR = STT_DIR / "bin"
MAX_AUDIO_BYTES = 12 * 1024 * 1024
_ffmpeg_prepared = False
_ffmpeg_prepare_lock = threading.Lock()

_gigaam_model = None
_whisper_model = None
_model_lock = threading.Lock()
_model_loading = False
_model_error: str | None = None
_active_engine = "gigaam"

WAKE_RE = re.compile(
    r"(?:^|[\s,.!?])(?:"
    r"дж(?:а(?:[\s,.!?]|$)|(?:арвис|рвис|рви|рв|р))|"
    r"jarvis|жарвис|дарвис|ярвис|джавис|джаврис|"
    r"джарвиз|джарвес|jarwiz|charvis|джервис"
    r")(?:[\s,.!?]|$)?",
    re.I,
)

STOP_RE = re.compile(
    r"(?:^|[\s,.!?])(?:джарвис|jarvis|жарвис|джавис)\s*[,]?\s*стоп|"
    r"стоп\s*[,]?\s*(?:джарвис|jarvis)(?:[\s,.!?]|$)",
    re.I,
)

WAKE_STRIP_RE = [
    re.compile(r"джарвис[,:]?\s*", re.I),
    re.compile(r"jarvis[,:]?\s*", re.I),
    re.compile(r"жарвис[,:]?\s*", re.I),
    re.compile(r"дарвис[,:]?\s*", re.I),
    re.compile(r"ярвис[,:]?\s*", re.I),
    re.compile(r"джавис[,:]?\s*", re.I),
    re.compile(r"джаврис[,:]?\s*", re.I),
    re.compile(r"джарви[,:]?\s*", re.I),
    re.compile(r"jarvi[s]?[,:]?\s*", re.I),
    re.compile(r"джа[,:]?\s*", re.I),
]

_WAKE_PREFIX_RE = re.compile(
    r"^(?:"
    r"джарвис|jarvis|жарвис|дарвис|ярвис|джавис|джаврис|"
    r"джар\s*vis|джар\s*вис|jar\s*vis|"
    r"джарви|джарв|джар|джа|"
    r"jarvi?s|джарвиз|джарвес|jarwiz|charvis|джервис"
    r")[,.!\s]*",
    re.I,
)

_WAKE_ONLY_RE = re.compile(
    r"^(?:"
    r"дж(?:а(?:р(?:в(?:ис?)?)?)?)?|"
    r"jarvi?s|жарвис|джавис|джаврис|"
    r"джарвиз|джарвес|jarwiz|charvis|джервис"
    r")$",
    re.I,
)


def _stt_engine() -> str:
    return (os.getenv("JARVIS_STT_ENGINE") or "gigaam").strip().lower() or "gigaam"


def _gigaam_model_name() -> str:
    return (os.getenv("JARVIS_GIGAAM_MODEL") or "e2e_rnnt").strip() or "e2e_rnnt"


def _whisper_model_name() -> str:
    return (os.getenv("JARVIS_WHISPER_MODEL") or "base").strip() or "base"


def _gigaam_cache_dir() -> Path:
    p = models_dir() / "gigaam"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _norm_wake(text: str) -> str:
    return (text or "").lower().replace("ё", "е").strip()


def _collapse_wake_spaces(text: str) -> str:
    return re.sub(r"(?<=[а-яa-z])\s+(?=[а-яa-z])", "", _norm_wake(text), flags=re.I)


def detect_wake(text: str) -> bool:
    norm = _norm_wake(text)
    if not norm:
        return False
    if WAKE_RE.search(norm):
        return True
    collapsed = _collapse_wake_spaces(norm)
    if collapsed != norm and WAKE_RE.search(collapsed):
        return True
    for token in re.findall(r"[\wа-яё]+", norm, flags=re.I):
        t = token.lower().replace("ё", "е")
        if t in (
            "дж",
            "джа",
            "джар",
            "джарв",
            "джарви",
            "джарвис",
            "jarvis",
            "jarvi",
            "jarviz",
            "жарвис",
            "джавис",
        ):
            return True
        if t.startswith("дж") and len(t) <= 10 and "р" in t[2:]:
            return True
        if t.startswith("jar") and len(t) <= 8:
            return True
    return False


def is_wake_only(text: str) -> bool:
    norm = _collapse_wake_spaces(text)
    return bool(_WAKE_ONLY_RE.match(norm))


def _ffmpeg_path() -> str | None:
    candidates: list[str] = []
    shim = STT_BIN_DIR / "ffmpeg.exe"
    if shim.is_file():
        candidates.append(str(shim.resolve()))
    try:
        import imageio_ffmpeg

        candidates.append(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        pass
    w = shutil.which("ffmpeg")
    if w:
        candidates.append(w)
    for raw in candidates:
        if not raw:
            continue
        p = Path(raw)
        if p.is_file():
            return str(p.resolve())
    return None


def _ensure_ffmpeg_shim() -> str | None:
    """
    GigaAM внутри вызывает subprocess ['ffmpeg', ...] — нужен ffmpeg.exe в PATH.
    Копируем bundled imageio-ffmpeg в data/stt/bin/ffmpeg.exe.
    """
    global _ffmpeg_prepared
    with _ffmpeg_prepare_lock:
        if _ffmpeg_prepared:
            return _ffmpeg_path()
        STT_BIN_DIR.mkdir(parents=True, exist_ok=True)
        dest = STT_BIN_DIR / "ffmpeg.exe"
        source = None
        try:
            import imageio_ffmpeg

            source = Path(imageio_ffmpeg.get_ffmpeg_exe())
        except Exception:
            source = None
        if source and source.is_file():
            try:
                if not dest.is_file() or dest.stat().st_size != source.stat().st_size:
                    shutil.copy2(source, dest)
            except Exception:
                pass
        ff = _ffmpeg_path()
        if ff:
            ff_dir = str(Path(ff).parent)
            path_env = os.environ.get("PATH", "")
            if ff_dir.lower() not in path_env.lower():
                os.environ["PATH"] = ff_dir + os.pathsep + path_env
        _ffmpeg_prepared = True
        return ff


def _wav_is_16k_mono(path: Path) -> bool:
    try:
        import wave

        with wave.open(str(path), "rb") as wf:
            return (
                wf.getnchannels() == 1
                and wf.getsampwidth() == 2
                and wf.getframerate() == 16000
            )
    except Exception:
        return False


def _to_wav_16k_mono(src: Path, dst: Path) -> None:
    _ensure_ffmpeg_shim()
    if src.suffix.lower() == ".wav" and _wav_is_16k_mono(src):
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dst.resolve():
            dst.write_bytes(src.read_bytes())
        return

    ff = _ffmpeg_path()
    if not ff:
        raise RuntimeError(
            "Нужен ffmpeg для декодирования аудио. "
            "Запустите install-chat-voice.bat (imageio-ffmpeg)."
        )
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = dst if src.resolve() != dst.resolve() else dst.with_name("decoded.wav")
    try:
        proc = subprocess.run(
            [
                ff,
                "-y",
                "-i",
                str(src.resolve()),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(out.resolve()),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            f"ffmpeg не найден ({ff}). Запустите install-chat-voice.bat."
        ) from e
    if proc.returncode != 0 or not out.is_file():
        err = (proc.stderr or proc.stdout or "ffmpeg error")[-500:]
        raise RuntimeError(f"Не удалось декодировать аудио: {err}")
    if out != dst:
        dst.write_bytes(out.read_bytes())


def _load_gigaam():
    global _gigaam_model, _model_loading, _model_error, _active_engine
    _ensure_ffmpeg_shim()
    if not _ffmpeg_path():
        raise RuntimeError(
            "ffmpeg не найден. Запустите install-chat-voice.bat (imageio-ffmpeg)."
        )
    with _model_lock:
        if _gigaam_model is not None:
            return _gigaam_model
        if _model_error and _stt_engine() == "gigaam":
            raise RuntimeError(_model_error)
        _model_loading = True
    try:
        import gigaam

        m = gigaam.load_model(
            _gigaam_model_name(),
            device="cpu",
            fp16_encoder=False,
            download_root=str(_gigaam_cache_dir()),
        )
        with _model_lock:
            _gigaam_model = m
            _active_engine = "gigaam"
            _model_loading = False
            _model_error = None
        return m
    except Exception as e:
        with _model_lock:
            _model_error = str(e)
            _model_loading = False
        raise


def _load_whisper():
    global _whisper_model, _model_loading, _model_error, _active_engine
    with _model_lock:
        if _whisper_model is not None:
            return _whisper_model
        _model_loading = True
    try:
        from faster_whisper import WhisperModel

        cache = models_dir() / "whisper"
        cache.mkdir(parents=True, exist_ok=True)
        m = WhisperModel(
            _whisper_model_name(),
            device="cpu",
            compute_type="int8",
            download_root=str(cache),
        )
        with _model_lock:
            _whisper_model = m
            _active_engine = "whisper"
            _model_loading = False
            _model_error = None
        return m
    except Exception as e:
        with _model_lock:
            _model_error = str(e)
            _model_loading = False
        raise


def _gigaam_extract_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("text", "transcription", "result"):
            val = result.get(key)
            if val:
                return str(val).strip()
    if hasattr(result, "text"):
        return str(result.text or "").strip()
    return str(result).strip()


def _transcribe_with_gigaam(wav: Path) -> tuple[str, float]:
    model = _load_gigaam()
    result = model.transcribe(str(wav))
    text = _gigaam_extract_text(result)
    try:
        import wave

        with wave.open(str(wav), "rb") as wf:
            duration = wf.getnframes() / float(wf.getframerate() or 16000)
    except Exception:
        duration = 0.0
    return text, duration


def _transcribe_with_whisper(wav: Path) -> tuple[str, float]:
    model = _load_whisper()
    segments, info = model.transcribe(
        str(wav),
        language="ru",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
        initial_prompt="Джарвис, привет, вопрос, слушай",
    )
    parts = [seg.text.strip() for seg in segments if seg.text.strip()]
    text = " ".join(parts).strip()
    duration = float(getattr(info, "duration", 0) or 0)
    return text, duration


def _allow_whisper_fallback() -> bool:
    return (os.getenv("JARVIS_STT_ALLOW_WHISPER_FALLBACK") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _run_transcription(wav: Path) -> tuple[str, float, str]:
    engine = _stt_engine()
    if engine == "whisper":
        text, dur = _transcribe_with_whisper(wav)
        return text, dur, "whisper"

    try:
        text, dur = _transcribe_with_gigaam(wav)
        if text:
            return text, dur, "gigaam_v3"
    except Exception as giga_err:
        if _allow_whisper_fallback():
            try:
                text, dur = _transcribe_with_whisper(wav)
                if text:
                    return text, dur, f"whisper_fallback({giga_err})"
            except Exception:
                pass
        raise giga_err

    if _allow_whisper_fallback():
        text, dur = _transcribe_with_whisper(wav)
        return text, dur, "whisper_fallback"

    return "", 0.0, "gigaam_v3_empty"


def warmup_stt_model() -> None:
    """Фоновая загрузка GigaAM при старте сервера (не блокирует HTTP)."""
    if _stt_engine() == "whisper":
        return

    def _run() -> None:
        try:
            _ensure_ffmpeg_shim()
            _load_gigaam()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True, name="jarvis-stt-warmup").start()


def get_stt_status() -> dict[str, Any]:
    global _active_engine
    _ensure_ffmpeg_shim()
    ready = _gigaam_model is not None or _whisper_model is not None
    err = _model_error
    ff = _ffmpeg_path()
    ff_shim = (STT_BIN_DIR / "ffmpeg.exe").is_file()
    giga_pkg = False
    whisper_pkg = False
    try:
        import gigaam  # noqa: F401

        giga_pkg = True
    except ImportError:
        pass
    try:
        import faster_whisper  # noqa: F401

        whisper_pkg = True
    except ImportError:
        pass

    engine = _stt_engine()
    model_label = (
        f"GigaAM-v3 ({_gigaam_model_name()})"
        if engine != "whisper"
        else f"Whisper ({_whisper_model_name()})"
    )
    if _gigaam_model is not None:
        model_label = f"GigaAM-v3 ({_gigaam_model_name()})"
    elif _whisper_model is not None:
        model_label = f"Whisper ({_whisper_model_name()})"

    gigaam_active = _gigaam_model is not None and _active_engine == "gigaam"
    return {
        "ready": ready,
        "loading": _model_loading,
        "package_installed": giga_pkg or whisper_pkg,
        "gigaam_installed": giga_pkg,
        "gigaam_active": gigaam_active,
        "gigaam_v3": engine != "whisper" and giga_pkg,
        "whisper_installed": whisper_pkg,
        "ffmpeg": bool(ff),
        "ffmpeg_shim": ff_shim,
        "ffmpeg_path": str(ff) if ff else None,
        "engine": _active_engine if ready else engine,
        "model": model_label,
        "error": err,
        "message": (
            f"STT готов ({model_label})"
            if ready
            else (
                "Установите: install-chat-voice.bat (GigaAM-v3 + ffmpeg)"
                if not (giga_pkg or whisper_pkg)
                else "Модель загрузится при первом распознавании (~430 МБ GigaAM-v3)"
            )
        ),
    }


def extract_command_after_wake(text: str) -> tuple[str | None, bool]:
    raw = (text or "").strip()
    if not raw:
        return None, False
    if not detect_wake(raw):
        return raw if len(raw) >= 2 else None, False

    idx = -1
    for pat in WAKE_STRIP_RE:
        for m in pat.finditer(raw):
            end = m.end()
            if end > idx:
                idx = end
    fallback = raw[idx:].strip().lstrip(",.!? ") if idx >= 0 else ""

    prefix_match = _WAKE_PREFIX_RE.match(raw.strip())
    command = raw[prefix_match.end() :].strip().lstrip(",.!? ") if prefix_match else ""
    if not command:
        command = fallback

    if not command and is_wake_only(raw):
        return "слушаю", True
    return (command if len(command) >= 2 else None), True


def transcribe_audio(data: bytes, *, filename: str = "speech.webm") -> dict[str, Any]:
    if not data:
        raise ValueError("Пустой аудиофайл")
    if len(data) > MAX_AUDIO_BYTES:
        raise ValueError(f"Лимит аудио: {MAX_AUDIO_BYTES // (1024 * 1024)} МБ")

    _ensure_ffmpeg_shim()
    if not _ffmpeg_path():
        raise RuntimeError(
            "ffmpeg не найден для GigaAM. Запустите install-chat-voice.bat."
        )

    STT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower() or ".webm"
    with tempfile.TemporaryDirectory(dir=STT_DIR) as tmp:
        src = Path(tmp) / f"input{suffix}"
        wav = Path(tmp) / "input.wav"
        src.write_bytes(data)
        _to_wav_16k_mono(src, wav)

        text, duration_sec, engine_used = _run_transcription(wav)

    norm = text.lower().replace("ё", "е")
    stop_command = bool(STOP_RE.search(norm))
    wake_found = detect_wake(text)
    command, _ = extract_command_after_wake(text)

    if not command and len(text.strip()) >= 2:
        command = text.strip()

    return {
        "text": text,
        "command": command or text,
        "wake_found": wake_found,
        "stop_command": stop_command,
        "language": "ru",
        "duration_sec": round(duration_sec, 2),
        "engine": engine_used,
    }


try:
    _ensure_ffmpeg_shim()
except Exception:
    pass
