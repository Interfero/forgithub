"""
Управление элементами интерфейса Jarvis из бэкенда / Qwen: поля Telegram, Авито, кнопки.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Поля → id для фронтенда
TELEGRAM_FIELDS = {
    "bot_token": "Токен бота (BotFather)",
    "telegram_proxy": "Прокси для Telegram (если без VPN не подключается)",
    "bot_logic": "Логика бота (bot_logic.json)",
}

AVITO_FIELDS = {
    "client_id": "Client ID (из developers.avito.ru)",
    "client_secret": "Client Secret",
    "user_id": "User ID (номер профиля Авито, можно пусто — подставится сам)",
}

_BOT_TOKEN_RE = re.compile(r"\b(\d{8,12}:[A-Za-z0-9_-]{20,})\b")
_PROXY_RE = re.compile(r"(socks5|socks4|http|https)://[^\s\"']+", re.I)
_CLIENT_ID_RE = re.compile(
    r"(?:client[_\s-]?id|clientid)\s*[:=]\s*['\"]?([A-Za-z0-9_-]{8,})['\"]?",
    re.I,
)
_CLIENT_SECRET_RE = re.compile(
    r"(?:client[_\s-]?secret|secret)\s*[:=]\s*['\"]?([A-Za-z0-9_-]{8,})['\"]?",
    re.I,
)
_USER_ID_RE = re.compile(
    r"(?:user[_\s-]?id|userid|профил)\s*[:=]\s*['\"]?(\d{5,12})['\"]?",
    re.I,
)


def queue_ui_command(cmd: dict[str, Any]) -> None:
    from modules.agent import get_runtime

    get_runtime().pending_ui_commands.append(cmd)


def drain_ui_commands() -> list[dict[str, Any]]:
    from modules.agent import get_runtime

    rt = get_runtime()
    cmds = list(rt.pending_ui_commands)
    rt.pending_ui_commands = []
    return cmds


def get_telegram_fields_snapshot() -> dict[str, Any]:
    from modules import tg_bot_logic
    from modules import tg_twin

    cfg = tg_twin.get_config()
    logic_text = ""
    if cfg.get("bot_logic_configured"):
        try:
            logic_text = json.dumps(tg_bot_logic.load_logic(), ensure_ascii=False, indent=2)
            if len(logic_text) > 2000:
                logic_text = logic_text[:2000] + "\n…"
        except Exception as e:
            logic_text = f"(ошибка чтения: {e})"
    else:
        logic_text = "(файл не настроен — пример по кнопке «Пример» в панели)"

    return {
        "bot_token": {
            "label": TELEGRAM_FIELDS["bot_token"],
            "configured": bool(cfg.get("bot_token_configured")),
            "display": cfg.get("bot_token") or "(не задан — введите в поле в сайдбаре)",
            "draft_hint": "Поле ввода пусто после сохранения; на диске токен есть" if cfg.get("bot_token_configured") else "",
        },
        "telegram_proxy": {
            "label": TELEGRAM_FIELDS["telegram_proxy"],
            "value": cfg.get("telegram_proxy") or "",
        },
        "bot_logic": {
            "label": TELEGRAM_FIELDS["bot_logic"],
            "configured": bool(cfg.get("bot_logic_configured")),
            "preview": logic_text,
        },
        "server": tg_twin.to_dict(),
    }


def get_avito_fields_snapshot() -> dict[str, Any]:
    from modules import avito as avito_module

    cfg = avito_module.get_config()
    st = avito_module.to_dict()
    return {
        "client_id": {
            "label": AVITO_FIELDS["client_id"],
            "configured": bool(cfg.get("client_id_configured")),
            "display": cfg.get("client_id") or "(не задан)",
        },
        "client_secret": {
            "label": AVITO_FIELDS["client_secret"],
            "configured": bool(cfg.get("client_secret_configured")),
            "display": "(сохранён на сервере)" if cfg.get("client_secret_configured") else "(не задан)",
        },
        "user_id": {
            "label": AVITO_FIELDS["user_id"],
            "value": cfg.get("user_id") or st.get("user_id") or "",
        },
        "sync": {
            "enabled": bool(st.get("enabled")),
            "status_label": st.get("status_label"),
            "last_sync_date": st.get("last_sync_date"),
        },
    }


def get_app_indicators_snapshot() -> dict[str, Any]:
    from modules import avito as avito_module
    from modules import local_qwen as lq
    from modules import tg_twin
    from modules.agent import get_runtime
    from modules.neural_keys import get_neural_availability

    rt = get_runtime()
    keys = get_neural_availability()
    qwen = lq.get_qwen_status()
    return {
        "agent_status": rt.status,
        "mode": rt.mode.value,
        "deepseek_configured": keys.get("deepseek"),
        "nanobanana_configured": keys.get("nanobanana"),
        "qwen": {
            "label": qwen.get("label"),
            "ready": qwen.get("ready"),
            "value": qwen.get("value"),
        },
        "telegram_mother_core": tg_twin.to_dict(),
        "avito_connector": avito_module.to_dict(),
        "voice_listening": rt.voice_enabled,
        "chat_speech": rt.chat_speech_enabled,
    }


def get_avito_connector_status_text() -> str:
    """Снимок коннектора Авито для Qwen."""
    from modules import avito as avito_module

    av = avito_module.to_dict()
    cfg = avito_module.get_config()
    lines = [
        f"Синхронизация: {'ВКЛ' if av.get('enabled') else 'ВЫКЛ'} ({av.get('status_label')})",
        f"Ключи API: {'загружены' if av.get('client_id_configured') and av.get('client_secret_configured') else 'нет'}",
        f"User ID: {cfg.get('user_id') or av.get('user_id') or '(подставится автоматически)'}",
        f"Последняя синхронизация: {av.get('last_sync_date') or '—'}",
        f"Объявлений в последней выгрузке: {av.get('items_synced', 0)}",
        f"Последнее событие: {av.get('last_event') or '—'}",
    ]
    if av.get("error"):
        lines.append(f"Ошибка: {av['error']}")
    lines.append(
        "Метрики хранятся в SQLite (таблица avito_stats). Читай: get_stored_metrics; "
        "обновить с API: fetch_and_save_avito_metrics."
    )
    return "\n".join(lines)


def get_connectors_live_context() -> str:
    """
    Живой контекст панелей сайдбара — всегда в системном промпте Qwen/LLM.
    Чтобы модель «видела» материнское ядро и Авито без вызова инструмента.
    """
    from modules import tg_twin

    tg_txt = tg_twin.get_mother_core_status_text()
    av_txt = get_avito_connector_status_text()
    return (
        "---\n"
        "[Панели сайдбара — LIVE, обновляется каждый запрос]\n"
        "Обе панели в **левом сайдбаре** приложения Jarvis (над списком чатов), раскрываются кликом.\n\n"
        "**1) Материнское ядро telegram** — ваш BotFather-бот: токен, прокси, bot_logic.json, "
        "тумблер «Сервер бота». Входящие в Telegram обрабатывает этот же процесс (polling).\n"
        f"{tg_txt}\n\n"
        "**2) Коннектор Авито** — Client ID/Secret, User ID, тумблер ежедневной синхронизации, SQLite-метрики.\n"
        f"{av_txt}\n\n"
        "**Как управлять (JSON-инструменты):**\n"
        "• ui_get_app_state — поля ввода и индикаторы\n"
        "• ui_set_telegram_field / ui_set_avito_field — записать в поля сайдбара\n"
        "• ui_apply_text_to_connectors — ключи из текста пользователя\n"
        "• ui_click — expand_telegram, expand_avito, telegram_server_on/off, avito_sync_on/off\n"
        "• telegram_mother_core_status — детальный статус ТГ-бота\n"
        "• telegram_send_message — отправить сообщение от бота (chat_id, text)\n"
        "• get_stored_metrics / fetch_and_save_avito_metrics — аналитика Авито\n"
    )


def get_ui_snapshot() -> str:
    tg = get_telegram_fields_snapshot()
    av = get_avito_fields_snapshot()
    ind = get_app_indicators_snapshot()
    lines = [
        "=== Индикаторы приложения ===",
        f"Режим чата: {ind['mode']}, статус агента: {ind['agent_status']}",
        f"DeepSeek ключ: {'да' if ind['deepseek_configured'] else 'нет'}",
        f"Nano Banana ключ: {'да' if ind['nanobanana_configured'] else 'нет'}",
        f"Qwen 2.5 14B: {ind['qwen'].get('value')} (ready={ind['qwen'].get('ready')})",
        f"Telegram ядро: {ind['telegram_mother_core'].get('status_label')} "
        f"(сервер {'вкл' if ind['telegram_mother_core'].get('enabled') else 'выкл'})",
        f"Авито: {ind['avito_connector'].get('status_label')} "
        f"(синхр. {'вкл' if ind['avito_connector'].get('enabled') else 'выкл'})",
        "",
        "=== Материнское ядро Telegram (поля ввода) ===",
        f"• {tg['bot_token']['label']}: {tg['bot_token']['display']}",
        f"• {tg['telegram_proxy']['label']}: {tg['telegram_proxy']['value'] or '(пусто)'}",
        f"• {tg['bot_logic']['label']}: {'настроен' if tg['bot_logic']['configured'] else 'нет'}",
        "",
        "=== Коннектор Авито (поля ввода) ===",
        f"• {av['client_id']['label']}: {av['client_id']['display']}",
        f"• {av['client_secret']['label']}: {av['client_secret']['display']}",
        f"• {av['user_id']['label']}: {av['user_id']['value'] or '(пусто — подставится автоматически)'}",
    ]
    return "\n".join(lines)


def set_telegram_field(field: str, value: str, *, persist: bool = True) -> str:
    field = (field or "").strip().lower().replace(" ", "_")
    from modules import tg_bot_logic
    from modules import tg_twin

    queue_ui_command({"action": "expand_panel", "panel": "telegram"})
    queue_ui_command({"action": "set_field", "target": "telegram", "field": field, "value": value})

    if field in ("bot_token", "token", "токен"):
        if persist and value.strip() and "•" not in value:
            res = tg_twin.save_config(bot_token=value.strip())
            return f"Токен бота: {res.get('message', 'сохранён')}"
        return "Токен подставлен в поле «Токен бота (BotFather)» в сайдбаре — нажмите «Сохранить токен»."

    if field in ("telegram_proxy", "proxy", "прокси"):
        if persist:
            tg_twin.save_config(telegram_proxy=value.strip())
            return f"Прокси сохранён: {value.strip() or '(пусто / direct)'}"
        return "Прокси подставлен в поле — нажмите «Сохранить прокси»."

    if field in ("bot_logic", "logic", "логика"):
        try:
            parsed = json.loads(value) if value.strip().startswith("{") else value
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
        except json.JSONDecodeError as e:
            return f"Ошибка JSON логики: {e}"
        if persist:
            r = tg_bot_logic.save_logic(parsed)
            return f"Логика бота сохранена: {r.get('message', 'ok')}"
        return "JSON логики подставлен в поле — нажмите «Сохранить логику»."

    return f"Неизвестное поле Telegram: {field}. Допустимо: bot_token, telegram_proxy, bot_logic"


def set_avito_field(field: str, value: str, *, persist: bool = True) -> str:
    field = (field or "").strip().lower().replace(" ", "_")
    from modules import avito as avito_module

    queue_ui_command({"action": "expand_panel", "panel": "avito"})
    queue_ui_command({"action": "set_field", "target": "avito", "field": field, "value": value})

    kwargs: dict[str, Any] = {}
    if field in ("client_id", "clientid"):
        kwargs["client_id"] = value.strip()
    elif field in ("client_secret", "secret"):
        kwargs["client_secret"] = value.strip()
    elif field in ("user_id", "userid"):
        kwargs["user_id"] = value.strip()
    else:
        return f"Неизвестное поле Авито: {field}. Допустимо: client_id, client_secret, user_id"

    if persist and any(kwargs.get(k) for k in kwargs):
        res = avito_module.save_config(**kwargs)
        return res.get("message", "Настройки Авито сохранены на сервере")
    return "Значения подставлены в поля коннектора Авито — нажмите «Сохранить ключи»."


def parse_and_apply_credentials(text: str, *, persist: bool = True) -> str:
    """Извлечь токены/ключи из произвольного текста пользователя."""
    applied: list[str] = []
    t = text or ""

    m = _BOT_TOKEN_RE.search(t)
    if m:
        applied.append(set_telegram_field("bot_token", m.group(1), persist=persist))

    m = _PROXY_RE.search(t)
    if m:
        applied.append(set_telegram_field("telegram_proxy", m.group(0), persist=persist))

    cid = _CLIENT_ID_RE.search(t)
    csec = _CLIENT_SECRET_RE.search(t)
    uid = _USER_ID_RE.search(t)
    if cid or csec or uid:
        if cid:
            applied.append(set_avito_field("client_id", cid.group(1), persist=persist))
        if csec:
            applied.append(set_avito_field("client_secret", csec.group(1), persist=persist))
        if uid:
            applied.append(set_avito_field("user_id", uid.group(1), persist=persist))
    elif "avito" in t.lower() or "авито" in t.lower():
        # пары строк ClientID\nSecret без меток
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        alnum = [ln for ln in lines if re.match(r"^[A-Za-z0-9_-]{8,}$", ln)]
        if len(alnum) >= 2:
            applied.append(set_avito_field("client_id", alnum[0], persist=persist))
            applied.append(set_avito_field("client_secret", alnum[1], persist=persist))

    if not applied:
        return "Не удалось извлечь токены из текста. Укажите явно: BotFather токен, Client ID/Secret Авито."
    queue_ui_command({"action": "refresh_status"})
    return "Применено:\n" + "\n".join(f"• {a}" for a in applied)


def execute_ui_click(action: str) -> str:
    action = (action or "").strip().lower()
    from modules import avito as avito_module
    from modules import tg_twin

    if action in ("open_settings", "settings", "настройки"):
        section = "general"
        queue_ui_command({"action": "open_settings", "section": section})
        return "Открыты полноэкранные Настройки."

    if action in ("open_settings_deepseek", "settings_deepseek"):
        queue_ui_command({"action": "open_settings", "section": "deepseek"})
        return "Открыты Настройки — раздел DeepSeek."

    if action in ("open_settings_nanobanana", "settings_nanobanana", "settings_google"):
        queue_ui_command({"action": "open_settings", "section": "nanobanana"})
        return "Открыты Настройки — раздел Google Nano Banana."

    if action in ("expand_telegram", "telegram_panel", "telegram"):
        queue_ui_command({"action": "expand_panel", "panel": "telegram"})
        return "Развёрнута панель «Материнское ядро telegram»."

    if action in ("expand_avito", "avito_panel", "avito"):
        queue_ui_command({"action": "expand_panel", "panel": "avito"})
        return "Развёрнута панель «Коннектор Авито»."

    if action in ("telegram_server_on", "telegram_toggle_on"):
        queue_ui_command({"action": "click", "target": "telegram", "control": "server_toggle", "on": True})
        r = tg_twin.toggle(True)
        return f"Сервер Telegram: {r.get('status_label', 'переключено')}"

    if action in ("telegram_server_off", "telegram_toggle_off"):
        queue_ui_command({"action": "click", "target": "telegram", "control": "server_toggle", "on": False})
        r = tg_twin.toggle(False)
        return f"Сервер Telegram: {r.get('status_label', 'переключено')}"

    if action in ("avito_sync_on", "avito_toggle_on"):
        queue_ui_command({"action": "click", "target": "avito", "control": "sync_toggle", "on": True})
        r = avito_module.toggle(True)
        return f"Синхронизация Авито: {r.get('status_label', 'переключено')}"

    if action in ("avito_sync_off", "avito_toggle_off"):
        queue_ui_command({"action": "click", "target": "avito", "control": "sync_toggle", "on": False})
        r = avito_module.toggle(False)
        return f"Синхронизация Авито: {r.get('status_label', 'переключено')}"

    if action in ("collapse_indicators", "toggle_indicators"):
        queue_ui_command({"action": "click", "target": "app", "control": "indicators_toggle"})
        return "Переключена панель индикации."

    _mode_actions = {
        "mode_standard": "standard",
        "mode_accountant": "accountant",
        "mode_marketer": "marketer",
        "mode_developer": "developer",
        "standard_mode": "standard",
        "developer_mode": "developer",
    }
    if action in _mode_actions:
        from modules.agent import AgentMode
        from modules.mode_switch import apply_chat_mode

        mode = AgentMode(_mode_actions[action])
        ok, msg = apply_chat_mode(mode)
        return msg

    return (
        f"Неизвестное действие UI: {action}. "
        "Доступно: open_settings, expand_telegram, expand_avito, telegram_server_on/off, avito_sync_on/off, "
        "mode_developer, mode_standard, mode_accountant, mode_marketer"
    )
