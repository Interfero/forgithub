"""
Доступность внешних нейросетей по сохранённым API-ключам (для роутера Qwen и режимов чата).
"""

from __future__ import annotations

import store
from modules.media_generation import media_availability_snapshot, nanobanana_usable
from modules.nano_banana import key_valid as nanobanana_key_valid
from modules.service_flags import openai_usable, xai_usable


def _deepseek_key_valid(key: str) -> bool:
    k = (key or "").strip()
    return k.startswith("sk-") and len(k) >= 20


def get_neural_availability() -> dict[str, bool]:
    s = store.load_settings()
    media = media_availability_snapshot()
    return {
        "deepseek": _deepseek_key_valid(s.get("deepseek_key") or ""),
        "nanobanana": nanobanana_key_valid(s.get("nanobanana_key") or ""),
        "openai": openai_usable(),
        "perplexity": bool((s.get("perplexity_key") or "").strip().startswith("pplx-")),
        "xai": xai_usable(),
        "media_image": media["image"],
        "media_video": media["video"],
        "ideogram": bool((s.get("ideogram_key") or "").strip()),
    }


def format_availability_for_router() -> str:
    from modules.media_generation import format_media_for_router

    a = get_neural_availability()
    lines = [
        "DeepSeek: "
        + (
            "ДА (только ТЕКСТ: бухгалтерия, юридика, код; НЕ картинки/видео)"
            if a["deepseek"]
            else "НЕТ — не выбирай [COMPLEX_TEXT] для юридики; подскажи ключ sk-… в Настройках"
        ),
        "Perplexity: "
        + (
            "ДА (текст, поиск; режим «Разработчик»)"
            if a["perplexity"]
            else "НЕТ — для режима «Разработчик» подскажи ключ pplx-… в Настройках"
        ),
        format_media_for_router(),
    ]
    if a["openai"] and not a["media_image"]:
        lines.append("OpenAI: ДА (текст; для картинок включите сервис в Настройках)")
    elif a["openai"]:
        lines.append("OpenAI: ДА (текст + DALL·E 3 при включённом сервисе)")
    if a["xai"]:
        lines.append(
            "xAI Grok: ДА"
            + (" (Imagine: картинки и видео)" if a["media_image"] or a["media_video"] else " (включите сервис)")
        )
    if a["nanobanana"] and nanobanana_usable():
        lines.append("Google Nano Banana: ДА (картинки через Gemini)")
    elif a["nanobanana"]:
        lines.append("Google Nano Banana: ключ есть, сервис выключен в Настройках")
    from modules.service_flags import ideogram_usable

    if ideogram_usable():
        lines.append("Ideogram: ДА (картинки ideogram.ai)")
    elif a.get("ideogram") or (store.load_settings().get("ideogram_key") or "").strip():
        lines.append("Ideogram: ключ есть, сервис выключен в Настройках")
    return "\n".join(lines)


def neural_stack_summary_for_user() -> str:
    """Фактический ответ Шефу: какие модели и API сейчас доступны Jarvis."""
    from modules import local_qwen as lq
    from modules.service_flags import deepseek_usable, ideogram_usable

    a = get_neural_availability()
    s = store.load_settings()
    lines: list[str] = [
        "**Как Jarvis генерирует ответы**",
        "",
        "Я — **Jarvis** на вашем ПК, не ChatGPT и не Claude. Текст в чате собирает **роутер**:",
    ]

    if lq.qwen_available():
        lines.append(
            "• **Qwen 2.5 14B** (локально, Ollama/файл в Jarvis) — обычный диалог, инструменты, UI."
        )
    else:
        lines.append(
            "• **Qwen 2.5 14B** — файла модели пока нет; запустите **install-qwen.bat** или **start.bat**."
        )

    if deepseek_usable():
        lines.append("• **DeepSeek** (облако) — бухгалтерия, юридика, сложный текст.")
    elif a["deepseek"]:
        lines.append("• **DeepSeek** — ключ есть, включите сервис в ⚙️ Настройках.")
    else:
        lines.append("• **DeepSeek** — нет ключа (`sk-…` в Настройках).")

    if a["perplexity"]:
        lines.append("• **Perplexity** — режим «Разработчик», поиск и код.")
    else:
        lines.append("• **Perplexity** — нет ключа (`pplx-…`) для режима разработчика.")

    media_parts: list[str] = []
    if ideogram_usable():
        media_parts.append("Ideogram")
    if a["nanobanana"] and nanobanana_usable():
        media_parts.append("Nano Banana")
    if a["openai"] and openai_usable():
        media_parts.append("OpenAI DALL·E")
    if a["xai"] and xai_usable():
        media_parts.append("xAI Grok Imagine")

    if media_parts:
        lines.append(
            f"• **Картинки/видео** — медиа-роутер: {', '.join(media_parts)} (что включено в Настройках)."
        )
    elif a.get("media_image") or a.get("media_video") or (s.get("ideogram_key") or "").strip():
        lines.append("• **Картинки/видео** — ключи есть, включите тумблеры медиа-сервисов в ⚙️ Настройках.")
    else:
        lines.append(
            "• **Картинки/видео** — добавьте Ideogram / Nano Banana / OpenAI / xAI в ⚙️ Настройках."
        )

    lines.extend(
        [
            "",
            "Режим чата (стандарт / бухгалтер / маркетолог / разработчик) выбирается **автоматически** по задаче.",
            "Спросите «нарисуй …» или про Авито — отвечу по делу, без выдуманных «я Anthropic».",
        ]
    )
    return "\n".join(lines)
