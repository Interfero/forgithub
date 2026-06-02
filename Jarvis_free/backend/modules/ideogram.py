"""
Ideogram 3.0 — генерация изображений (api.ideogram.ai).
"""

from __future__ import annotations

import uuid

import httpx

from store import DATA_DIR

IMAGES_DIR = DATA_DIR / "generated_images"
API_URL = "https://api.ideogram.ai/v1/ideogram-v3/generate"


def key_valid(api_key: str) -> bool:
    k = (api_key or "").strip()
    return len(k) >= 16 and "•" not in k


def generate_image(api_key: str, prompt: str) -> dict:
    """Возвращает {ok, url?, error?, message?, provider?, caption?}."""
    if not key_valid(api_key):
        return {"ok": False, "error": "Не задан API-ключ Ideogram"}

    clean = (prompt or "").strip()[:4000]
    if not clean:
        return {"ok": False, "error": "Пустой запрос для генерации"}

    try:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                API_URL,
                headers={"Api-Key": api_key.strip()},
                data={
                    "prompt": clean,
                    "rendering_speed": "TURBO",
                    "aspect_ratio": "1:1",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response else str(e)
        return {
            "ok": False,
            "error": f"Ideogram API: {e.response.status_code}",
            "detail": detail,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

    items = data.get("data") or []
    if not items:
        return {"ok": False, "error": "Ideogram не вернул изображение"}

    item = items[0]
    if item.get("is_image_safe") is False:
        return {"ok": False, "error": "Ideogram: запрос не прошёл проверку безопасности"}

    remote_url = item.get("url")
    if not remote_url:
        return {"ok": False, "error": "Ideogram: пустой URL изображения"}

    try:
        raw = _download_url(remote_url, timeout=120.0)
    except Exception as e:
        return {"ok": False, "error": f"Не удалось скачать изображение: {e}"}

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"ido_{uuid.uuid4().hex[:12]}.png"
    path = IMAGES_DIR / fname
    path.write_bytes(raw)
    url = f"/api/images/{fname}"
    return {
        "ok": True,
        "url": url,
        "message": "Изображение сгенерировано (Ideogram 3.0)",
        "provider": "ideogram",
        "provider_label": "Ideogram 3.0",
        "caption": "",
    }


def _download_url(url: str, timeout: float = 120.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content
