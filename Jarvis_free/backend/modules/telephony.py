"""
Входящие звонки через API облачной АТС (Mango Office, Zadarma, generic webhook).
Озвучка приветствия и ответов — edge-tts (голос Jarvis), при наличии XTTS — расширяется позже.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("jarvis.telephony")

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
TEL_DIR = DATA_DIR / "telephony"
CONFIG_FILE = TEL_DIR / "config.json"
CACHE_DIR = TEL_DIR / "cache"
CALLS_FILE = TEL_DIR / "active_calls.json"

MANGO_API = "https://app.mango-office.ru/vpbx"


class TelProvider(str, Enum):
    GENERIC = "generic"
    MANGO = "mango"
    ZADARMA = "zadarma"


@dataclass
class TelephonyState:
    enabled: bool = False
    status: str = "off"
    status_label: str = "Выключено"
    last_event: str = ""
    error: str | None = None
    last_call_id: str | None = None
    last_caller: str | None = None
    greeting_ready: bool = False


_state = TelephonyState()
_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}


def _default_config() -> dict:
    return {
        "enabled": False,
        "provider": TelProvider.GENERIC.value,
        "public_base_url": "",
        "webhook_secret": "",
        "greeting_text": (
            "Здравствуйте. Вас приветствует Джарвис. "
            "Я ваш голосовой ассистент. Чем могу помочь?"
        ),
        "mango_api_key": "",
        "mango_api_salt": "",
        "mango_line_number": "",
        "mango_extension": "",
        "zadarma_api_key": "",
        "zadarma_api_secret": "",
        "zadarma_ivr_file_id": "",
        "use_llm_on_call": True,
    }


def _load_config() -> dict:
    TEL_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_default_config(), **raw}
        except Exception:
            pass
    return _default_config()


def _save_config(data: dict) -> None:
    merged = {**_default_config(), **data}
    CONFIG_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _mask_secret(value: str) -> str:
    v = (value or "").strip()
    if len(v) < 8:
        return ""
    return v[:4] + "••••••••"


def get_config() -> dict:
    cfg = _load_config()
    base = (cfg.get("public_base_url") or "").strip().rstrip("/")
    return {
        "enabled": bool(cfg.get("enabled")),
        "provider": cfg.get("provider") or TelProvider.GENERIC.value,
        "public_base_url": base,
        "webhook_secret": _mask_secret(cfg.get("webhook_secret", "")),
        "webhook_secret_configured": bool((cfg.get("webhook_secret") or "").strip()),
        "greeting_text": cfg.get("greeting_text") or _default_config()["greeting_text"],
        "mango_api_key": _mask_secret(cfg.get("mango_api_key", "")),
        "mango_api_key_configured": bool((cfg.get("mango_api_key") or "").strip()),
        "mango_api_salt": _mask_secret(cfg.get("mango_api_salt", "")),
        "mango_api_salt_configured": bool((cfg.get("mango_api_salt") or "").strip()),
        "mango_line_number": cfg.get("mango_line_number") or "",
        "mango_extension": cfg.get("mango_extension") or "",
        "zadarma_api_key": _mask_secret(cfg.get("zadarma_api_key", "")),
        "zadarma_api_key_configured": bool((cfg.get("zadarma_api_key") or "").strip()),
        "zadarma_api_secret": _mask_secret(cfg.get("zadarma_api_secret", "")),
        "zadarma_api_secret_configured": bool(
            (cfg.get("zadarma_api_secret") or "").strip()
        ),
        "zadarma_ivr_file_id": cfg.get("zadarma_ivr_file_id") or "",
        "use_llm_on_call": bool(cfg.get("use_llm_on_call", True)),
        "webhook_url": f"{base or 'http://127.0.0.1:8000'}/api/telephony/webhook",
        "scenario_url": f"{base or 'http://127.0.0.1:8000'}/api/telephony/scenario",
        "greeting_media_url": f"{base or 'http://127.0.0.1:8000'}/api/telephony/media/greeting.mp3",
    }


def _merge_secret(incoming: str, current: str) -> str:
    return current if "•" in (incoming or "") else (incoming or "").strip()


def save_config(body: dict) -> dict:
    cfg = _load_config()
    for key in (
        "enabled",
        "provider",
        "public_base_url",
        "webhook_secret",
        "greeting_text",
        "mango_line_number",
        "mango_extension",
        "zadarma_ivr_file_id",
        "use_llm_on_call",
    ):
        if key in body and body[key] is not None:
            cfg[key] = body[key]
    for key in ("mango_api_key", "mango_api_salt", "zadarma_api_key", "zadarma_api_secret"):
        if key in body and body[key] is not None:
            cfg[key] = _merge_secret(str(body[key]), cfg.get(key, ""))

    _save_config(cfg)
    with _lock:
        _state.enabled = bool(cfg.get("enabled"))
        if _state.enabled:
            _state.status = "ready"
            _state.status_label = "Готов принимать звонки"
        else:
            _state.status = "off"
            _state.status_label = "Выключено"
    if cfg.get("enabled"):
        threading.Thread(target=_warm_greeting, daemon=True).start()
    out = get_config()
    out["save_ok"] = True
    return out


def to_dict() -> dict:
    cfg = get_config()
    with _lock:
        return {
            "enabled": _state.enabled and cfg["enabled"],
            "status": _state.status,
            "status_label": _state.status_label,
            "last_event": _state.last_event,
            "error": _state.error,
            "last_call_id": _state.last_call_id,
            "last_caller": _state.last_caller,
            "greeting_ready": _state.greeting_ready,
            **cfg,
        }


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _greeting_path(text: str) -> Path:
    return CACHE_DIR / f"greeting_{_text_hash(text)}.mp3"


async def _synthesize_mp3_async(text: str, dest: Path) -> None:
    import edge_tts

    voice = "ru-RU-DmitryNeural"
    communicate = edge_tts.Communicate(text.strip(), voice)
    await communicate.save(str(dest))


def synthesize_greeting(text: str | None = None) -> Path:
    cfg = _load_config()
    phrase = (text or cfg.get("greeting_text") or "").strip()
    if not phrase:
        raise ValueError("Пустой текст приветствия")
    dest = _greeting_path(phrase)
    if dest.is_file() and dest.stat().st_size > 500:
        with _lock:
            _state.greeting_ready = True
        return dest
    asyncio.run(_synthesize_mp3_async(phrase, dest))
    link = CACHE_DIR / "greeting.mp3"
    try:
        import shutil

        shutil.copy2(dest, link)
    except Exception:
        pass
    with _lock:
        _state.greeting_ready = True
        _state.last_event = "Приветствие синтезировано"
    return dest


def _warm_greeting() -> None:
    try:
        synthesize_greeting()
    except Exception as e:
        with _lock:
            _state.error = str(e)
            _state.greeting_ready = False


def get_greeting_media_path() -> Path | None:
    link = CACHE_DIR / "greeting.mp3"
    if link.is_file():
        return link
    cfg = _load_config()
    path = _greeting_path(cfg.get("greeting_text", ""))
    return path if path.is_file() else None


def _public_url(path: str) -> str:
    cfg = _load_config()
    base = (cfg.get("public_base_url") or "").strip().rstrip("/")
    if not base:
        base = "http://127.0.0.1:8000"
    return f"{base}{path}"


def _verify_webhook_secret(headers: dict[str, str], body_secret: str = "") -> bool:
    cfg = _load_config()
    secret = (cfg.get("webhook_secret") or "").strip()
    if not secret:
        return True
    if body_secret and hmac.compare_digest(body_secret, secret):
        return True
    hdr = headers.get("x-jarvis-secret") or headers.get("X-Jarvis-Secret") or ""
    return hmac.compare_digest(hdr, secret) if hdr else False


def _mango_sign(api_key: str, payload: str, salt: str) -> str:
    raw = f"{api_key}{payload}{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _verify_mango_form(form: dict[str, str]) -> bool:
    cfg = _load_config()
    key = (cfg.get("mango_api_key") or "").strip()
    salt = (cfg.get("mango_api_salt") or "").strip()
    if not key or not salt:
        return True
    sign = form.get("sign", "")
    payload = form.get("json", "")
    if not sign:
        return False
    return hmac.compare_digest(sign, _mango_sign(key, payload, salt))


def _verify_zadarma_form(form: dict[str, str]) -> bool:
    cfg = _load_config()
    secret = (cfg.get("zadarma_api_secret") or "").strip()
    if not secret:
        return True
    expected = form.get("zd_echo")
    if expected:
        return True
    caller = form.get("caller_id", "")
    called = form.get("called_did", "")
    start = form.get("call_start", "")
    sig = base64_hmac = __import__("base64").b64encode(
        hmac.new(
            secret.encode("utf-8"),
            f"{caller}{called}{start}".encode("utf-8"),
            hashlib.sha1,
        ).digest()
    ).decode()
    return hmac.compare_digest(form.get("signature", ""), sig) if form.get("signature") else True


def _llm_reply(user_text: str, call_id: str) -> str:
    try:
        import store
        from modules.agent import generate_reply

        s = store.load_settings()
        key = (s.get("deepseek_key") or "").strip()
        model = s.get("default_model") or "deepseek-chat"
        sess = _session_get(call_id)
        history = list(sess.get("history", []))
        text, _ = generate_reply(user_text, history, deepseek_key=key, model=model)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": text})
        sess["history"] = history[-8:]
        clean = re.sub(r"\*+|`+|#+", "", text)
        return clean[:400] if len(clean) > 400 else clean
    except Exception as e:
        logger.warning("LLM on call failed: %s", e)
        return "Я вас слушаю. Повторите вопрос, пожалуйста."


def _session_get(call_id: str) -> dict[str, Any]:
    if call_id not in _sessions:
        _sessions[call_id] = {"turn": 0, "history": []}
    return _sessions[call_id]


def _handle_incoming_call(
    call_id: str,
    caller: str,
    called: str,
    provider: str,
) -> dict[str, Any]:
    cfg = _load_config()
    if not cfg.get("enabled"):
        return {"ok": False, "error": "Телефония выключена в настройках"}

    threading.Thread(target=_warm_greeting, daemon=True).start()
    audio_url = _public_url("/api/telephony/media/greeting.mp3")

    with _lock:
        _state.last_call_id = call_id
        _state.last_caller = caller
        _state.last_event = f"Входящий звонок {caller} → {called}"
        _state.status = "active"
        _state.status_label = "На линии"
        _state.error = None

    _session_get(call_id)["turn"] = 1

    return {
        "ok": True,
        "call_id": call_id,
        "action": "play",
        "audio_url": audio_url,
        "greeting_text": cfg.get("greeting_text"),
        "provider": provider,
        "mango_scenario": {
            "message": "OK",
            "result": [
                {"type": "playback", "params": {"file": audio_url}},
            ],
        },
        "zadarma": _zadarma_play_response(cfg, audio_url),
    }


def _zadarma_play_response(cfg: dict, audio_url: str) -> dict[str, Any]:
    file_id = (cfg.get("zadarma_ivr_file_id") or "").strip()
    if file_id:
        return {"ivr_play": file_id}
    return {
        "ivr_saypopular": 1,
        "language": "ru",
        "note": "Загрузите mp3 в кабинет Zadarma и укажите ivr file id, "
        "либо используйте public URL в сценарии: " + audio_url,
    }


def handle_webhook(
    *,
    headers: dict[str, str],
    form: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    raw_body: bytes = b"",
) -> tuple[int, dict[str, Any] | str]:
    cfg = _load_config()
    form = form or {}

    if not _verify_webhook_secret(headers, form.get("secret", "")):
        return 403, {"error": "invalid webhook secret"}

    provider = (cfg.get("provider") or TelProvider.GENERIC.value).lower()

    if form.get("json") and (form.get("sign") or provider == TelProvider.MANGO.value):
        if not _verify_mango_form(form):
            return 403, {"error": "invalid mango sign"}
        try:
            payload = json.loads(form["json"])
        except json.JSONDecodeError:
            return 400, {"error": "invalid mango json"}
        return _handle_mango_event(payload)

    if form.get("event", "").startswith("NOTIFY_") or provider == TelProvider.ZADARMA.value:
        if not _verify_zadarma_form(form):
            return 403, {"error": "invalid zadarma sign"}
        return _handle_zadarma_event(form)

    body = json_body or {}
    if raw_body and not body:
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except Exception:
            body = {}

    event = str(body.get("event", "incoming")).lower()
    call_id = str(body.get("call_id") or body.get("pbx_call_id") or uuid.uuid4())
    caller = str(body.get("from") or body.get("caller") or body.get("caller_id") or "?")
    called = str(body.get("to") or body.get("called") or body.get("called_did") or "?")

    if event in ("incoming", "call_start", "notify_start"):
        result = _handle_incoming_call(call_id, caller, called, TelProvider.GENERIC.value)
        return 200, result

    if event in ("dtmf", "speech", "input"):
        digits = str(body.get("digits") or body.get("dtmf") or "")
        text = str(body.get("text") or body.get("speech") or "")
        user_msg = text or f"Нажата клавиша {digits}" if digits else "Продолжаем разговор"
        reply = (
            _llm_reply(user_msg, call_id)
            if cfg.get("use_llm_on_call")
            else "Спасибо за звонок."
        )
        reply_path = CACHE_DIR / f"reply_{_text_hash(reply)}.mp3"
        if not reply_path.is_file():
            asyncio.run(_synthesize_mp3_async(reply, reply_path))
        return 200, {
            "ok": True,
            "action": "play",
            "audio_url": _public_url(f"/api/telephony/media/{reply_path.name}"),
            "text": reply,
        }

    return 200, {"ok": True, "ignored": True, "event": event}


def _handle_mango_event(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    call_id = str(payload.get("call_id") or payload.get("entry_id") or uuid.uuid4())
    state = str(payload.get("call_state") or "").lower()
    from_info = payload.get("from") or {}
    to_info = payload.get("to") or {}
    caller = str(from_info.get("number") if isinstance(from_info, dict) else from_info or "?")
    called = str(to_info.get("number") if isinstance(to_info, dict) else to_info or "?")

    with _lock:
        _state.last_event = f"Mango: {state} {caller}"

    if state in ("appeared", "connected", "oncall"):
        result = _handle_incoming_call(call_id, caller, called, TelProvider.MANGO.value)
        return 200, result

    if state in ("disconnected", "ended"):
        with _lock:
            _state.status = "ready"
            _state.status_label = "Готов принимать звонки"
        return 200, {"ok": True, "ended": True}

    return 200, {"ok": True, "state": state}


def _handle_zadarma_event(form: dict[str, str]) -> tuple[int, dict[str, Any]]:
    event = form.get("event", "")
    call_id = form.get("pbx_call_id") or form.get("call_id") or str(uuid.uuid4())
    caller = form.get("caller_id", "?")
    called = form.get("called_did", "?")

    if event == "NOTIFY_START":
        result = _handle_incoming_call(call_id, caller, called, TelProvider.ZADARMA.value)
        zresp = result.get("zadarma") or {}
        if isinstance(zresp, dict):
            return 200, zresp
        return 200, result

    if event == "NOTIFY_IVR":
        digits = form.get("digits", "")
        if digits and _load_config().get("use_llm_on_call"):
            reply = _llm_reply(f"Клиент нажал {digits}. Ответьте кратко.", call_id)
        else:
            reply = "Спасибо. До свидания."
        reply_path = CACHE_DIR / f"reply_{_text_hash(reply)}.mp3"
        if not reply_path.is_file():
            asyncio.run(_synthesize_mp3_async(reply, reply_path))
        cfg = _load_config()
        file_id = (cfg.get("zadarma_ivr_file_id") or "").strip()
        if file_id:
            return 200, {"ivr_play": file_id}
        return 200, {"ivr_saypopular": 17, "language": "ru"}

    return 200, {"ok": True, "event": event}


def handle_scenario_query(params: dict[str, str]) -> dict[str, Any]:
    """Mango «запрос к внешней системе» в схеме входящего звонка (GET/POST)."""
    call_id = params.get("call_id") or params.get("entry_id") or str(uuid.uuid4())
    caller = params.get("from") or params.get("caller_id") or "?"
    called = params.get("to") or params.get("called_did") or params.get("line_number") or "?"
    result = _handle_incoming_call(call_id, caller, called, "scenario")
    return result.get("mango_scenario") or {
        "message": "OK",
        "result": [{"type": "playback", "params": {"file": result.get("audio_url")}}],
    }


def mango_outbound_call(to_number: str) -> dict[str, Any]:
    """Исходящий звонок через Mango (проверка API-ключей)."""
    cfg = _load_config()
    key = (cfg.get("mango_api_key") or "").strip()
    salt = (cfg.get("mango_api_salt") or "").strip()
    ext = (cfg.get("mango_extension") or "").strip()
    line = (cfg.get("mango_line_number") or "").strip()
    if not key or not salt or not ext:
        return {"ok": False, "error": "Заполните Mango API key, salt и extension"}

    command = {
        "command_id": f"jarvis-{int(time.time())}",
        "from": {"extension": ext},
        "to_number": re.sub(r"\D", "", to_number),
    }
    if line:
        command["line_number"] = line
    payload = json.dumps(command, ensure_ascii=False)
    sign = _mango_sign(key, payload, salt)
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                f"{MANGO_API}/commands/callback",
                data={"vpbx_api_key": key, "sign": sign, "json": payload},
            )
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200 and (data.get("result") in (1000, "1000", None) or data.get("ok")):
            with _lock:
                _state.last_event = f"Исходящий на {to_number}"
            return {"ok": True, "message": "Звонок инициирован", "mango": data}
        return {"ok": False, "error": str(data or r.text), "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def test_webhook_local() -> dict[str, Any]:
    code, body = handle_webhook(
        headers={"Content-Type": "application/json"},
        json_body={
            "event": "incoming",
            "call_id": "test-local",
            "from": "+79001234567",
            "to": "+74950000000",
        },
    )
    return {"http_status": code, **(body if isinstance(body, dict) else {"raw": body})}
