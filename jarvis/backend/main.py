"""
Jarvis — FastAPI. Чат через DeepSeek при наличии ключа, иначе мок.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from modules.agent import (
    AgentMode,
    MODE_LABELS,
    generate_reply,
    get_mode,
    get_runtime,
    is_voice_interaction_mode,
    set_mode,
    set_chat_speech,
    set_voice,
)
from modules import documents
from modules import jarvis_db
from modules import menu_search
from modules import mail_client
from modules import memory_store
from modules import telephony as telephony_module
from modules import tg_bot_logic
from modules import tg_twin
from modules import avito as avito_module
from modules import openconnect_vpn as vpn_module
from modules import pc_shell as pc_shell_module
from modules import local_qwen as local_qwen_module
from modules import voice as voice_module
from modules import nano_banana as nano_banana_module
from modules import chat_assistant as chat_assistant_module
import store

FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:4173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

from modules.app_paths import frontend_dist_dir

FRONTEND_DIST = frontend_dist_dir()
JARVIS_HOST = os.getenv("JARVIS_HOST", "127.0.0.1")
JARVIS_PORT = int(os.getenv("JARVIS_PORT", "8000"))


def _cors_origins() -> list[str]:
    origins = list(FRONTEND_ORIGINS)
    extra = os.getenv("JARVIS_CORS_ORIGINS", "").strip()
    for item in extra.split(","):
        item = item.strip()
        if item and item not in origins:
            origins.append(item)
    return origins


class ModeIn(BaseModel):
    mode: str


class VoiceToggleIn(BaseModel):
    enabled: bool


class TgToggleIn(BaseModel):
    enabled: bool


class TgConfigIn(BaseModel):
    bot_token: str = ""
    blocklist_ids: list[str] = Field(default_factory=list)
    telegram_proxy: str = ""


class HfSearchIn(BaseModel):
    query: str = ""
    repo_type: str = "model"
    limit: int = 12


class HfDownloadIn(BaseModel):
    repo_id: str
    repo_type: str = "model"
    revision: str = "main"
    filenames: list[str] = Field(default_factory=list)
    allow_patterns: list[str] = Field(default_factory=list)
    label: str = ""


class HfEnableIn(BaseModel):
    skill_id: str
    enabled: bool = True


class AvitoConfigIn(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    user_id: str = ""


class AvitoToggleIn(BaseModel):
    enabled: bool = False


class TelephonyConfigIn(BaseModel):
    enabled: bool = False
    provider: str = "generic"
    public_base_url: str = ""
    webhook_secret: str = ""
    greeting_text: str = ""
    mango_api_key: str = ""
    mango_api_salt: str = ""
    mango_line_number: str = ""
    mango_extension: str = ""
    zadarma_api_key: str = ""
    zadarma_api_secret: str = ""
    zadarma_ivr_file_id: str = ""
    use_llm_on_call: bool = True


class TelephonyTestCallIn(BaseModel):
    to_number: str = ""


class ChatCreateIn(BaseModel):
    title: str = "Новый диалог"


class ChatUpdateIn(BaseModel):
    title: str


class MessageIn(BaseModel):
    content: str
    mode: str | None = None
    voice_enabled: bool | None = None
    chat_speech_enabled: bool | None = None
    insult_request_id: str | None = None
    chat_surface_mode: str | None = None


class InsultEvaluateIn(BaseModel):
    text: str
    request_id: str | None = None
    chat_id: str | None = None


class ChatSpeechIn(BaseModel):
    enabled: bool


class VoiceSpeakIn(BaseModel):
    text: str


class SystemLogIn(BaseModel):
    content: str
    importance: str = "important"  # important | routine


class GenerateDocIn(BaseModel):
    counterparty_id: int | None = None
    amount: float = 10000.0


class SettingsIn(BaseModel):
    provider: str = "deepseek"
    default_model: str = "deepseek-chat"
    openai_key: str = ""
    openai_model: str = "gpt-5.5-instant"
    anthropic_key: str = ""
    deepseek_key: str = ""
    perplexity_key: str = ""
    perplexity_model: str = "sonar"
    xai_key: str = ""
    xai_model: str = "grok-4.20"
    nanobanana_key: str = ""
    ideogram_key: str = ""


def _key_configured(key: str, prefix: str | tuple[str, ...], min_len: int = 16) -> bool:
    k = (key or "").strip()
    if not k or "•" in k or len(k) < min_len:
        return False
    if isinstance(prefix, str):
        return k.startswith(prefix)
    return any(k.startswith(p) for p in prefix)


def _merge_secret(incoming: str, current: str) -> str:
    """Пустое или маскированное поле не затирает уже сохранённый ключ."""
    inc = (incoming or "").strip()
    if not inc or _is_masked(inc):
        return current
    return inc


def _mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return key
    return key[:7] + "••••••••••••••••"


def _is_masked(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return True
    if "•" in v or "…" in v or "***" in v:
        return True
    # Маска с API: sk-04f7••••••••••••••••
    if v.startswith("sk-") and len(v) < 24 and any(c in v for c in "•*"):
        return True
    return False


def _load_settings_model() -> SettingsIn:
    from modules.free_edition import apply_free_settings

    raw = apply_free_settings(store.load_settings())
    return SettingsIn(**raw)


def _save_settings_model(body: SettingsIn) -> SettingsIn:
    from modules.free_edition import protect_free_settings_save

    current = _load_settings_model()
    body_dump = protect_free_settings_save(
        body.model_dump(),
        store.load_settings(),
    )
    merged = SettingsIn(
        provider=body_dump.get("provider", body.provider),
        default_model=body_dump.get("default_model", body.default_model),
        openai_key=_merge_secret(body.openai_key, current.openai_key),
        openai_model=body.openai_model,
        anthropic_key=_merge_secret(body.anthropic_key, current.anthropic_key),
        deepseek_key=_merge_secret(
            str(body_dump.get("deepseek_key", body.deepseek_key)),
            current.deepseek_key,
        ),
        perplexity_key=_merge_secret(body.perplexity_key, current.perplexity_key),
        perplexity_model=body.perplexity_model,
        xai_key=_merge_secret(body.xai_key, current.xai_key),
        xai_model=body.xai_model,
        nanobanana_key=_merge_secret(body.nanobanana_key, current.nanobanana_key),
        ideogram_key=_merge_secret(body.ideogram_key, current.ideogram_key),
    )
    from modules.service_flags import apply_active_flags_on_settings_save

    before = store.load_settings()
    patched = apply_active_flags_on_settings_save(before, merged.model_dump())
    store.save_settings(patched)
    return SettingsIn(**patched)


def _deepseek_configured() -> bool:
    from modules.service_flags import deepseek_usable

    return deepseek_usable(_load_settings_model().deepseek_key)


def _nanobanana_configured() -> bool:
    from modules.service_flags import nanobanana_usable

    return nanobanana_usable(_load_settings_model().nanobanana_key)


def _perplexity_configured() -> bool:
    from modules.service_flags import perplexity_usable

    return perplexity_usable(_load_settings_model().perplexity_key)


def _developer_mode_ready() -> bool:
    return _perplexity_configured()


def _settings_flags(s: SettingsIn) -> dict:
    from modules.service_flags import service_flags_payload

    return service_flags_payload(s.model_dump())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from modules.app_paths import bootstrap_user_data, ensure_user_data_dir

    ensure_user_data_dir()
    bootstrap_user_data()
    store.DATA_DIR.mkdir(parents=True, exist_ok=True)
    voice_module.ensure_default_base_voice()
    voice_module.get_slots()  # подхват слотов студии с диска
    from modules import silero_tts

    silero_tts.bootstrap()
    memory_store._ensure_dirs()
    jarvis_db.init_db()
    from modules.insult_lexicon import ensure_lexicon_ready

    ensure_lexicon_ready()
    try:
        from modules.web_stereotypes import ensure_default_stereotypes_file

        ensure_default_stereotypes_file()
    except Exception:
        pass
    from modules.moderation import warmup_moderation

    warmup_moderation()
    menu_search.sync_catalog()
    jarvis_db.sync_db_to_disk()
    jarvis_db.sync_all_from_disk()
    documents.init_db()
    from modules import jarvis_docs

    jarvis_docs.register_shutdown_hooks()
    _session_boot = jarvis_docs.on_app_startup()
    jarvis_docs.ensure_tech_documentation()
    jarvis_docs.start_doc_scheduler()
    try:
        from modules.maintenance_runner import start_maintenance_scheduler

        start_maintenance_scheduler()
    except Exception:
        pass
    tg_twin.bootstrap()
    avito_module.bootstrap()
    mail_client.bootstrap()
    local_qwen_module.warmup_qwen_async()
    try:
        from modules.voice_stt import warmup_stt_model, _ensure_ffmpeg_shim

        _ensure_ffmpeg_shim()
        warmup_stt_model()
    except Exception:
        pass
    try:
        from modules.voice import ensure_default_base_voice

        ensure_default_base_voice()
    except Exception:
        pass
    try:
        from modules.chromium_browser import warmup_chromium_dependencies_async

        warmup_chromium_dependencies_async()
    except Exception:
        pass
    try:
        from modules.jarvis_component_updates import maybe_run_components_update_async

        maybe_run_components_update_async(force=False)
    except Exception:
        pass
    yield
    jarvis_docs.on_app_shutdown()
    jarvis_docs.stop_doc_scheduler()
    try:
        from modules.maintenance_runner import stop_maintenance_scheduler

        stop_maintenance_scheduler()
    except Exception:
        pass
    try:
        from modules.chromium_browser import shutdown_chromium_browser

        shutdown_chromium_browser()
    except Exception:
        pass
    tg_twin.shutdown()
    avito_module.shutdown()


app = FastAPI(title="Jarvis API", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Мгновенный ping — без сети/Qwen/XTTS (их опрос — /api/network и /api/status)."""
    return {"ok": True, "version": "0.5.0"}


@app.post("/api/app/restart")
def api_app_restart():
    """Dev: restart.bat (сборка UI). Exe: повторный запуск Jarvis.exe."""
    if sys.platform != "win32":
        raise HTTPException(501, "Перезапуск из UI поддерживается только на Windows")
    try:
        from modules.app_restart import trigger_restart

        return trigger_restart()
    except FileNotFoundError as e:
        raise HTTPException(500, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/network")
def api_network():
    """Сеть и веб-поиск: те же соединения, что у Windows."""
    from modules.network_env import get_network_summary

    return get_network_summary()


@app.get("/api/status")
def status():
    rt = get_runtime()
    s = _load_settings_model()
    base = voice_module.get_base_voice_info()
    xtts = voice_module.get_xtts_status()
    silero = voice_module.get_silero_status()
    chat_voice = voice_module.get_chat_voice_readiness()
    qwen = local_qwen_module.get_qwen_status()
    qwen_ready = bool(qwen.get("ready") or qwen.get("ollama_model_loaded"))
    deepseek_ok = _deepseek_configured()
    chat_llm_ready = bool(qwen_ready or deepseek_ok)
    if chat_llm_ready:
        chat_mode_label = "Полный чат (нейросеть)"
        chat_mode_detail = (
            "Ответы через Qwen и/или DeepSeek — см. «Последний ответ» после сообщения."
        )
    else:
        chat_mode_label = "Только справка"
        chat_mode_detail = (
            "Нет Qwen на диске/Ollama и нет ключа DeepSeek — в чате короткие шаблоны и правила, "
            "не полноценный ИИ. install-qwen.bat (~9 ГБ) или ключ sk-… в Настройках."
        )
    from modules.jarvis_memory import get_ram_snapshot

    ram_usage = get_ram_snapshot()
    from modules.chromium_browser import chromium_browser_status
    from modules.insult_handler import insult_status_payload
    from modules.network_env import internet_status_payload
    from modules.system_google_chrome import google_chrome_status

    chromium_browser = chromium_browser_status()
    google_chrome = google_chrome_status()
    from modules.voice_stt import get_stt_status

    stt = get_stt_status()
    from modules.free_edition import deepseek_bundled_for_client
    from modules.jarvis_edition import edition_label, is_free_edition

    return {
        "edition": "free" if is_free_edition() else "pro",
        "edition_label": edition_label(),
        "deepseek_bundled": deepseek_bundled_for_client(),
        "backend_status": "connected",
        "status": rt.status,
        "session_tokens": rt.session_tokens,
        "model": (
            local_qwen_module.active_model_display_name()
            if qwen_ready
            else (s.default_model if _deepseek_configured() else "заглушка")
        ),
        "neural_ready": chat_llm_ready,
        "qwen_ready": qwen_ready,
        "chat_llm_ready": chat_llm_ready,
        "chat_mode_label": chat_mode_label,
        "chat_mode_detail": chat_mode_detail,
        "qwen": qwen,
        "qwen_ram_enabled": bool(qwen.get("ram_enabled")),
        "router": {
            "last_intent": rt.last_router_intent or None,
            "last_engine": rt.last_router_engine or None,
        },
        "mode": rt.mode.value,
        "voice_enabled": rt.voice_enabled,
        "voice_listening": rt.voice_enabled,
        "chat_speech_enabled": rt.chat_speech_enabled,
        "icq_smileys_enabled": bool(store.load_settings().get("icq_smileys_enabled")),
        "nanobanana_configured": _nanobanana_configured(),
        **_settings_flags(s),
        "deepseek_configured": _deepseek_configured(),
        "deepseek_usable": _deepseek_configured(),
        "voice_base": base,
        "silero": silero,
        "xtts": silero,
        "chat_voice": chat_voice,
        "stt": stt,
        "tool_logs": [
            {"id": l.id, "timestamp": l.timestamp, "tool": l.tool, "message": l.message}
            for l in rt.tool_logs
        ],
        "telegram": tg_twin.to_dict(),
        "avito": avito_module.to_dict(),
        "mail": mail_client.to_dict(),
        "telephony": telephony_module.to_dict(),
        "memory": memory_store.get_stores_summary(for_chat_ui=True),
        "ram_usage": ram_usage,
        "chromium_browser": chromium_browser,
        "google_chrome": google_chrome,
        "net": internet_status_payload(),
        **insult_status_payload(rt),
        "mood": _mood_status(rt),
    }


def _mood_status(rt):
    from modules.jarvis_mood import mood_status_payload

    return mood_status_payload(rt)


@app.post("/api/insult/evaluate")
def api_insult_evaluate(body: InsultEvaluateIn):
    """Регистрация оскорбления (вызывается UI при отправке сообщения)."""
    from modules.agent import get_runtime
    from modules.insult_handler import process_user_message_insult
    from modules.moderation import moderate_message, moderation_log_to_runtime

    rt = get_runtime()
    session_key = (body.chat_id or body.request_id or "default").strip() or "default"
    mod_out = moderate_message(body.text.strip(), session_key, apply_context=False)
    moderation_log_to_runtime(rt, mod_out)
    result = process_user_message_insult(
        body.text.strip(),
        rt,
        request_id=body.request_id,
        session_id=session_key,
        moderation=mod_out,
    )
    result["moderation"] = {
        "action": mod_out.action,
        "triggered_by": mod_out.triggered_by,
        "jarvis_directed": mod_out.jarvis_directed,
        "response_time_ms": round(mod_out.response_time_ms, 2),
    }
    if mod_out.action in ("WARN", "BLOCK") and mod_out.response:
        result["moderation_response"] = mod_out.response
    if result.get("kind") != "at_jarvis" or not result.get("counted"):
        try:
            from modules.jarvis_mood import on_user_message

            on_user_message(rt, body.text.strip(), insult_counted=False)
        except Exception:
            pass
    result["mood"] = _mood_status(rt)
    return result


@app.post("/api/session/reset-insults")
def api_reset_insult_session():
    """Сброс счётчика оскорблений при старте backend (не даёт +30 к настроению)."""
    from modules.agent import get_runtime
    from modules.insult_handler import reset_insult_session, insult_status_payload

    rt = get_runtime()
    reset_insult_session(rt)
    return {**insult_status_payload(rt), "mood": _mood_status(rt)}


@app.post("/api/insult/restart")
def api_insult_restart():
    """RESTART: сброс счётчика оскорблений +30 к настроению (после порога)."""
    from modules.agent import get_runtime
    from modules.insult_handler import insult_status_payload
    from modules.jarvis_mood import can_restart_insults, on_insult_restart

    rt = get_runtime()
    if not can_restart_insults(rt):
        from modules.insult_handler import INSULT_THRESHOLD

        raise HTTPException(
            400,
            f"RESTART доступен после {INSULT_THRESHOLD} оскорблений в сессии.",
        )
    on_insult_restart(rt, clear_chat=True)
    import store

    chat = store.ensure_single_chat()
    return {
        **insult_status_payload(rt),
        "mood": _mood_status(rt),
        "chat_cleared": True,
        "message_count": len(chat.get("messages") or []),
    }


@app.put("/api/agent/mode")
def api_set_mode(body: ModeIn):
    try:
        mode = AgentMode(body.mode)
    except ValueError:
        raise HTTPException(400, "mode: standard | accountant | marketer | developer")
    if mode == AgentMode.MARKETER and not _nanobanana_configured():
        from modules.media_generation import has_media_provider

        if not has_media_provider("image") and not _deepseek_configured():
            raise HTTPException(
                400,
                "Режим «Маркетолог+Дизайнер» требует ключ для медиа (Nano Banana, OpenAI или xAI) или DeepSeek для текстов",
            )
    if mode == AgentMode.ACCOUNTANT and not _deepseek_configured():
        raise HTTPException(
            400,
            "Режим «Бухгалтер + Юрист» требует API-ключ DeepSeek (sk-…) в Настройках",
        )
    if mode == AgentMode.DEVELOPER and not _developer_mode_ready():
        raise HTTPException(
            400,
            "Режим «Разработчик» требует API-ключ Perplexity (pplx-…) в Настройках",
        )
    prev = get_mode()
    log_message = set_mode(mode, previous=prev)
    return {"mode": mode.value, "log_message": log_message}


@app.put("/api/agent/voice")
def api_set_voice(body: VoiceToggleIn):
    set_voice(body.enabled)
    rt = get_runtime()
    return {
        "voice_enabled": body.enabled,
        "chat_speech_enabled": rt.chat_speech_enabled,
    }


@app.put("/api/agent/chat-speech")
def api_set_chat_speech(body: ChatSpeechIn):
    set_chat_speech(body.enabled)
    return {"chat_speech_enabled": body.enabled}


class QwenRamIn(BaseModel):
    enabled: bool


class ServiceActiveIn(BaseModel):
    enabled: bool


@app.put("/api/agent/qwen-ram")
def api_set_qwen_ram(body: QwenRamIn):
    """Включить/выключить загрузку Qwen 2.5 14B в ОЗУ."""
    return local_qwen_module.set_qwen_ram_enabled(body.enabled)


@app.post("/api/agent/qwen-download")
def api_qwen_download(force: bool = Query(default=False)):
    """Скачать Qwen 2.5 14B (GGUF ~9 ГБ) в backend/data/models внутри Jarvis."""
    return local_qwen_module.start_qwen_download(force=bool(force))


@app.get("/api/agent/qwen-download/status")
def api_qwen_download_status():
    """Прогресс скачивания GGUF (для полосы в настройках)."""
    return local_qwen_module.get_qwen_download_progress()


@app.get("/api/system/jarvis-ram")
def api_jarvis_ram():
    """ОЗУ и процессы Jarvis (лёгкий опрос для полоски на экране аватара)."""
    from modules.jarvis_memory import get_ram_snapshot

    return get_ram_snapshot()


@app.get("/api/system/health-report")
def api_system_health_report():
    """HTML-отчёт «Проверка систем» для стартового экрана и смены режима."""
    from modules.system_health import build_system_health_report

    return {"content": build_system_health_report()}


@app.get("/api/system/chromium-browser")
def api_chromium_browser():
    """Статус встроенного headless Chromium (Playwright)."""
    from modules.chromium_browser import chromium_browser_status

    return chromium_browser_status()


@app.post("/api/system/chromium-browser/install")
def api_chromium_browser_install():
    """Повторный запуск автоустановки (как install-chromium.bat)."""
    from modules.chromium_browser import chromium_browser_status, start_auto_install_if_needed

    started = start_auto_install_if_needed(force=True)
    return {"started": started, **chromium_browser_status(force_refresh=True)}


@app.get("/api/system/google-chrome")
def api_google_chrome():
    """Google Chrome на Windows — оконный режим браузера Jarvis."""
    from modules.system_google_chrome import google_chrome_status

    return google_chrome_status()


@app.post("/api/system/google-chrome/install")
def api_google_chrome_install():
    """Переустановить оконный браузер в Jarvis/browsers (--force chromium)."""
    from modules.jarvis_browsers import (
        google_chrome_status,
        warmup_jarvis_browsers_repair_async,
    )

    warmup_jarvis_browsers_repair_async()
    return {"started": True, "repair": True, **google_chrome_status()}


@app.post("/api/system/free-updates/run")
def api_free_updates_run(force: bool = False):
    """Обновить бесплатные pip-пакеты и браузеры Jarvis."""
    from modules.jarvis_component_updates import run_components_update

    return run_components_update(force_browsers=force, force_pip=True)


@app.post("/api/system/open-ui")
def api_open_jarvis_ui():
    """Открыть http://127.0.0.1:8000/ во встроенном Chrome Jarvis."""
    from modules.jarvis_browsers import open_jarvis_ui_in_chrome

    ok, detail = open_jarvis_ui_in_chrome()
    if not ok:
        raise HTTPException(503, detail)
    return {"ok": True, "url": detail}


@app.post("/api/system/open-game")
def api_open_jarvis_game():
    """2D-игра Jarvis (/game) во встроенном Chrome, полный экран."""
    from modules.jarvis_browsers import open_jarvis_game_in_chrome

    ok, detail = open_jarvis_game_in_chrome()
    if not ok:
        raise HTTPException(503, detail)
    return {"ok": True, "url": detail}


@app.get("/api/settings")
def get_settings():
    s = _load_settings_model()
    flags = _settings_flags(s)
    return {
        "provider": s.provider,
        "default_model": s.default_model,
        "openai_key": _mask_key(s.openai_key) if s.openai_key else "",
        "openai_model": s.openai_model,
        "anthropic_key": _mask_key(s.anthropic_key) if s.anthropic_key else "",
        "deepseek_key": _mask_key(s.deepseek_key) if s.deepseek_key else "",
        "perplexity_key": _mask_key(s.perplexity_key) if s.perplexity_key else "",
        "perplexity_model": s.perplexity_model,
        "xai_key": _mask_key(s.xai_key) if s.xai_key else "",
        "xai_model": s.xai_model,
        "nanobanana_key": _mask_key(s.nanobanana_key) if s.nanobanana_key else "",
        "ideogram_key": _mask_key(s.ideogram_key) if s.ideogram_key else "",
        **flags,
    }


@app.put("/api/settings")
def put_settings(body: SettingsIn):
    merged = _save_settings_model(body)
    get_runtime().log("settings", "Настройки сохранены")
    return get_settings()


_SERVICE_ACTIVE_MAP = {
    "deepseek": "deepseek_active",
    "openai": "openai_active",
    "perplexity": "perplexity_active",
    "xai": "xai_active",
    "nanobanana": "nanobanana_active",
    "ideogram": "ideogram_active",
    "xtts": "xtts_active",
}


@app.put("/api/settings/service/{service_name}/active")
def api_set_service_active(service_name: str, body: ServiceActiveIn):
    flag = _SERVICE_ACTIVE_MAP.get(service_name.strip().lower())
    if not flag:
        raise HTTPException(400, "service: deepseek | openai | perplexity | xai | nanobanana | ideogram | xtts")
    from modules.service_flags import (
        service_flag_has_credentials,
        set_active,
    )

    if body.enabled and not service_flag_has_credentials(flag):
        raise HTTPException(400, "Сначала сохраните ключ API на сервере")
    set_active(flag, body.enabled)
    label = {
        "deepseek_active": "DeepSeek",
        "openai_active": "OpenAI",
        "perplexity_active": "Perplexity",
        "xai_active": "xAI",
        "nanobanana_active": "Nano Banana",
        "ideogram_active": "Ideogram",
        "xtts_active": "Silero TTS",
    }.get(flag, service_name)
    state = "включён" if body.enabled else "выключен"
    get_runtime().log("settings", f"{label} {state}")
    return get_settings()


@app.get("/api/session/startup")
def api_session_startup():
    """Состояние чата: история хранится в chats.json до полного закрытия Jarvis."""
    from modules import jarvis_docs

    info = jarvis_docs.get_startup_info()
    chat = store.ensure_single_chat()
    n = len(chat.get("messages") or [])
    info["message_count"] = n
    info["chat_empty"] = n == 0
    info["chat_persisted"] = n > 0
    return info


@app.get("/api/chats")
def api_list_chats():
    return store.list_chats()


@app.post("/api/chats")
def api_create_chat(body: ChatCreateIn | None = None):
    """Один чат на установку — возвращает существующий диалог."""
    title = body.title if body and body.title else None
    return store.create_chat(title or store.SINGLE_CHAT_TITLE)


@app.patch("/api/chats/{chat_id}")
def api_update_chat(chat_id: str, body: ChatUpdateIn):
    chat = store.update_chat_title(chat_id, body.title.strip() or "Без названия")
    if not chat:
        raise HTTPException(404, "Чат не найден")
    return chat


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str):
    """Очистка истории единственного чата (удаление диалога недоступно)."""
    chat = store.clear_chat_messages(chat_id)
    if not chat:
        raise HTTPException(404, "Чат не найден")
    rt = get_runtime()
    rt.uploaded_docs.clear()
    rt.tool_logs.clear()
    rt.session_tokens = 0
    return {"ok": True, "cleared": True, "chat": chat}


@app.post("/api/chats/{chat_id}/system")
def api_system_log(chat_id: str, body: SystemLogIn):
    from modules.notify import IMPORTANT, ROUTINE, infer_notify_level

    if not store.get_chat(chat_id):
        raise HTTPException(404, "Чат не найден")
    text = body.content.strip()
    if not text:
        raise HTTPException(400, "Пустое сообщение")
    imp = (body.importance or "important").strip().lower()
    if imp not in (IMPORTANT, ROUTINE):
        imp = infer_notify_level(text)
    msg = store.add_message(chat_id, "system", text, notify_level=imp)
    if not msg:
        raise HTTPException(404, "Чат не найден")
    get_runtime().log("system", text[:80])
    return msg


def _memory_store_name(name: str) -> str:
    """mode-standard устарел — файлы в «Сознательное»."""
    return "conscious" if name == "mode-standard" else name


@app.get("/api/memory")
def api_memory_list():
    return memory_store.get_stores_summary()


@app.get("/api/memory/{store_name}/{file_id}")
def api_memory_read(store_name: str, file_id: str):
    if store_name not in (
        "conscious",
        "unconscious",
        "mode-standard",
        "mode-accountant",
        "mode-marketer",
    ):
        raise HTTPException(
            400,
            "store: conscious | unconscious | mode-standard | mode-accountant | mode-marketer",
        )
    meta = memory_store.read_file(_memory_store_name(store_name), file_id)
    if not meta:
        raise HTTPException(404, "Файл не найден")
    return meta


@app.post("/api/memory/{store_name}/upload")
async def api_memory_upload(store_name: str, file: UploadFile = File(...)):
    if store_name not in (
        "conscious",
        "unconscious",
        "mode-standard",
        "mode-accountant",
        "mode-marketer",
    ):
        raise HTTPException(
            400,
            "store: conscious | unconscious | mode-standard | mode-accountant | mode-marketer",
        )
    data = await file.read()
    store_key = _memory_store_name(store_name)
    meta = memory_store.add_file(store_key, file.filename or "note.txt", data)
    jarvis_db.sync_all_from_disk()
    labels = {
        "conscious": "Сознательное",
        "unconscious": "Бессознательное",
        "mode-standard": "Сознательное",
        "mode-accountant": "Режим: Бухгалтер + Юрист",
        "mode-marketer": "Режим: Маркетолог+Дизайнер",
    }
    label = labels.get(store_key, store_key)
    get_runtime().log("memory", f"{label}: добавлен {meta['name']}")
    return meta


@app.delete("/api/memory/{store_name}/{file_id}")
def api_memory_delete(store_name: str, file_id: str):
    if store_name not in (
        "conscious",
        "unconscious",
        "mode-standard",
        "mode-accountant",
        "mode-marketer",
    ):
        raise HTTPException(
            400,
            "store: conscious | unconscious | mode-standard | mode-accountant | mode-marketer",
        )
    if memory_store.is_protected(store_name, file_id):
        raise HTTPException(403, "Системный файл нельзя удалить")
    store_key = _memory_store_name(store_name)
    if not memory_store.delete_file(store_key, file_id):
        raise HTTPException(404, "Файл не найден")
    jarvis_db.sync_all_from_disk()
    labels = {
        "conscious": "Сознательное",
        "unconscious": "Бессознательное",
        "mode-standard": "Сознательное",
        "mode-accountant": "Режим: Бухгалтер + Юрист",
        "mode-marketer": "Режим: Маркетолог+Дизайнер",
    }
    label = labels.get(store_key, store_key)
    get_runtime().log("memory", f"{label}: удалён {file_id}")
    return {"ok": True}


class MemoryCellIn(BaseModel):
    mode_code: str | None = None
    namespace: str = "default"
    cell_key: str
    content: str


@app.post("/api/memory/cells")
def api_memory_cell_set(body: MemoryCellIn):
    """Расширяемая ячейка памяти (пользователь или будущие команды агента)."""
    if not body.cell_key.strip():
        raise HTTPException(400, "cell_key обязателен")
    mode = body.mode_code.strip() if body.mode_code else None
    if mode and mode not in ("standard", "accountant", "marketer", "developer"):
        raise HTTPException(400, "mode_code: standard | accountant | marketer | developer | null")
    result = jarvis_db.set_cell(
        mode_code=mode,
        namespace=body.namespace.strip() or "default",
        cell_key=body.cell_key.strip(),
        content=body.content,
        source="user",
    )
    get_runtime().log("memory", f"Ячейка {body.cell_key} обновлена")
    return result


@app.get("/api/memory/db-info")
def api_memory_db_info():
    return jarvis_db.get_schema_summary()


@app.get("/api/menu/search")
def api_menu_search(q: str = "", limit: int = 24):
    """Поиск по ячейкам меню в jarvis.db (блоки, разделы, ключевые слова)."""
    lim = max(1, min(int(limit), 64))
    return menu_search.search_menu(q, limit=lim)


@app.post("/api/menu/rebuild")
def api_menu_rebuild():
    """Пересобрать индекс меню (каталог → ячейки jarvis.db)."""
    return menu_search.sync_catalog()


@app.get("/api/menu/stats")
def api_menu_stats():
    return menu_search.catalog_stats()


async def _drain_thinking_events(last_idx: int) -> tuple[int, list[str]]:
    """Новые строки runtime-трейса с момента last_idx."""
    rt = get_runtime()
    trace = list(getattr(rt, "thinking_trace", []) or [])
    if last_idx >= len(trace):
        return len(trace), []
    return len(trace), trace[last_idx:]


async def _emit_stream_with_thinking(
    chat_id: str,
    reply: str,
    *,
    think_idx: int = 0,
    **kwargs,
) -> AsyncIterator[str]:
    """Стрим ответа + SSE think для блока рассуждений в чате."""
    from modules.operation_stream import sse_think

    idx = think_idx
    async for chunk in _stream_assistant_reply(chat_id, reply, **kwargs):
        idx, lines = await _drain_thinking_events(idx)
        for line in lines:
            yield sse_think(line)
        yield chunk


async def _stream_assistant_reply(
    chat_id: str,
    reply: str,
    *,
    tokens: int = 0,
    meta: dict | None = None,
    instant: bool = False,
    user_text: str = "",
    history: list[dict] | None = None,
    speech_text: str | None = None,
    deepseek_key: str = "",
    model: str = "deepseek-chat",
) -> AsyncIterator[str]:
    """Чанки ответа ассистента + озвучка (только короткая речь) + done."""
    from modules.avito_report_html import is_avito_report_message
    from modules.system_health import is_health_report_message
    from modules.dialog_handlers import is_canned_smalltalk_reply
    from modules.operation_stream import append_thinking, sse_think_end
    from modules.text_sanitize import polish_assistant_reply, repair_truncated_markdown
    from modules.voice_speech import build_voice_speech_fast, finalize_speech_for_tts

    rt = get_runtime()
    append_thinking("Чат: финальная правка текста (в чат — полный ответ)")
    structured_report = is_health_report_message(reply) or is_avito_report_message(reply)
    if "<!-- jarvis-page-content -->" in (reply or ""):
        reply = (reply or "").replace("<!-- jarvis-page-content -->", "").strip()
    elif not structured_report and not is_canned_smalltalk_reply(reply or ""):
        reply = polish_assistant_reply(reply, user_text)
    if instant or len(reply) < 500 or structured_report:
        yield f"data: {json.dumps({'type': 'chunk', 'content': reply}, ensure_ascii=False)}\n\n"
    else:
        import re

        segments = re.split(r"(\n\n+)", reply)
        acc = ""
        for i, seg in enumerate(segments):
            acc += seg
            chunk = repair_truncated_markdown(acc)
            if i % 2 == 0 or i == len(segments) - 1:
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.04)
        reply = repair_truncated_markdown(acc)

    if tokens:
        rt.add_tokens(tokens)
    assistant = store.add_message(chat_id, "assistant", reply)

    speech_on = rt.chat_speech_enabled and not structured_report
    spoken = ""
    if speech_on:
        spoken = (speech_text or "").strip()
        if not spoken:
            spoken = build_voice_speech_fast(user_text, reply, history or [])
        spoken = finalize_speech_for_tts(spoken, user_text)
        rt.pending_speech_text = spoken
        append_thinking(f"Озвучка (только суть): {spoken[:72]}{'…' if len(spoken) > 72 else ''}")
        tts = await asyncio.to_thread(voice_module.synthesize_chat_speech, spoken)
        if tts.get("ok"):
            rt.log("tts", tts.get("message", "Озвучено"))
            yield f"data: {json.dumps({'type': 'tts', 'audio_url': tts['audio_url'], 'engine': tts.get('engine'), 'message': tts.get('message')}, ensure_ascii=False)}\n\n"
        else:
            rt.log("tts", tts.get("message", "Ошибка озвучки"))
            yield f"data: {json.dumps({'type': 'speak', 'text': spoken}, ensure_ascii=False)}\n\n"

    done_payload: dict = {"type": "done", "message": assistant}
    done_meta = dict(meta) if meta else {}
    if speech_on:
        done_payload["speak"] = True
        if spoken:
            done_meta["speech_text"] = spoken
    if done_meta:
        done_payload["meta"] = done_meta
    yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
    yield sse_think_end()


async def _message_stream(
    chat_id: str,
    content: str,
    insult_request_id: str | None = None,
) -> AsyncIterator[str]:
    rt = get_runtime()
    settings = _load_settings_model()
    user_msg = store.add_message(chat_id, "user", content)
    if not user_msg:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Чат не найден'}, ensure_ascii=False)}\n\n"
        return

    yield f"data: {json.dumps({'type': 'user', 'message': user_msg}, ensure_ascii=False)}\n\n"

    from modules.dialog_handlers import try_handle_early_dialog

    dialog_handled, dialog_reply = try_handle_early_dialog(content)
    if dialog_handled:
        from modules.operation_stream import append_thinking, clear_thinking_trace

        clear_thinking_trace()
        append_thinking("Ранний ответ: шаблон без вызова Qwen")
        async for chunk in _emit_stream_with_thinking(
            chat_id, dialog_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.jarvis_mood import handle_restart_command, on_user_message

    if re.match(r"^\s*RESTART\s*\.?!?\s*$", content, re.I):
        ok_restart, restart_reply = handle_restart_command(rt)
        insult_payload = {}
        try:
            from modules.insult_handler import insult_status_payload

            insult_payload = insult_status_payload(rt)
        except Exception:
            pass
        yield f"data: {json.dumps({'type': 'insult', 'kind': 'restart', 'counted': False, 'insult': insult_payload, 'mood': _mood_status(rt)}, ensure_ascii=False)}\n\n"
        async for chunk in _stream_assistant_reply(chat_id, restart_reply, instant=True):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.insult_handler import process_user_message_insult
    from modules.moderation import moderate_message, moderation_log_to_runtime

    session_key = chat_id
    mod_out = moderate_message(content, session_key)
    moderation_log_to_runtime(rt, mod_out)

    insult_ev = process_user_message_insult(
        content,
        rt,
        request_id=insult_request_id,
        session_id=session_key,
        moderation=mod_out,
    )
    if insult_ev.get("kind") != "none":
        yield f"data: {json.dumps({'type': 'insult', **insult_ev}, ensure_ascii=False)}\n\n"
    if insult_ev.get("kind") != "at_jarvis" or not insult_ev.get("counted"):
        try:
            on_user_message(rt, content, insult_counted=False)
        except Exception:
            pass
    try:
        yield f"data: {json.dumps({'type': 'mood', 'mood': _mood_status(rt)}, ensure_ascii=False)}\n\n"
    except Exception:
        pass

    if mod_out.action in ("WARN", "BLOCK") and (mod_out.response or "").strip():
        insult_handled_by_llm = (
            insult_ev.get("kind") == "at_jarvis" and bool(insult_ev.get("counted"))
        )
        if not insult_handled_by_llm:
            reply = mod_out.response.strip()
            async for chunk in _stream_assistant_reply(chat_id, reply, instant=True):
                yield chunk
            yield "data: [DONE]\n\n"
            return

    handled, setup_reply, setup_tokens, setup_meta = chat_assistant_module.try_handle_setup_message(
        content
    )
    if handled:
        from modules.ui_control import drain_ui_commands

        ui_cmds = drain_ui_commands()
        if ui_cmds:
            yield f"data: {json.dumps({'type': 'ui', 'commands': ui_cmds}, ensure_ascii=False)}\n\n"
        async for chunk in _stream_assistant_reply(
            chat_id, setup_reply, tokens=setup_tokens, meta=setup_meta
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.system_health import try_handle_system_health

    health_handled, health_reply = try_handle_system_health(content)
    if health_handled:
        async for chunk in _stream_assistant_reply(chat_id, health_reply, instant=True):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.mode_switch import try_handle_mode_switch

    chat = store.get_chat(chat_id)
    history = [
        {
            "role": m["role"],
            "content": m["content"],
            **({"notify_level": m["notify_level"]} if m.get("notify_level") else {}),
        }
        for m in chat["messages"]
    ]

    from modules.avito_overview_handler import (
        build_avito_listing_success_reply,
        build_avito_overview_reply,
        wants_avito_listing_success,
        wants_avito_overview,
    )

    if wants_avito_overview(content, history):
        yield f"data: {json.dumps({'type': 'status', 'status': 'Thinking...'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'progress', 'phase': 'avito_report', 'message': 'Собираю отчёт Авито (API + SQLite)…', 'current': 0, 'total': 1, 'percent': 20}, ensure_ascii=False)}\n\n"
        try:
            avito_reply = await asyncio.to_thread(build_avito_overview_reply, content)
        except Exception as e:
            avito_reply = (
                f"⚠️ Не удалось собрать отчёт Авито: {str(e)[:220]}\n\n"
                "Проверьте коннектор Авито и напишите «**синхронизируй авито**»."
            )
        async for chunk in _stream_assistant_reply(
            chat_id, avito_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    if wants_avito_listing_success(content, history):
        yield f"data: {json.dumps({'type': 'progress', 'phase': 'avito_report', 'message': 'Метрики объявлений из SQLite…', 'current': 0, 'total': 1, 'percent': 25}, ensure_ascii=False)}\n\n"
        try:
            listing_reply = await asyncio.to_thread(build_avito_listing_success_reply, content)
        except Exception as e:
            listing_reply = f"⚠️ Ошибка отчёта: {str(e)[:220]}"
        async for chunk in _stream_assistant_reply(
            chat_id, listing_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.avito_analyze_handler import (
        stream_avito_analyze_operation,
        wants_avito_chat_analyze,
    )
    from modules.avito_sync_handler import stream_avito_sync_operation, wants_avito_chat_sync

    if wants_avito_chat_analyze(content, history) and not wants_avito_chat_sync(
        content, history
    ):
        async for chunk in stream_avito_analyze_operation(
            chat_id,
            content,
            history,
            stream_reply=_stream_assistant_reply,
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    if wants_avito_chat_sync(content, history):
        async for chunk in stream_avito_sync_operation(
            chat_id,
            content,
            history,
            stream_reply=_stream_assistant_reply,
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    mode_handled, mode_reply = try_handle_mode_switch(content)
    if mode_handled:
        from modules.ui_control import drain_ui_commands

        ui_cmds = drain_ui_commands()
        if ui_cmds:
            yield f"data: {json.dumps({'type': 'ui', 'commands': ui_cmds}, ensure_ascii=False)}\n\n"
        async for chunk in _stream_assistant_reply(chat_id, mode_reply, instant=True):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    mode = get_mode()
    if mode == AgentMode.ACCOUNTANT and not _deepseek_configured():
        err = (
            "⚠️ Режим **Бухгалтер + Юрист** недоступен без API-ключа **DeepSeek** (`sk-…`). "
            "Добавьте ключ в **Настройках** (раздел DeepSeek)."
        )
        async for chunk in _stream_assistant_reply(chat_id, err):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    if mode == AgentMode.DEVELOPER and not _developer_mode_ready():
        err = (
            "⚠️ Режим **Разработчик** недоступен без ключа **Perplexity** (`pplx-…`). "
            "Добавьте ключ в **Настройках** (раздел Perplexity) и включите сервис."
        )
        async for chunk in _stream_assistant_reply(chat_id, err):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.url_page_handler import try_handle_url_page_request, user_wants_page_lookup

    if user_wants_page_lookup(content, history):
        yield f"data: {json.dumps({'type': 'status', 'status': 'Searching Web...'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'progress', 'phase': 'browse', 'message': 'Открываю страницу в браузере Jarvis…', 'current': 0, 'total': 1, 'percent': 15}, ensure_ascii=False)}\n\n"
    try:
        url_handled, url_reply = await asyncio.to_thread(
            try_handle_url_page_request, content, history
        )
    except Exception as e:
        url_handled, url_reply = True, (
            f"Не удалось обработать ссылку: {str(e)[:200]}. "
            "Проверьте, что сервер Jarvis запущен и Chromium установлен."
        )
    if url_handled:
        async for chunk in _stream_assistant_reply(
            chat_id, url_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.exchange_rates import try_handle_exchange_rate
    from modules.web_research import user_wants_web_research, research_web_query_async
    from modules.agent import is_voice_interaction_mode
    import queue as thread_queue

    try:
        ex_handled, ex_reply = await asyncio.to_thread(
            try_handle_exchange_rate, content, history
        )
    except Exception as e:
        ex_handled, ex_reply = True, f"⚠️ Не удалось получить курс: {str(e)[:200]}"
    if ex_handled:
        yield f"data: {json.dumps({'type': 'status', 'status': 'IDLE'}, ensure_ascii=False)}\n\n"
        async for chunk in _stream_assistant_reply(
            chat_id, ex_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    from modules.jarvis_capabilities import try_handle_jarvis_meta_question

    try:
        meta_handled, meta_reply = await asyncio.to_thread(
            try_handle_jarvis_meta_question, content
        )
    except Exception:
        meta_handled, meta_reply = False, ""
    if meta_handled and meta_reply:
        yield f"data: {json.dumps({'type': 'status', 'status': 'IDLE'}, ensure_ascii=False)}\n\n"
        async for chunk in _stream_assistant_reply(
            chat_id, meta_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    if user_wants_web_research(content, history):
        yield f"data: {json.dumps({'type': 'status', 'status': 'Searching Web...'}, ensure_ascii=False)}\n\n"
        prog_q: thread_queue.Queue[tuple[int, int, str]] = thread_queue.Queue()
        voice_mode = is_voice_interaction_mode()

        async def _run_research() -> str:
            return await asyncio.to_thread(
                research_web_query_async,
                content,
                progress_queue=prog_q,
                history=history,
                max_pages=10,
                deepseek_key=settings.deepseek_key,
                model=settings.default_model,
                voice_mode=voice_mode,
            )

        task = asyncio.create_task(_run_research())
        while not task.done():
            while not prog_q.empty():
                cur, tot, msg = prog_q.get_nowait()
                pct = int((cur / max(tot, 1)) * 85) if tot else 10
                yield f"data: {json.dumps({'type': 'progress', 'phase': 'web_research', 'message': msg, 'current': cur, 'total': tot, 'percent': pct}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.15)
        while not prog_q.empty():
            cur, tot, msg = prog_q.get_nowait()
            pct = int((cur / max(tot, 1)) * 85) if tot else 10
            yield f"data: {json.dumps({'type': 'progress', 'phase': 'web_research', 'message': msg, 'current': cur, 'total': tot, 'percent': pct}, ensure_ascii=False)}\n\n"
        try:
            research_reply = await task
        except Exception as e:
            research_reply = f"⚠️ Не удалось выполнить веб-исследование: {str(e)[:220]}"
        async for chunk in _stream_assistant_reply(
            chat_id, research_reply, instant=True, user_text=content
        ):
            yield chunk
        yield "data: [DONE]\n\n"
        return

    yield f"data: {json.dumps({'type': 'status', 'status': 'Thinking...'}, ensure_ascii=False)}\n\n"
    from modules.operation_stream import append_thinking, clear_thinking_trace, sse_think

    clear_thinking_trace()
    append_thinking("SSE: запрос принят, запуск generate_reply")

    think_idx = 0
    reply_task = asyncio.create_task(
        asyncio.to_thread(
            generate_reply,
            content,
            history,
            settings.deepseek_key,
            settings.default_model,
            settings.nanobanana_key,
            perplexity_key=settings.perplexity_key,
            perplexity_model=settings.perplexity_model,
        )
    )
    while not reply_task.done():
        think_idx, lines = await _drain_thinking_events(think_idx)
        for line in lines:
            yield sse_think(line)
        await asyncio.sleep(0.08)
    think_idx, lines = await _drain_thinking_events(think_idx)
    for line in lines:
        yield sse_think(line)

    reply, tokens = reply_task.result()
    if rt.status == "Generating image..." or rt.status == "Generating video...":
        yield f"data: {json.dumps({'type': 'status', 'status': rt.status}, ensure_ascii=False)}\n\n"

    from modules.ui_control import drain_ui_commands

    ui_cmds = drain_ui_commands()
    if ui_cmds:
        yield f"data: {json.dumps({'type': 'ui', 'commands': ui_cmds}, ensure_ascii=False)}\n\n"

    async for chunk in _emit_stream_with_thinking(
        chat_id,
        reply,
        think_idx=think_idx,
        tokens=tokens,
        user_text=content,
        history=history,
        deepseek_key=settings.deepseek_key,
        model=settings.default_model,
    ):
        yield chunk
    try:
        from modules.insult_handler import clear_insult_turn

        clear_insult_turn(rt)
    except Exception:
        pass
    yield "data: [DONE]\n\n"


@app.post("/api/chats/{chat_id}/messages")
async def api_send_message(chat_id: str, body: MessageIn):
    rt = get_runtime()
    if not store.get_chat(chat_id):
        raise HTTPException(404, "Чат не найден")
    if not body.content.strip():
        raise HTTPException(400, "Пустое сообщение")
    if body.mode:
        try:
            set_mode(AgentMode(body.mode))
        except ValueError:
            pass
    if body.voice_enabled is not None:
        set_voice(body.voice_enabled)
    if body.chat_speech_enabled is not None:
        set_chat_speech(body.chat_speech_enabled)
    if body.chat_surface_mode in ("text", "voice", "multimedia"):
        rt.chat_surface_mode = body.chat_surface_mode

    return StreamingResponse(
        _message_stream(
            chat_id,
            body.content.strip(),
            insult_request_id=body.insult_request_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/files/upload")
async def api_upload_files(
    files: list[UploadFile] = File(...),
    mode: str | None = None,
):
    rt = get_runtime()
    from modules.agent import register_document

    saved = []
    acc_mode = mode == "accountant" or get_mode() == AgentMode.ACCOUNTANT

    for f in files:
        data = await f.read()
        fname = f.filename or "file.bin"
        ext = Path(fname).suffix.lower()

        if voice_module.is_audio_filename(fname):
            try:
                info = voice_module.set_base_voice(data, fname)
                rt.log("voice", f"Голос из чата: {fname}")
                saved.append(
                    {
                        "name": fname,
                        "type": "voice_base",
                        "indexed": True,
                        "filename": info.get("filename"),
                        "size_bytes": info.get("size_bytes"),
                        "message": "Базовый голос обновлён — озвучка «Речь в текст» использует этот файл.",
                    }
                )
            except ValueError as e:
                saved.append({"name": fname, "indexed": False, "error": str(e), "type": "voice_base"})
            continue

        if ext in {".txt", ".md", ".json"}:
            mem = chat_assistant_module.handle_memory_upload(fname, data)
            if mem.get("ok"):
                rt.log("memory", f"Из чата: {mem['name']} → {mem['store']}")
                saved.append(
                    {
                        "name": mem["name"],
                        "type": "memory",
                        "store": mem["store"],
                        "label": mem["label"],
                        "indexed": True,
                    }
                )
            else:
                saved.append({"name": fname, "indexed": False, "error": mem.get("error"), "type": "memory"})
            continue

        from modules.image_tools import is_image_filename, save_chat_image

        if is_image_filename(fname) and not acc_mode:
            try:
                info = save_chat_image(data, fname)
                rt.last_chat_image_id = info["id"]
                rt.log("image", f"Картинка: {fname} → {info['id']}")
                saved.append(
                    {
                        "name": fname,
                        "type": "chat_image",
                        "indexed": True,
                        "image_id": info["id"],
                        "url": info["url"],
                        "analysis": info["analysis"],
                        "markdown": info["markdown"],
                        "width": info["width"],
                        "height": info["height"],
                    }
                )
            except Exception as e:
                saved.append({"name": fname, "indexed": False, "error": str(e), "type": "chat_image"})
            continue

        if acc_mode:
            result = documents.process_upload(fname, data)
            if result.get("ok") and result.get("summary_markdown"):
                rt.log("documents", f"Выписка: {fname} — {result.get('transaction_count', 0)} операций")
                register_document(fname)
                saved.append(
                    {
                        "name": fname,
                        "stored": result.get("stored", fname),
                        "indexed": True,
                        "type": "bank_statement",
                        "transaction_count": result.get("transaction_count"),
                        "summary_markdown": result.get("summary_markdown"),
                    }
                )
            elif result.get("ok"):
                rt.log("documents", f"Файл бухгалтера: {fname}")
                register_document(fname)
                saved.append({"name": fname, "indexed": True, "type": "document"})
            else:
                rt.log("documents", result.get("error", "Ошибка обработки"))
                saved.append({"name": fname, "indexed": False, "error": result.get("error")})
        elif ext == ".pdf":
            name = store.save_uploaded_file(fname, data)
            register_document(fname)
            preview = ""
            pages = 0
            try:
                from modules.document_tools import read_document

                stored_path = store.FILES_DIR / name
                doc = read_document(str(stored_path), max_chars=8000)
                preview = (doc.get("content") or "")[:500]
                pages = int(doc.get("pages") or 0)
                rt.log("docs", f"PDF: {fname} — {pages} стр., {doc.get('chars', 0)} симв.")
            except Exception as e:
                rt.log("docs", f"PDF {fname}: {e}")
            saved.append(
                {
                    "name": fname,
                    "stored": name,
                    "indexed": True,
                    "type": "pdf",
                    "pages": pages,
                    "preview": preview,
                }
            )
        else:
            name = store.save_uploaded_file(fname, data)
            register_document(fname)
            rt.log("rag", f"Файл: {fname}")
            saved.append({"name": fname, "stored": name, "indexed": True})

    return {"files": saved, "mode": "accountant" if acc_mode else "standard"}


@app.get("/api/accountant/counterparties")
def api_counterparties():
    return {"items": documents.list_counterparties()}


@app.post("/api/accountant/documents/contract")
def api_generate_contract(body: GenerateDocIn | None = None):
    cid = body.counterparty_id if body else None
    info = documents.generate_contract_docx(cid)
    get_runtime().log("documents", info.get("message", "Договор"))
    return info


@app.post("/api/accountant/documents/invoice")
def api_generate_invoice(body: GenerateDocIn | None = None):
    body = body or GenerateDocIn()
    info = documents.generate_invoice_xlsx(body.counterparty_id, body.amount)
    get_runtime().log("documents", info.get("message", "Счёт"))
    return info


@app.get("/api/accountant/download/{file_id}")
def api_download_generated(file_id: str):
    path = documents.get_generated_path(file_id)
    if not path:
        raise HTTPException(404, "Файл не найден")
    media = "application/octet-stream"
    if path.suffix == ".docx":
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif path.suffix == ".xlsx":
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/voice/slots")
def api_voice_slots():
    return {"slots": voice_module.get_slots()}


@app.post("/api/voice/slots/{slot}/upload")
async def api_voice_upload(slot: int, file: UploadFile = File(...)):
    data = await file.read()
    result = voice_module.validate_audio(slot, data, file.filename or "sample.wav")
    get_runtime().log("voice", f"Слот {slot}: {result['message']}")
    return result


@app.get("/api/voice/preview")
def api_voice_preview():
    path = voice_module.get_preview_path()
    if not path or not path.exists():
        raise HTTPException(404, "Базовый голос не найден")
    media_map = {
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".webm": "audio/webm",
        ".m4a": "audio/mp4",
    }
    media = media_map.get(path.suffix.lower(), "application/octet-stream")
    mtime = int(path.stat().st_mtime)
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "ETag": f'"{mtime}"',
        },
    )


@app.get("/api/voice/base")
def api_voice_base_info():
    return voice_module.get_base_voice_info()


@app.post("/api/voice/base/upload")
async def api_voice_base_upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        info = voice_module.set_base_voice(data, file.filename or "voice.ogg")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    get_runtime().log("voice", f"Базовый голос: {info.get('filename')}")
    return info


@app.get("/api/docs/readiness")
def api_docs_readiness():
    """MarkItDown: локальное чтение PDF/Office без токенов LLM."""
    from modules.document_tools import get_document_engine_status, supported_formats_help

    st = get_document_engine_status()
    return {**st, "help": supported_formats_help()}


@app.get("/api/voice/readiness")
def api_voice_readiness():
    """Проверка: можно ли озвучивать ответы в чате."""
    from modules.voice_stt import get_stt_status

    tts = voice_module.get_chat_voice_readiness()
    stt = get_stt_status()
    return {
        **tts,
        "stt": stt,
        "dialog_ready": bool(tts.get("ready")) and bool(stt.get("package_installed")) and bool(stt.get("ffmpeg")),
    }


@app.get("/api/voice/stt/status")
def api_voice_stt_status():
    from modules.voice_stt import get_stt_status

    return get_stt_status()


@app.post("/api/voice/transcribe")
async def api_voice_transcribe(file: UploadFile = File(...)):
    """Локальное STT (GigaAM-v3) — голосовой диалог."""
    from modules.voice_stt import transcribe_audio, get_stt_status

    data = await file.read()
    fname = file.filename or "speech.webm"
    try:
        result = transcribe_audio(data, filename=fname)
        get_runtime().log("stt", f"Распознано: {result.get('text', '')[:80]}")
        return result
    except FileNotFoundError as e:
        st = get_stt_status()
        hint = st.get("message") or "install-chat-voice.bat"
        raise HTTPException(
            400,
            f"STT: не найден ffmpeg для GigaAM. Запустите install-chat-voice.bat. ({e})",
        ) from e
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        msg = str(e).strip() or "stt_failed"
        if "WinError 2" in msg or "не удается найти" in msg.lower():
            msg = (
                "STT: ffmpeg не в PATH (нужен GigaAM). "
                "Перезапустите Jarvis или install-chat-voice.bat. "
                f"({msg})"
            )
        raise HTTPException(400, msg) from e


@app.post("/api/voice/speak")
def api_voice_speak(body: VoiceSpeakIn):
    if not body.text.strip():
        raise HTTPException(400, "Пустой текст")
    result = voice_module.synthesize_chat_speech(body.text)
    if not result.get("ok"):
        raise HTTPException(
            503,
            detail=result.get("message") or result.get("error") or "synthesis_failed",
        )
    return result


@app.get("/api/icq-smileys/{smiley_id}.png")
def api_icq_smiley(smiley_id: str):
    from modules.icq_smileys import image_path

    path = image_path(smiley_id)
    if not path:
        raise HTTPException(404, "Смайлик не найден")
    return FileResponse(path, media_type="image/png", filename=path.name)


@app.get("/api/icq-smileys/status")
def api_icq_smileys_status():
    from modules.icq_smileys import is_enabled, load_catalog

    return {
        "enabled": is_enabled(),
        "count": len(load_catalog().get("smileys") or []),
        "token_format": ":icq:{id}:",
    }


@app.get("/api/images/{filename}")
def api_generated_image(filename: str):
    from modules import nano_banana as nb_mod
    from modules.media_generation import IMAGES_DIR
    import re
    from pathlib import Path

    path = nb_mod.get_image_path(filename)
    if not path:
        safe = re.sub(r"[^a-zA-Z0-9._-]", "", Path(filename).name)
        alt = IMAGES_DIR / safe if safe else None
        if alt and alt.is_file():
            path = alt
    if not path:
        raise HTTPException(404, "Изображение не найдено")
    media_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    media = media_map.get(path.suffix.lower(), "image/png")
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/chat-images/{image_id}")
def api_chat_image(image_id: str, ext: str | None = None):
    from modules.image_tools import resolve_chat_image_path

    try:
        path = resolve_chat_image_path(image_id, ext_hint=ext)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    media_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    media = media_map.get(path.suffix.lower(), "image/png")
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/api/videos/{filename}")
def api_generated_video(filename: str):
    from modules.media_generation import get_video_path

    path = get_video_path(filename)
    if not path:
        raise HTTPException(404, "Видео не найдено")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.get("/api/voice/generated/{filename}")
def api_voice_generated(filename: str):
    path = voice_module.get_generated_audio_path(filename)
    if not path:
        raise HTTPException(404, "Файл не найден")
    media = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/voice/download-jarvis")
def api_download_jarvis_voice():
    return voice_module.start_silero_install()


@app.get("/api/voice/download-status")
def api_download_status():
    return voice_module.get_silero_status()


class SileroVoiceSettingsIn(BaseModel):
    speaker: str | None = None
    tempo: float | None = None


class SileroStressLexiconIn(BaseModel):
    lines: str = ""
    plain: str | None = None  # удалить запись по plain-ключу


@app.get("/api/voice/speakers")
def api_voice_speakers():
    from modules import silero_tts

    return silero_tts.get_voice_config()


@app.put("/api/voice/speaker")
def api_voice_speaker_set(body: SileroVoiceSettingsIn):
    from modules import silero_tts

    try:
        return silero_tts.set_voice_settings(speaker=body.speaker, tempo=body.tempo)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.put("/api/voice/settings")
def api_voice_settings(body: SileroVoiceSettingsIn):
    from modules import silero_tts

    try:
        return silero_tts.set_voice_settings(speaker=body.speaker, tempo=body.tempo)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/voice/stress-lexicon")
def api_voice_stress_lexicon_get():
    from modules import silero_tts

    return {
        "entries": silero_tts.list_stress_lexicon(),
        "stress_flags": silero_tts.SILERO_STRESS_FLAGS,
        "hint": "Пишите «+» перед ударной гласной: на св+язи",
    }


@app.put("/api/voice/stress-lexicon")
def api_voice_stress_lexicon_put(body: SileroStressLexiconIn):
    from modules import silero_tts

    if body.plain:
        entries = silero_tts.delete_stress_lexicon_entry(body.plain)
    else:
        entries = silero_tts.save_stress_lexicon_lines(body.lines)
        if (body.lines or "").strip() and not entries:
            raise HTTPException(
                400,
                "Добавьте «+» перед ударной гласной, например: на св+язи",
            )
    return {"entries": entries, "stress_flags": silero_tts.SILERO_STRESS_FLAGS}


@app.post("/api/voice/preview-speaker")
def api_voice_preview_speaker(body: SileroVoiceSettingsIn):
    from modules import silero_tts

    if not body.speaker:
        raise HTTPException(400, "Укажите speaker")
    try:
        path = silero_tts.preview_speaker(body.speaker, tempo=body.tempo)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@app.post("/api/voice/purge-legacy-tts")
def api_voice_purge_legacy():
    from modules import silero_tts

    return silero_tts.purge_legacy_tts_models(force=True)


# --- OpenConnect VPN ---


class OpenConnectConfigIn(BaseModel):
    server: str = ""
    port: int = 443
    username: str = ""
    password: str = ""
    use_jarvis_preset: bool = False
    openconnect_path: str = ""
    server_cert_pin: str = ""


class OpenConnectCertPinIn(BaseModel):
    server: str = Field(..., min_length=3, max_length=253)
    port: int = 443


@app.get("/api/vpn/openconnect/status")
def api_vpn_openconnect_status():
    return vpn_module.status_dict()


@app.get("/api/vpn/openconnect/config")
def api_vpn_openconnect_config():
    return vpn_module.get_config()


@app.put("/api/vpn/openconnect/config")
def api_vpn_openconnect_config_put(body: OpenConnectConfigIn):
    return vpn_module.save_config(
        server=body.server,
        port=body.port,
        username=body.username,
        password=body.password,
        use_jarvis_preset=body.use_jarvis_preset,
        openconnect_path=body.openconnect_path,
        server_cert_pin=body.server_cert_pin,
    )


@app.post("/api/vpn/openconnect/connect")
def api_vpn_openconnect_connect():
    try:
        return vpn_module.connect()
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/vpn/openconnect/disconnect")
def api_vpn_openconnect_disconnect():
    return vpn_module.disconnect()


@app.get("/api/vpn/openconnect/log")
def api_vpn_openconnect_log(limit: int = Query(80, ge=1, le=200)):
    return {"lines": vpn_module.get_log_tail(limit)}


@app.post("/api/vpn/openconnect/cert-pin")
def api_vpn_openconnect_cert_pin(body: OpenConnectCertPinIn):
    try:
        return vpn_module.resolve_server_cert_pin(body.server, body.port)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except OSError as e:
        raise HTTPException(502, f"Не удалось получить сертификат: {e}") from e


# --- Консоль / PowerShell ---


class ShellOpenIn(BaseModel):
    shell: str = "powershell"
    cwd: str = ""


class ShellRunIn(BaseModel):
    command: str = Field(..., min_length=1, max_length=8000)
    shell: str = "powershell"
    cwd: str = ""
    visible: bool = False
    timeout: int = Field(120, ge=5, le=600)


class ShellSessionSendIn(BaseModel):
    command: str = Field(..., min_length=1, max_length=8000)


@app.get("/api/shell/status")
def api_shell_status():
    return pc_shell_module.status_dict()


@app.post("/api/shell/open")
def api_shell_open(body: ShellOpenIn):
    cwd = body.cwd.strip() or None
    return pc_shell_module.open_console(shell=body.shell, cwd=cwd)


@app.post("/api/shell/run")
def api_shell_run(body: ShellRunIn):
    try:
        res = pc_shell_module.run_command(
            body.command,
            shell=body.shell,
            cwd=body.cwd.strip() or None,
            visible=body.visible,
            timeout=body.timeout,
        )
        return res
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/shell/session/start")
def api_shell_session_start(body: ShellOpenIn):
    cwd = body.cwd.strip() or None
    return pc_shell_module.start_session(shell=body.shell, cwd=cwd)


@app.post("/api/shell/session/send")
def api_shell_session_send(body: ShellSessionSendIn):
    try:
        return pc_shell_module.send_session_command(body.command)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/shell/session/close")
def api_shell_session_close():
    return pc_shell_module.close_session()


# --- Hugging Face Skills ---


@app.get("/api/hf/status")
def api_hf_status():
    from modules.hf_hub_client import status_payload

    return status_payload()


@app.post("/api/hf/search")
def api_hf_search(body: HfSearchIn):
    from modules.hf_hub_client import search_hub_result, token_configured

    if not token_configured():
        raise HTTPException(400, "Нет токена HF — положите huggingface.key в backend/config/")
    try:
        from modules.hf_hub_client import search_hub_result

        result = search_hub_result(
            body.query,
            repo_type=body.repo_type,
            limit=min(body.limit, 20),
        )
    except Exception as e:
        raise HTTPException(502, f"HF search: {e}") from e
    return {
        "items": result["items"],
        "query": body.query,
        "repo_type": body.repo_type,
        "search_mode": result.get("search_mode", "exact"),
        "terms": result.get("terms", []),
    }


@app.get("/api/hf/installed")
def api_hf_installed():
    from modules.hf_skills_store import list_installed, summarize_registry

    return {"skills": list_installed(), **summarize_registry()}


@app.post("/api/hf/download")
def api_hf_download(body: HfDownloadIn):
    from modules.hf_hub_client import token_configured
    from modules.hf_skills_store import install_skill

    if not token_configured():
        raise HTTPException(400, "Нет токена HF — положите huggingface.key в backend/config/")
    try:
        manifest = install_skill(
            body.repo_id,
            repo_type=body.repo_type,
            revision=body.revision or "main",
            filenames=body.filenames or None,
            allow_patterns=body.allow_patterns or None,
            label=body.label,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"HF download: {e}") from e
    return manifest


@app.post("/api/hf/enable")
def api_hf_enable(body: HfEnableIn):
    from modules.hf_skills_store import set_enabled

    try:
        return set_enabled(body.skill_id, body.enabled)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.delete("/api/hf/installed/{skill_id}")
def api_hf_remove(skill_id: str):
    from modules.hf_skills_store import remove_skill

    if not remove_skill(skill_id):
        raise HTTPException(404, "Навык не найден")
    return {"ok": True, "skill_id": skill_id}


@app.get("/api/hf/repo-files")
def api_hf_repo_files(repo_id: str, repo_type: str = "model", revision: str = "main"):
    from modules.hf_hub_client import list_files, token_configured

    if not token_configured():
        raise HTTPException(400, "Нет токена HF")
    try:
        files = list_files(repo_id, repo_type=repo_type, revision=revision)
    except Exception as e:
        raise HTTPException(502, str(e)) from e
    return {"repo_id": repo_id, "files": files[:200]}


# --- Коннектор Telegram (Bot API) ---


@app.get("/api/telegram/status")
def api_tg_status():
    return tg_twin.to_dict()


@app.post("/api/telegram/toggle")
def api_tg_toggle(body: TgToggleIn):
    return tg_twin.toggle(body.enabled)


@app.get("/api/telegram/config")
def api_tg_config():
    return tg_twin.get_config()


@app.put("/api/telegram/config")
def api_tg_config_put(body: TgConfigIn):
    return tg_twin.save_config(
        body.blocklist_ids,
        bot_token=body.bot_token,
        telegram_proxy=body.telegram_proxy,
    )


@app.get("/api/telegram/bot-logic")
def api_tg_bot_logic_get():
    logic = tg_bot_logic.load_logic()
    return {**tg_bot_logic.get_logic_info(), "logic": logic}


@app.put("/api/telegram/bot-logic")
def api_tg_bot_logic_put(body: dict):
    return tg_bot_logic.save_logic(body)


@app.get("/api/telegram/bot-logic/example")
def api_tg_bot_logic_example():
    if tg_bot_logic.EXAMPLE_FILE.is_file():
        return json.loads(tg_bot_logic.EXAMPLE_FILE.read_text(encoding="utf-8"))
    return {}


# --- Коннектор Авито ---


@app.get("/api/avito/status")
def api_avito_status():
    return avito_module.to_dict()


@app.get("/api/avito/config")
def api_avito_config():
    return avito_module.get_config()


@app.put("/api/avito/config")
def api_avito_config_put(body: AvitoConfigIn):
    return avito_module.save_config(
        client_id=body.client_id,
        client_secret=body.client_secret,
        user_id=body.user_id,
    )


@app.post("/api/avito/toggle")
def api_avito_toggle(body: AvitoToggleIn):
    return avito_module.toggle(body.enabled)


@app.post("/api/avito/sync")
def api_avito_sync():
    return avito_module.sync_day()


class MailAccountIn(BaseModel):
    id: str | None = None
    label: str = ""
    email: str = ""
    password: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_ssl: bool = True
    enabled: bool = True
    preset: str = ""
    provider: str = ""
    slot: int = 0


class MailConfigIn(BaseModel):
    accounts: list[MailAccountIn] = Field(default_factory=list)


@app.get("/api/mail/status")
def api_mail_status():
    return mail_client.to_dict()


@app.get("/api/mail/config")
def api_mail_config():
    return mail_client.get_config()


@app.put("/api/mail/config")
def api_mail_config_put(body: MailConfigIn):
    try:
        return mail_client.save_accounts([a.model_dump() for a in body.accounts])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/mail/test/{account_id}")
def api_mail_test(account_id: str):
    try:
        return mail_client.test_account(account_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/mail/messages/{account_id}")
def api_mail_messages(
    account_id: str,
    folder: str = "INBOX",
    limit: int = 20,
    unread_only: bool = False,
):
    try:
        return mail_client.list_messages(
            account_id,
            folder=folder,
            limit=limit,
            unread_only=unread_only,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/mail/message/{account_id}/{uid}")
def api_mail_message(account_id: str, uid: str, folder: str = "INBOX"):
    try:
        return mail_client.get_message(uid, account_id, folder=folder)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/mail/message/{account_id}/{uid}/read")
def api_mail_mark_read(account_id: str, uid: str, folder: str = "INBOX", read: bool = True):
    try:
        return mail_client.set_read_flag(uid, read=read, account_id=account_id, folder=folder)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/avito/metrics")
def api_avito_metrics(date_from: str | None = None, date_to: str | None = None):
    return avito_module.get_metrics(date_from, date_to)


@app.get("/api/avito/account")
def api_avito_account():
    from modules.avito_messenger import fetch_account_profile, get_account_from_db

    try:
        row = get_account_from_db()
        if not row:
            row = fetch_account_profile()
        return {"ok": True, "account": row}
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/avito/chats")
def api_avito_chats(limit: int = 50, offset: int = 0, q: str | None = None):
    from modules.avito_messenger import get_chats_from_db

    try:
        return get_chats_from_db(limit=min(limit, 200), offset=offset, search=q)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/avito/chats/{chat_id}/messages")
def api_avito_chat_messages(chat_id: str, limit: int = 100, offset: int = 0):
    from modules.avito_messenger import get_messages_from_db

    try:
        return get_messages_from_db(chat_id, limit=min(limit, 500), offset=offset)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/avito/sync/chats")
def api_avito_sync_chats(
    max_chats: int = 500,
    messages_per_chat: int = 100,
    days: int | None = None,
):
    try:
        if days and days > 0:
            from modules.avito_chat_analytics import sync_chats_for_period

            return sync_chats_for_period(
                days=days,
                max_chats=max_chats,
                messages_per_chat=messages_per_chat,
            )
        from modules.avito_messenger import sync_chats

        return sync_chats(max_chats=max_chats, messages_per_chat=messages_per_chat)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/avito/analyze")
def api_avito_analyze(days: int = 30, chat_id: str | None = None):
    from modules.avito_chat_analytics import analyze_chats, format_analysis_report

    try:
        data = analyze_chats(days=days, chat_id=chat_id)
        return {"ok": True, "data": data, "report": format_analysis_report(data)}
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/avito/pipeline")
def api_avito_pipeline(days: int = 30):
    from modules.avito_chat_analytics import run_full_pipeline

    try:
        return run_full_pipeline(days=days)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/avito/chats/{chat_id}")
def api_avito_purge_chat(chat_id: str):
    from modules.avito_chat_analytics import purge_chat_archive

    try:
        return purge_chat_archive(chat_id)
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/avito/sync/all")
def api_avito_sync_all(force: bool = False, stats_days: int = 14, max_chats: int = 500):
    from modules.avito_api import sync_all_avito_data

    try:
        return sync_all_avito_data(
            stats_days=max(1, min(stats_days, 30)),
            max_chats=max(10, min(max_chats, 800)),
            force=bool(force),
        )
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/avito/probe")
def api_avito_probe():
    from modules.avito_messenger import probe_api

    return probe_api()


# --- Телефония / АТС ---


@app.get("/api/telephony/config")
def api_telephony_config_get():
    return telephony_module.get_config()


@app.put("/api/telephony/config")
def api_telephony_config_put(body: TelephonyConfigIn):
    saved = telephony_module.save_config(body.model_dump())
    return {**telephony_module.to_dict(), **saved}


@app.get("/api/telephony/status")
def api_telephony_status():
    return telephony_module.to_dict()


@app.post("/api/telephony/synthesize")
def api_telephony_synthesize():
    try:
        path = telephony_module.synthesize_greeting()
        return {"ok": True, "path": str(path.name)}
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/telephony/test-webhook")
def api_telephony_test_webhook():
    return telephony_module.test_webhook_local()


@app.post("/api/telephony/test-call")
def api_telephony_test_call(body: TelephonyTestCallIn):
    if not body.to_number.strip():
        raise HTTPException(400, "to_number required")
    return telephony_module.mango_outbound_call(body.to_number.strip())


@app.api_route(
    "/api/telephony/webhook",
    methods=["GET", "POST"],
)
async def api_telephony_webhook(request: Request):
    form = dict(await request.form()) if request.method == "POST" else {}
    params = dict(request.query_params)
    if request.method == "GET" and params:
        return telephony_module.handle_scenario_query(
            {k: str(v) for k, v in params.items()}
        )
    raw = await request.body()
    json_body = None
    if raw and request.headers.get("content-type", "").startswith("application/json"):
        try:
            json_body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            json_body = None
    headers = {k.lower(): v for k, v in request.headers.items()}
    code, body = telephony_module.handle_webhook(
        headers=headers,
        form={k: str(v) for k, v in form.items()} if form else None,
        json_body=json_body,
        raw_body=raw,
    )
    if code != 200:
        raise HTTPException(code, body if isinstance(body, str) else str(body))
    return body


@app.api_route(
    "/api/telephony/scenario",
    methods=["GET", "POST"],
)
async def api_telephony_scenario(request: Request):
    """Сценарий Mango «HTTP-запрос к внешней системе» при входящем звонке."""
    if request.method == "POST":
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}
        if form.get("json"):
            try:
                payload = json.loads(str(form.get("json")))
                params.update({k: str(v) for k, v in payload.items() if v is not None})
            except json.JSONDecodeError:
                pass
    else:
        params = {k: str(v) for k, v in request.query_params.items()}
    return telephony_module.handle_scenario_query(params)


@app.get("/api/telephony/media/{filename}")
def api_telephony_media(filename: str):
    safe = Path(filename).name
    if safe == "greeting.mp3":
        path = telephony_module.get_greeting_media_path()
    else:
        path = telephony_module.CACHE_DIR / safe
    if not path or not path.is_file():
        raise HTTPException(404, "audio not found")
    return FileResponse(path, media_type="audio/mpeg")


def _mount_frontend_dist() -> None:
    """Собранный UI (npm run build) — один порт :8000, без Vite."""
    if not FRONTEND_DIST.is_dir():
        return
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.get("/")
    def spa_index():
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{spa_path:path}")
    def spa_files(spa_path: str):
        if spa_path.startswith("api") or spa_path == "docs":
            raise HTTPException(404, "Not Found")
        target = FRONTEND_DIST / spa_path
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIST / "index.html")


_mount_frontend_dist()


if __name__ == "__main__":
    import uvicorn

    reload = os.getenv("JARVIS_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run("main:app", host=JARVIS_HOST, port=JARVIS_PORT, reload=reload)
