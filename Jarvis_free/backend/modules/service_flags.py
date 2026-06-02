"""Включение/выключение сервисов без удаления сохранённых ключей."""

from __future__ import annotations

from store import load_settings, save_settings

ESSENTIAL_FLAGS = frozenset({"deepseek_active", "xtts_active"})

ACTIVE_DEFAULTS: dict[str, bool] = {
    "deepseek_active": True,
    "openai_active": False,
    "perplexity_active": False,
    "xai_active": False,
    "nanobanana_active": False,
    "ideogram_active": False,
    "xtts_active": True,
}

_OPTIONAL_FLAG_SPECS: tuple[tuple[str, str, str | tuple[str, ...], int], ...] = (
    ("openai_active", "openai_key", "sk-", 20),
    ("perplexity_active", "perplexity_key", "pplx-", 12),
    ("xai_active", "xai_key", ("xai-", "sk-"), 16),
)


def key_configured(key: str, prefix: str | tuple[str, ...], min_len: int = 16) -> bool:
    k = (key or "").strip()
    if not k or "•" in k or len(k) < min_len:
        return False
    if isinstance(prefix, str):
        return k.startswith(prefix)
    return any(k.startswith(p) for p in prefix)


def _nanobanana_configured(key: str) -> bool:
    from modules.nano_banana import key_valid

    return key_valid(key or "")


def _ideogram_configured(key: str) -> bool:
    from modules.ideogram import key_valid

    return key_valid(key or "")


def normalize_active_flags(settings: dict) -> dict:
    """Активны: DeepSeek/XTTS по умолчанию; прочие API — только при сохранённом ключе."""
    s = dict(settings)

    for flag in ESSENTIAL_FLAGS:
        if flag not in s:
            s[flag] = ACTIVE_DEFAULTS[flag]

    for flag, key_field, prefix, min_len in _OPTIONAL_FLAG_SPECS:
        configured = key_configured(s.get(key_field, ""), prefix, min_len)
        if not configured:
            s[flag] = False
        elif flag not in s:
            s[flag] = True

    if not _nanobanana_configured(s.get("nanobanana_key", "")):
        s["nanobanana_active"] = False
    elif "nanobanana_active" not in s:
        s["nanobanana_active"] = True

    if not _ideogram_configured(s.get("ideogram_key", "")):
        s["ideogram_active"] = False
    elif "ideogram_active" not in s:
        s["ideogram_active"] = True

    return s


def apply_active_flags_on_settings_save(before: dict, after: dict) -> dict:
    """После сохранения ключей: новый токен → включить; удалённый → выключить (кроме ядра)."""
    s = normalize_active_flags(after)

    for flag, key_field, prefix, min_len in _OPTIONAL_FLAG_SPECS:
        now_cfg = key_configured(s.get(key_field, ""), prefix, min_len)
        was_cfg = key_configured(before.get(key_field, ""), prefix, min_len)
        if not now_cfg:
            s[flag] = False
        elif now_cfg and not was_cfg:
            s[flag] = True

    nb_now = _nanobanana_configured(s.get("nanobanana_key", ""))
    nb_was = _nanobanana_configured(before.get("nanobanana_key", ""))
    if not nb_now:
        s["nanobanana_active"] = False
    elif nb_now and not nb_was:
        s["nanobanana_active"] = True

    id_now = _ideogram_configured(s.get("ideogram_key", ""))
    id_was = _ideogram_configured(before.get("ideogram_key", ""))
    if not id_now:
        s["ideogram_active"] = False
    elif id_now and not id_was:
        s["ideogram_active"] = True

    return s


def service_flag_has_credentials(flag: str, settings: dict | None = None) -> bool:
    """Можно ли включить тумблер (для опциональных API нужен ключ)."""
    if flag in ESSENTIAL_FLAGS:
        return True
    s = settings if settings is not None else load_settings()
    if flag == "openai_active":
        return key_configured(s.get("openai_key", ""), "sk-", 20)
    if flag == "perplexity_active":
        return key_configured(s.get("perplexity_key", ""), "pplx-", 12)
    if flag == "xai_active":
        return key_configured(s.get("xai_key", ""), ("xai-", "sk-"), 16)
    if flag == "nanobanana_active":
        return _nanobanana_configured(s.get("nanobanana_key", ""))
    if flag == "ideogram_active":
        return _ideogram_configured(s.get("ideogram_key", ""))
    return False


def is_active(flag: str, default: bool | None = None) -> bool:
    s = load_settings()
    if default is None:
        default = ACTIVE_DEFAULTS.get(flag, False)
    return bool(s.get(flag, default))


def set_active(flag: str, enabled: bool) -> bool:
    if enabled and flag not in ESSENTIAL_FLAGS and not service_flag_has_credentials(flag):
        enabled = False
    save_settings({flag: bool(enabled)})
    return is_active(flag)


def deepseek_usable(key: str | None = None) -> bool:
    s = load_settings()
    k = (key if key is not None else s.get("deepseek_key", "")) or ""
    return key_configured(k, "sk-", 20) and is_active("deepseek_active")


def openai_usable(key: str | None = None) -> bool:
    s = load_settings()
    k = (key if key is not None else s.get("openai_key", "")) or ""
    return key_configured(k, "sk-", 20) and is_active("openai_active")


def perplexity_usable(key: str | None = None) -> bool:
    s = load_settings()
    k = (key if key is not None else s.get("perplexity_key", "")) or ""
    return key_configured(k, "pplx-", 12) and is_active("perplexity_active")


def xai_usable(key: str | None = None) -> bool:
    s = load_settings()
    k = (key if key is not None else s.get("xai_key", "")) or ""
    return key_configured(k, ("xai-", "sk-"), 16) and is_active("xai_active")


def nanobanana_usable(key: str | None = None) -> bool:
    s = load_settings()
    k = (key if key is not None else s.get("nanobanana_key", "")) or ""
    return _nanobanana_configured(k) and is_active("nanobanana_active")


def ideogram_usable(key: str | None = None) -> bool:
    s = load_settings()
    k = (key if key is not None else s.get("ideogram_key", "")) or ""
    return _ideogram_configured(k) and is_active("ideogram_active")


def xtts_service_enabled() -> bool:
    return is_active("xtts_active")


def service_flags_payload(settings: dict | None = None) -> dict:
    """Для /api/settings и /api/status."""
    s = normalize_active_flags(settings if settings is not None else load_settings())
    ds_key = s.get("deepseek_key", "")
    oa_key = s.get("openai_key", "")
    pp_key = s.get("perplexity_key", "")
    xa_key = s.get("xai_key", "")
    nb_key = s.get("nanobanana_key", "")
    id_key = s.get("ideogram_key", "")
    oa_active = key_configured(oa_key, "sk-", 20) and bool(s.get("openai_active", False))
    xa_active = key_configured(xa_key, ("xai-", "sk-"), 16) and bool(s.get("xai_active", False))
    nb_active = _nanobanana_configured(nb_key) and bool(s.get("nanobanana_active", False))
    id_active = _ideogram_configured(id_key) and bool(s.get("ideogram_active", False))
    return {
        "deepseek_configured": key_configured(ds_key, "sk-", 20),
        "deepseek_active": bool(s.get("deepseek_active", True)),
        "deepseek_usable": key_configured(ds_key, "sk-", 20) and bool(s.get("deepseek_active", True)),
        "openai_configured": key_configured(oa_key, "sk-", 20),
        "openai_active": bool(s.get("openai_active", False)),
        "openai_usable": key_configured(oa_key, "sk-", 20) and bool(s.get("openai_active", False)),
        "perplexity_configured": key_configured(pp_key, "pplx-", 12),
        "perplexity_active": bool(s.get("perplexity_active", False)),
        "perplexity_usable": key_configured(pp_key, "pplx-", 12)
        and bool(s.get("perplexity_active", False)),
        "xai_configured": key_configured(xa_key, ("xai-", "sk-"), 16),
        "xai_active": bool(s.get("xai_active", False)),
        "xai_usable": key_configured(xa_key, ("xai-", "sk-"), 16) and bool(s.get("xai_active", False)),
        "nanobanana_configured": _nanobanana_configured(nb_key),
        "nanobanana_active": bool(s.get("nanobanana_active", False)),
        "nanobanana_usable": _nanobanana_configured(nb_key) and bool(s.get("nanobanana_active", False)),
        "ideogram_configured": _ideogram_configured(id_key),
        "ideogram_active": bool(s.get("ideogram_active", False)),
        "ideogram_usable": id_active,
        "media_image_ready": any([nb_active, oa_active, id_active, xa_active]),
        "media_video_ready": xa_active,
        "xtts_active": bool(s.get("xtts_active", True)),
    }
