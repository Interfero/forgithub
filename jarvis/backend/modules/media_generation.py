"""
Генерация изображений и видео — выбор провайдера среди всех доступных API (ключи пользователя + встроенные).
"""

from __future__ import annotations

import base64
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import httpx

import store
from modules.nano_banana import IMAGE_INTENT_WORDS, generate_image as nb_generate_image
from modules.service_flags import ideogram_usable, nanobanana_usable, openai_usable, xai_usable

MediaKind = Literal["image", "video"]

IMAGES_DIR = store.DATA_DIR / "generated_images"
VIDEOS_DIR = store.DATA_DIR / "generated_videos"

VIDEO_INTENT_WORDS = (
    "видео",
    "video",
    "ролик",
    "анимац",
    "клип",
    "gif",
    "generate video",
    "сгенерируй видео",
    "сделай видео",
    "снимок в движен",
)


def wants_video_generation(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in VIDEO_INTENT_WORDS)


def wants_image_generation(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in IMAGE_INTENT_WORDS)


def detect_media_kind(text: str) -> MediaKind | None:
    """image | video | None."""
    if wants_video_generation(text):
        return "video"
    if wants_image_generation(text):
        return "image"
    return None


def wants_media_generation(text: str) -> bool:
    return detect_media_kind(text) is not None


@dataclass(frozen=True)
class MediaProvider:
    id: str
    label: str
    images: bool
    video: bool
    priority_image: int
    priority_video: int
    usable: Callable[[], bool]


def _settings() -> dict:
    return store.load_settings()


def _provider_specs() -> tuple[MediaProvider, ...]:
    return (
        MediaProvider(
            id="ideogram",
            label="Ideogram 3.0",
            images=True,
            video=False,
            priority_image=15,
            priority_video=999,
            usable=lambda: ideogram_usable(),
        ),
        MediaProvider(
            id="nanobanana",
            label="Google Nano Banana (Gemini)",
            images=True,
            video=False,
            priority_image=10,
            priority_video=999,
            usable=lambda: nanobanana_usable(),
        ),
        MediaProvider(
            id="openai",
            label="OpenAI DALL·E 3",
            images=True,
            video=False,
            priority_image=20,
            priority_video=999,
            usable=lambda: openai_usable(),
        ),
        MediaProvider(
            id="xai",
            label="xAI Grok Imagine",
            images=True,
            video=True,
            priority_image=30,
            priority_video=10,
            usable=lambda: xai_usable(),
        ),
    )


def list_usable_providers(*, kind: MediaKind | None = None) -> list[MediaProvider]:
    out: list[MediaProvider] = []
    for spec in _provider_specs():
        if not spec.usable():
            continue
        if kind == "image" and not spec.images:
            continue
        if kind == "video" and not spec.video:
            continue
        out.append(spec)
    if kind == "image":
        out.sort(key=lambda p: p.priority_image)
    elif kind == "video":
        out.sort(key=lambda p: p.priority_video)
    return out


def has_media_provider(kind: MediaKind) -> bool:
    return bool(list_usable_providers(kind=kind))


def pick_provider(kind: MediaKind) -> MediaProvider | None:
    providers = list_usable_providers(kind=kind)
    return providers[0] if providers else None


def media_availability_snapshot() -> dict[str, bool]:
    return {
        "image": has_media_provider("image"),
        "video": has_media_provider("video"),
        "nanobanana": nanobanana_usable(),
        "openai_image": openai_usable(),
        "xai_image": xai_usable(),
        "ideogram": ideogram_usable(),
    }


def format_media_for_router() -> str:
    img = list_usable_providers(kind="image")
    vid = list_usable_providers(kind="video")
    lines = ["Медиа-провайдеры (картинки/видео):"]
    if img:
        lines.append(
            "  Картинки: ДА — "
            + ", ".join(p.label for p in img)
            + " → можно [GEN_IMAGE]"
        )
    else:
        lines.append(
            "  Картинки: НЕТ — добавьте ключ Ideogram, Nano Banana, OpenAI или xAI в Настройках"
        )
    if vid:
        lines.append(
            "  Видео: ДА — " + ", ".join(p.label for p in vid) + " → можно [GEN_IMAGE]"
        )
    else:
        lines.append(
            "  Видео: НЕТ — нужен ключ xAI (Grok Imagine Video) в Настройках"
        )
    return "\n".join(lines)


def media_capability_reply(kind: MediaKind | None = None) -> str:
    """Подсказка, если медиа недоступно. Пустая строка — можно генерировать."""
    detected = kind or "image"
    if has_media_provider(detected):
        return ""
    lines = [
        "Шеф, **генерация медиа** в Jarvis работает через любой доступный облачный API:\n",
        "• **Картинки** — Ideogram, Nano Banana, OpenAI DALL·E или xAI Grok Imagine.",
        "• **Видео** — xAI Grok Imagine Video.",
        "• DeepSeek и Perplexity — только **текст**, не изображения.\n",
        "Добавьте и включите хотя бы один ключ в ⚙️ **Настройках**.",
    ]
    return "\n".join(lines)


def _save_bytes(data: bytes, prefix: str, ext: str, folder: Path) -> tuple[str, str]:
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
    path = folder / fname
    path.write_bytes(data)
    api_prefix = "images" if folder == IMAGES_DIR else "videos"
    return fname, f"/api/{api_prefix}/{fname}"


def _download_url(url: str, timeout: float = 120.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content


def _generate_ideogram(prompt: str) -> dict:
    from modules.ideogram import generate_image

    key = (_settings().get("ideogram_key") or "").strip()
    return generate_image(key, prompt)


def _generate_nanobanana(prompt: str) -> dict:
    key = (_settings().get("nanobanana_key") or "").strip()
    return nb_generate_image(key, prompt)


def _generate_openai_image(prompt: str) -> dict:
    key = (_settings().get("openai_key") or "").strip()
    clean = prompt.strip()[:4000]
    if not clean:
        return {"ok": False, "error": "Пустой запрос"}
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": clean,
                    "n": 1,
                    "size": "1024x1024",
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response else str(e)
        return {"ok": False, "error": f"OpenAI Images: {e.response.status_code}", "detail": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    b64 = (data.get("data") or [{}])[0].get("b64_json")
    if not b64:
        return {"ok": False, "error": "OpenAI не вернул изображение"}
    raw = base64.b64decode(b64)
    _, url = _save_bytes(raw, "oa", ".png", IMAGES_DIR)
    revised = (data.get("data") or [{}])[0].get("revised_prompt") or ""
    return {
        "ok": True,
        "url": url,
        "message": "Изображение сгенерировано (OpenAI DALL·E 3)",
        "caption": revised,
        "provider": "openai",
    }


def _generate_xai_image(prompt: str) -> dict:
    key = (_settings().get("xai_key") or "").strip()
    clean = prompt.strip()[:4000]
    try:
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                "https://api.x.ai/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-imagine-image-quality",
                    "prompt": clean,
                    "n": 1,
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response else str(e)
        return {"ok": False, "error": f"xAI Images: {e.response.status_code}", "detail": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    item = (data.get("data") or [{}])[0]
    b64 = item.get("b64_json")
    mime = item.get("mime_type") or "image/png"
    ext = ".webp" if "webp" in mime else ".jpg" if "jpeg" in mime else ".png"
    if b64:
        raw = base64.b64decode(b64)
    elif item.get("url"):
        raw = _download_url(item["url"])
    else:
        return {"ok": False, "error": "xAI не вернул изображение"}
    _, url = _save_bytes(raw, "xai", ext, IMAGES_DIR)
    return {
        "ok": True,
        "url": url,
        "message": "Изображение сгенерировано (xAI Grok Imagine)",
        "provider": "xai",
    }


def _generate_xai_video(prompt: str) -> dict:
    key = (_settings().get("xai_key") or "").strip()
    clean = prompt.strip()[:4000]
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                "https://api.x.ai/v1/videos/generations",
                headers=headers,
                json={
                    "model": "grok-imagine-video",
                    "prompt": clean,
                    "duration": 6,
                    "aspect_ratio": "16:9",
                    "resolution": "720p",
                },
            )
            resp.raise_for_status()
            request_id = resp.json().get("request_id")
            if not request_id:
                return {"ok": False, "error": "xAI Video: нет request_id"}
            deadline = time.time() + 300
            while time.time() < deadline:
                poll = client.get(
                    f"https://api.x.ai/v1/videos/{request_id}",
                    headers={"Authorization": f"Bearer {key}"},
                )
                poll.raise_for_status()
                body = poll.json()
                status = body.get("status")
                if status == "done":
                    video_url = (body.get("video") or {}).get("url")
                    if not video_url:
                        return {"ok": False, "error": "xAI Video: пустой URL"}
                    raw = _download_url(video_url, timeout=180.0)
                    _, url = _save_bytes(raw, "xai", ".mp4", VIDEOS_DIR)
                    return {
                        "ok": True,
                        "url": url,
                        "message": "Видео сгенерировано (xAI Grok Imagine Video)",
                        "provider": "xai",
                        "media_kind": "video",
                    }
                if status in ("failed", "expired"):
                    return {"ok": False, "error": f"xAI Video: {status}"}
                time.sleep(5)
            return {"ok": False, "error": "xAI Video: таймаут ожидания"}
    except httpx.HTTPStatusError as e:
        detail = e.response.text[:500] if e.response else str(e)
        return {"ok": False, "error": f"xAI Video: {e.response.status_code}", "detail": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_GENERATORS: dict[tuple[str, MediaKind], Callable[[str], dict]] = {
    ("ideogram", "image"): _generate_ideogram,
    ("nanobanana", "image"): _generate_nanobanana,
    ("openai", "image"): _generate_openai_image,
    ("xai", "image"): _generate_xai_image,
    ("xai", "video"): _generate_xai_video,
}


def generate_media(prompt: str, kind: MediaKind | None = None) -> dict:
    """Выбрать провайдера и сгенерировать медиа. Возвращает {ok, url?, error?, provider?, ...}."""
    media_kind = kind or detect_media_kind(prompt) or "image"
    provider = pick_provider(media_kind)
    if not provider:
        return {
            "ok": False,
            "error": "no_provider",
            "media_kind": media_kind,
            "hint": media_capability_reply(media_kind),
        }
    fn = _GENERATORS.get((provider.id, media_kind))
    if not fn:
        return {"ok": False, "error": f"Провайдер {provider.label} не поддерживает {media_kind}"}
    result = fn(prompt)
    if result.get("ok"):
        result.setdefault("provider", provider.id)
        result.setdefault("provider_label", provider.label)
        result.setdefault("media_kind", media_kind)
    return result


def get_video_path(filename: str) -> Path | None:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "", Path(filename).name)
    if not safe:
        return None
    path = VIDEOS_DIR / safe
    if path.is_file() and path.parent.resolve() == VIDEOS_DIR.resolve():
        return path
    return None
