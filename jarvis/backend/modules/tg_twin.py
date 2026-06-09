"""
Материнское ядро telegram — Bot API (токен BotFather), polling и bot_logic.json.
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import httpx

from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
TG_DIR = DATA_DIR / "telegram"
CONFIG_FILE = TG_DIR / "config.json"
# Сессия userbot для модуля tg_analyst (не используется ботом-двойником)
SESSION_PATH = TG_DIR / "userbot"


class TgTwinStatus(str, Enum):
    OFF = "off"
    WAITING = "waiting"
    ACTIVE = "active"
    NEED_TOKEN = "need_token"
    ERROR = "error"


@dataclass
class TgTwinState:
    enabled: bool = False
    status: TgTwinStatus = TgTwinStatus.OFF
    last_event: str = ""
    error: str | None = None
    bot_username: str | None = None
    blocklist_ids: list[str] = field(default_factory=list)


_state = TgTwinState()
_start_lock = threading.Lock()
_poll_thread: threading.Thread | None = None
_poll_stop = threading.Event()
_update_offset = 0
_messages_handled = 0
_PROXY_UNSET = object()
_active_proxy: str | None | object = _PROXY_UNSET
_proxy_lock = threading.Lock()


def _default_config() -> dict:
    return {
        "bot_token": "",
        "blocklist_ids": [],
        "telegram_proxy": "",
        "mother_core_enabled": True,
    }


def _load_config_file() -> dict:
    TG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**_default_config(), **raw}
        except Exception:
            pass
    return _default_config()


def _save_config_file(data: dict) -> None:
    TG_DIR.mkdir(parents=True, exist_ok=True)
    merged = {**_default_config(), **data}
    CONFIG_FILE.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _mask_token(token: str) -> str:
    t = (token or "").strip()
    if not t or len(t) < 12:
        return ""
    return t[:8] + "••••••••"


def _token_configured(token: str) -> bool:
    t = (token or "").strip()
    return len(t) >= 20 and ":" in t


def _normalize_blocklist_entry(raw: str) -> str:
    s = str(raw).strip()
    if not s:
        return ""
    if s.lstrip("-").isdigit():
        return s
    name = s.lstrip("@").lower()
    return f"@{name}" if name else ""


def get_config() -> dict:
    cfg = _load_config_file()
    token = (cfg.get("bot_token") or "").strip()
    configured = _token_configured(token)
    from modules import tg_bot_logic

    return {
        "bot_token": _mask_token(token) if configured else "",
        "bot_token_configured": configured,
        "blocklist_ids": [str(x) for x in cfg.get("blocklist_ids", [])],
        "bot_username": _state.bot_username,
        "telegram_proxy": (cfg.get("telegram_proxy") or "").strip(),
        "ready": configured,
        **tg_bot_logic.get_logic_info(),
    }


def save_config(
    blocklist_ids: list[str] | None = None,
    *,
    bot_token: str | None = None,
    telegram_proxy: str | None = None,
) -> dict:
    cfg = _load_config_file()
    token_just_saved = False

    if bot_token is not None:
        incoming = bot_token.strip()
        if "•" in incoming:
            pass
        elif incoming:
            if not _token_configured(incoming):
                return {
                    **get_config(),
                    "save_ok": False,
                    "message": "Неверный формат токена (нужен вид 123456789:AAH…)",
                }
            cfg["bot_token"] = incoming
            token_just_saved = True
        else:
            cfg["bot_token"] = ""

    if blocklist_ids is not None:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in blocklist_ids:
            norm = _normalize_blocklist_entry(raw)
            if norm and norm not in seen:
                seen.add(norm)
                cleaned.append(norm)
        cfg["blocklist_ids"] = cleaned
        _state.blocklist_ids = cleaned

    if telegram_proxy is not None:
        cfg["telegram_proxy"] = telegram_proxy.strip()
        with _proxy_lock:
            global _active_proxy
            _active_proxy = _PROXY_UNSET

    _save_config_file(cfg)
    _state.blocklist_ids = list(cfg.get("blocklist_ids", []))
    out = get_config()
    if token_just_saved:
        out["save_ok"] = True
        out["message"] = (
            "Токен сохранён. Материнское ядро поднимет сервер бота "
            "(нужен доступ к api.telegram.org)."
        )
        cfg["mother_core_enabled"] = True
        _save_config_file(cfg)
        _state.status = TgTwinStatus.WAITING
        _state.last_event = "Токен сохранён — запуск сервера бота…"
        _state.error = None
        _start_mother_core_async()
    return out


# Короткий connect — мёртвый 127.0.0.1:10808 не блокирует цепочку на 25 с
_PROBE_TIMEOUT = httpx.Timeout(connect=4.0, read=12.0, write=8.0, pool=4.0)
_POLL_TIMEOUT = httpx.Timeout(connect=8.0, read=35.0, write=12.0, pool=8.0)

# Типичные порты Clash / V2Ray / Nekoray на Windows
_FALLBACK_PROXIES = (
    "socks5://127.0.0.1:10808",
    "http://127.0.0.1:10809",
    "socks5://127.0.0.1:7890",
    "http://127.0.0.1:7890",
)

_PROXY_ENV_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
)


def _normalize_proxy_url(url: str) -> str:
    """socks4 из VPN/Clash → socks5 (httpx + socksio)."""
    u = url.strip()
    low = u.lower()
    if low.startswith("socks4://"):
        return "socks5://" + u[9:]
    if low.startswith("socks://"):
        return "socks5://" + u[8:]
    return u


def _env_proxy_url() -> str | None:
    for key in _PROXY_ENV_KEYS:
        v = os.environ.get(key, "").strip()
        if v:
            return _normalize_proxy_url(v)
    return None


def _client_for_proxy(proxy: str | None, *, long_poll: bool = False) -> httpx.Client:
    timeout = _POLL_TIMEOUT if long_poll else _PROBE_TIMEOUT
    kwargs: dict = {"timeout": timeout, "trust_env": False}
    if proxy:
        return httpx.Client(proxy=_normalize_proxy_url(proxy), **kwargs)
    return httpx.Client(**kwargs)


def _proxy_attempt_chain(cfg: dict) -> list[tuple[str | None, str]]:
    """Порядок попыток: свой прокси → системный → типичные VPN → напрямую."""
    explicit = (cfg.get("telegram_proxy") or "").strip()
    if explicit.lower() in ("direct", "none", "off", "нет"):
        return [(None, "напрямую")]

    chain: list[tuple[str | None, str]] = []
    seen: set[str | None] = set()

    def add(proxy: str | None, label: str) -> None:
        key = proxy or "__direct__"
        if key in seen:
            return
        seen.add(key)
        chain.append((proxy, label))

    if explicit:
        add(_normalize_proxy_url(explicit), "ваш прокси")
    # Сразу после своего — если VPN выключен, а в поле остался 10808
    add(None, "напрямую")
    env_p = _env_proxy_url()
    if env_p:
        add(env_p, "прокси Windows/VPN")
    for url in _FALLBACK_PROXIES:
        add(url, url)
    return chain


def _set_active_proxy(proxy: str | None) -> None:
    global _active_proxy
    with _proxy_lock:
        _active_proxy = proxy


def _proxy_chain_for_requests(cfg: dict) -> list[tuple[str | None, str]]:
    """Цепочка прокси (без «залипшего» активного — иначе долгий таймаут)."""
    return _proxy_attempt_chain(cfg)


def _telegram_api_call(
    token: str,
    method: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
) -> dict:
    """Bot API с перебором прокси (getMe, getUpdates, sendMessage)."""
    cfg = _load_config_file()
    errors: list[str] = []
    url = f"https://api.telegram.org/bot{token}/{method}"
    long_poll = method == "getUpdates" and bool(params and params.get("timeout"))
    for proxy, label in _proxy_chain_for_requests(cfg):
        try:
            with _client_for_proxy(proxy, long_poll=long_poll) as client:
                if json_body is not None:
                    r = client.post(url, json=json_body)
                else:
                    r = client.get(url, params=params or {})
                data = r.json()
            if data.get("ok"):
                _set_active_proxy(proxy)
                explicit = (cfg.get("telegram_proxy") or "").strip()
                if proxy is None and explicit:
                    cfg["telegram_proxy"] = "direct"
                    _save_config_file(cfg)
                elif proxy and explicit != proxy:
                    cfg["telegram_proxy"] = proxy
                    _save_config_file(cfg)
                return data
            errors.append(f"{label}: {data.get('description', 'error')}")
        except httpx.TimeoutException:
            errors.append(f"{label}: таймаут")
        except Exception as e:
            err = str(e)
            if "10061" in err or "отверг" in err.lower():
                errors.append(f"{label}: порт закрыт (VPN выключен?)")
            else:
                errors.append(f"{label}: {err[:80]}")
    _set_active_proxy(_PROXY_UNSET)
    short = "; ".join(errors[:5])
    raise RuntimeError(
        f"{short}. "
        "Если VPN выключен — в поле прокси укажите **direct** и сохраните."
    )


def _verify_bot_token(token: str) -> tuple[bool, str | None, str | None]:
    """Проверка токена: перебор прокси, если один путь недоступен."""
    try:
        data = _telegram_api_call(token, "getMe")
        result = data.get("result") or {}
        return True, result.get("username"), None
    except Exception as e:
        return False, None, f"Нет связи с Telegram. {e}"


def _api_post(token: str, method: str, payload: dict) -> dict:
    return _telegram_api_call(token, method, json_body=payload)


def _is_blocked(user_id: int | str, username: str | None, cfg: dict) -> bool:
    blocklist = [str(x) for x in cfg.get("blocklist_ids", [])]
    uid = str(user_id)
    uname = f"@{username.lstrip('@').lower()}" if username else ""
    for entry in blocklist:
        e = entry.strip().lower()
        if e == uid or (uname and e.lstrip("@") == uname.lstrip("@")):
            return True
    return False


def _llm_for_bot(user_text: str, system_prompt: str) -> str:
    try:
        import store
        from modules.agent import generate_reply

        s = store.load_settings()
        key = (s.get("deepseek_key") or "").strip()
        model = s.get("default_model") or "deepseek-chat"
        extra = system_prompt or "Ты Telegram-бот Jarvis."
        wrapped = f"[Система: {extra}]\n\nПользователь: {user_text}"
        text, _ = generate_reply(wrapped, [], deepseek_key=key, model=model)
        return re.sub(r"\*+|`+", "", text)[:1500]
    except Exception as e:
        return f"Не могу ответить сейчас ({e})."


def _handle_message(token: str, message: dict) -> None:
    global _messages_handled
    from modules import tg_bot_logic

    cfg = _load_config_file()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    user = message.get("from") or {}
    if _is_blocked(user.get("id", ""), user.get("username"), cfg):
        return

    text = (message.get("text") or "").strip()
    entities = message.get("entities") or []
    is_cmd = bool(entities and entities[0].get("type") == "bot_command")
    command = None
    if is_cmd and text:
        command = text.split()[0].split("@")[0].lower()

    logic = tg_bot_logic.load_logic()
    reply = tg_bot_logic.resolve_reply(
        text,
        is_command=is_cmd,
        command=command,
        logic=logic,
        llm_callback=lambda t, p: _llm_for_bot(t, p),
    )
    if not reply:
        return

    result = _api_post(
        token,
        "sendMessage",
        {"chat_id": chat_id, "text": reply},
    )
    if result.get("ok"):
        _messages_handled += 1
        with _start_lock:
            _state.last_event = f"Ответ отправлен (всего {_messages_handled})"
    else:
        with _start_lock:
            _state.error = str(result.get("description", "sendMessage failed"))


def _poll_updates(token: str) -> None:
    global _update_offset
    _poll_stop.clear()
    while not _poll_stop.is_set() and _state.enabled:
        try:
            data = _telegram_api_call(
                token,
                "getUpdates",
                params={"timeout": 25, "offset": _update_offset + 1},
            )
            if not data.get("ok"):
                with _start_lock:
                    _state.error = str(data.get("description", "getUpdates"))
                _poll_stop.wait(5)
                continue
            for upd in data.get("result") or []:
                _update_offset = max(_update_offset, int(upd.get("update_id", 0)))
                msg = upd.get("message") or upd.get("edited_message")
                if msg:
                    _handle_message(token, msg)
        except Exception as e:
            with _start_lock:
                _state.last_event = f"Ошибка опроса: {e}"
                _state.error = str(e)[:400]
            _set_active_proxy(_PROXY_UNSET)
            _poll_stop.wait(5)


def _start_polling(token: str) -> None:
    global _poll_thread
    _stop_polling()
    _poll_thread = threading.Thread(
        target=_poll_updates, args=(token,), name="tg-bot-poll", daemon=True
    )
    _poll_thread.start()


def _stop_polling() -> None:
    global _poll_thread
    _poll_stop.set()
    if _poll_thread and _poll_thread.is_alive():
        _poll_thread.join(timeout=2)
    _poll_thread = None


def _connect_bot() -> None:
    global _messages_handled
    cfg = _load_config_file()
    token = (cfg.get("bot_token") or "").strip()
    if not _token_configured(token):
        _state.status = TgTwinStatus.NEED_TOKEN
        _state.enabled = False
        _state.last_event = "Укажите токен бота от BotFather"
        _state.error = None
        return

    _state.status = TgTwinStatus.WAITING
    _state.last_event = "Подключение к боту…"
    ok, username, err = _verify_bot_token(token)
    if not ok:
        _state.status = TgTwinStatus.ERROR
        _state.enabled = False
        _state.error = err
        _state.last_event = f"Токен не принят: {err}"
        return

    from modules import tg_bot_logic

    logic_name = tg_bot_logic.load_logic().get("name", "bot")
    _state.status = TgTwinStatus.ACTIVE
    _state.bot_username = username
    _messages_handled = 0
    _state.last_event = (
        f"Бот на связи (@{username}), логика: {logic_name}"
        if username
        else f"Бот на связи, логика: {logic_name}"
    )
    _state.error = None
    _start_polling(token)


def _start_mother_core_async() -> None:
    with _start_lock:
        if _state.enabled and _poll_thread and _poll_thread.is_alive():
            return
        _state.enabled = True
        cfg = _load_config_file()
        _state.blocklist_ids = [str(x) for x in cfg.get("blocklist_ids", [])]
    threading.Thread(
        target=_connect_bot, name="tg-mother-core", daemon=True
    ).start()


def bootstrap() -> None:
    """Запуск сервера бота при старте Jarvis, если токен сохранён и ядро не выключено."""
    from modules import tg_bot_logic

    tg_bot_logic.ensure_default_bot_logic()
    cfg = _load_config_file()
    token = (cfg.get("bot_token") or "").strip()
    if not _token_configured(token):
        if cfg.get("mother_core_enabled", True):
            _state.status = TgTwinStatus.NEED_TOKEN
            _state.last_event = "Укажите токен бота в материнском ядре"
        return
    if not cfg.get("mother_core_enabled", True):
        _state.status = TgTwinStatus.OFF
        return
    _start_mother_core_async()


def toggle(enabled: bool) -> dict:
    from modules import tg_bot_logic

    tg_bot_logic.ensure_default_bot_logic()
    with _start_lock:
        cfg = _load_config_file()
        cfg["mother_core_enabled"] = enabled
        _save_config_file(cfg)
        _state.blocklist_ids = [str(x) for x in cfg.get("blocklist_ids", [])]

        if not enabled:
            _state.enabled = False
            _stop_polling()
            _state.status = TgTwinStatus.OFF
            _state.last_event = "Материнское ядро остановлено"
            _state.error = None
            return to_dict()

        token = (cfg.get("bot_token") or "").strip()
        if not _token_configured(token):
            _state.enabled = False
            _state.status = TgTwinStatus.NEED_TOKEN
            _state.last_event = "Сначала сохраните токен BotFather"
            _state.error = None
            cfg["mother_core_enabled"] = False
            _save_config_file(cfg)
            return to_dict()

        _state.enabled = True
        _state.status = TgTwinStatus.WAITING
        _state.last_event = "Запуск сервера бота…"
        _state.error = None

    _start_mother_core_async()
    return to_dict()


def tick_activation() -> None:
    pass


def shutdown() -> None:
    _stop_polling()
    _state.enabled = False
    _state.status = TgTwinStatus.OFF


def send_message_outbound(chat_id: str | int, text: str) -> dict:
    """Исходящее сообщение от имени бота материнского ядра (для Qwen / API)."""
    cfg = _load_config_file()
    token = (cfg.get("bot_token") or "").strip()
    if not _token_configured(token):
        return {"ok": False, "error": "Токен бота не настроен — укажите в сайдбаре «Материнское ядро telegram»."}
    if not _state.enabled or _state.status != TgTwinStatus.ACTIVE:
        return {
            "ok": False,
            "error": f"Сервер бота не активен ({_state.status.value}). Включите тумблер в панели или ui_click telegram_server_on.",
        }
    body = (text or "").strip()
    if not body:
        return {"ok": False, "error": "Пустой текст сообщения"}
    try:
        cid: int | str = int(str(chat_id).strip())
    except ValueError:
        return {"ok": False, "error": "chat_id должен быть числом (ID чата Telegram)"}
    result = _api_post(
        token,
        "sendMessage",
        {"chat_id": cid, "text": body[:4096]},
    )
    if result.get("ok"):
        global _messages_handled
        _messages_handled += 1
        with _start_lock:
            _state.last_event = f"Исходящее от Jarvis → chat {cid} (всего {_messages_handled})"
        return {"ok": True, "message": "Сообщение отправлено через материнское ядро", "chat_id": cid}
    return {
        "ok": False,
        "error": str(result.get("description", "sendMessage failed")),
    }


def get_mother_core_status_text() -> str:
    """Текстовый снимок для Qwen — без полного bot_logic.json."""
    from modules import tg_bot_logic

    d = to_dict()
    logic_name = d.get("bot_logic_name") or "—"
    lines = [
        f"Сервер: {'ВКЛ' if d.get('enabled') else 'ВЫКЛ'} ({d.get('status_label')})",
        f"Опрос Telegram: {'активен' if d.get('polling_active') else 'нет'}",
        f"Бот: @{d.get('bot_username') or '—'}",
        f"Токен на диске: {'да' if d.get('bot_token_configured') else 'нет'}",
        f"Логика bot_logic.json: {logic_name} ({'настроена' if d.get('bot_logic_configured') else 'нет'})",
        f"Обработано входящих сообщений: {d.get('messages_handled', 0)}",
        f"Последнее событие: {d.get('last_event') or '—'}",
    ]
    if d.get("error"):
        lines.append(f"Ошибка: {d['error']}")
    bl = d.get("blocklist_ids") or []
    if bl:
        lines.append(f"Блоклист: {', '.join(bl[:8])}")
    try:
        logic = tg_bot_logic.load_logic()
        cmds = list((logic.get("commands") or {}).keys())[:6]
        if cmds:
            lines.append(f"Команды бота: {', '.join(cmds)}")
    except Exception:
        pass
    lines.append(
        "Синхронизация с чатом Jarvis: бот отвечает по bot_logic.json (команды, фразы, fallback LLM). "
        "Ты можешь отправить сообщение от имени бота через telegram_send_message (нужен chat_id)."
    )
    return "\n".join(lines)


def to_dict() -> dict:
    labels = {
        "off": "Сервер выключен",
        "waiting": "Запуск сервера…",
        "active": "Сервер бота на связи",
        "need_token": "Нужен токен бота",
        "error": "Ошибка сервера",
    }
    return {
        "enabled": _state.enabled,
        "status": _state.status.value,
        "status_label": labels.get(_state.status.value, "?"),
        "last_event": _state.last_event,
        "error": _state.error,
        "bot_username": _state.bot_username,
        "blocklist_ids": list(_state.blocklist_ids),
        "bot_token_configured": get_config()["bot_token_configured"],
        "bot_logic_configured": get_config().get("bot_logic_configured", False),
        "bot_logic_valid": get_config().get("bot_logic_valid", False),
        "bot_logic_error": get_config().get("bot_logic_error"),
        "bot_logic_name": get_config().get("bot_logic_name"),
        "messages_handled": _messages_handled,
        "polling_active": _poll_thread is not None and _poll_thread.is_alive(),
        "ready": get_config()["ready"],
    }
