"""
Google Nano Banana (Gemini Image) — генерация изображений через Gemini API.
"""

from __future__ import annotations

import base64
import re
import uuid
from pathlib import Path

import httpx

from store import DATA_DIR

IMAGES_DIR = DATA_DIR / "generated_images"
MODEL_ID = "gemini-2.5-flash-image"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent"

IMAGE_INTENT_WORDS = (
    "нарисуй",
    "нарисовать",
    "сгенерируй",
    "сгенерировать",
    "изображен",
    "картинк",
    "баннер",
    "логотип",
    "визуал",
    "макет",
    "иллюстрац",
    "фото",
    "poster",
    "banner",
    "generate image",
    "draw ",
    "[image]",
)


def key_valid(api_key: str) -> bool:
    k = (api_key or "").strip()
    return len(k) >= 20 and "•" not in k


def wants_image_generation(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in IMAGE_INTENT_WORDS)


def generate_image(api_key: str, prompt: str) -> dict:
    """Возвращает {ok, url?, filename?, error?, message?}."""
    if not key_valid(api_key):
        return {"ok": False, "error": "Не задан API-ключ Google (Nano Banana)"}

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    clean = prompt.strip()[:4000]
    if not clean:
        return {"ok": False, "error": "Пустой запрос для генерации"}

    payload = {
        "contents": [{"parts": [{"text": clean}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                API_URL,
                params={"key": api_key.strip()},
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response else str(e)
        return {"ok": False, "error": f"Gemini API: {e.response.status_code}", "detail": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    parts = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    image_b64 = None
    mime = "image/png"
    text_parts: list[str] = []
    for part in parts:
        if "inlineData" in part:
            image_b64 = part["inlineData"].get("data")
            mime = part["inlineData"].get("mimeType", mime)
        elif "text" in part:
            text_parts.append(part["text"])

    if not image_b64:
        return {
            "ok": False,
            "error": "Модель не вернула изображение",
            "detail": "\n".join(text_parts)[:500],
        }

    ext = ".png"
    if "jpeg" in mime or "jpg" in mime:
        ext = ".jpg"
    elif "webp" in mime:
        ext = ".webp"

    fname = f"nb_{uuid.uuid4().hex[:12]}{ext}"
    path = IMAGES_DIR / fname
    path.write_bytes(base64.b64decode(image_b64))

    url = f"/api/images/{fname}"
    caption = "\n".join(text_parts).strip()
    return {
        "ok": True,
        "url": url,
        "filename": fname,
        "message": "Изображение сгенерировано (Nano Banana)",
        "caption": caption,
    }


def get_image_path(filename: str) -> Path | None:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", Path(filename).name)
    if not safe:
        return None
    path = IMAGES_DIR / safe
    if path.is_file() and path.parent.resolve() == IMAGES_DIR.resolve():
        return path
    return None
