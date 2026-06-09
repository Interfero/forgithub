"""
Лёгкая обработка изображений для текстового чата Jarvis (уровень MS Paint).
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
CHAT_IMAGES_DIR = user_data_dir() / "files" / "chat_images"


def _ensure_dir() -> Path:
    CHAT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return CHAT_IMAGES_DIR


def _safe_id(image_id: str) -> str:
    sid = (image_id or "").strip()
    if not sid or ".." in sid or "/" in sid or "\\" in sid:
        raise ValueError("Некорректный id изображения")
    return sid


def image_path(image_id: str) -> Path:
    return _ensure_dir() / f"{_safe_id(image_id)}.png"


def public_url(image_id: str) -> str:
    return f"/api/chat-images/{_safe_id(image_id)}"


def resolve_chat_image_path(image_id: str, *, ext_hint: str | None = None) -> Path:
    sid = _safe_id(image_id)
    base = _ensure_dir()
    if ext_hint:
        p = base / f"{sid}.{ext_hint.lstrip('.')}"
        if p.is_file():
            return p
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        p = base / f"{sid}{suffix}"
        if p.is_file():
            return p
    legacy = base / f"{sid}.png"
    if legacy.is_file():
        return legacy
    raise FileNotFoundError("Изображение не найдено")


def markdown_embed(image_id: str, *, alt: str = "результат") -> str:
    return f"![{alt}]({public_url(image_id)})"


def save_chat_image(data: bytes, filename: str) -> dict[str, Any]:
    from PIL import Image

    if not data:
        raise ValueError("Пустой файл")
    if len(data) > 15 * 1024 * 1024:
        raise ValueError("Максимум 15 МБ на изображение")

    _ensure_dir()
    image_id = uuid.uuid4().hex[:12]
    out = image_path(image_id)

    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGBA")
        im.save(out, format="PNG")

    analysis = analyze_image_file(out, original_name=filename)
    return {
        "id": image_id,
        "url": public_url(image_id),
        "filename": filename,
        "width": analysis["width"],
        "height": analysis["height"],
        "format": "png",
        "analysis": analysis["summary"],
        "markdown": markdown_embed(image_id, alt=Path(filename).stem or "изображение"),
    }


def analyze_image_file(path: Path, *, original_name: str = "") -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as im:
        w, h = im.size
        mode = im.mode
        fmt = (im.format or "PNG").upper()
        has_alpha = mode in ("RGBA", "LA") or ("transparency" in im.info)

    name = original_name or path.name
    summary = (
        f"Изображение «{name}»: {w}×{h} px, формат {fmt}, "
        f"{'с прозрачностью' if has_alpha else 'без прозрачности'}."
    )
    return {
        "width": w,
        "height": h,
        "format": fmt,
        "has_alpha": has_alpha,
        "summary": summary,
    }


def load_image(image_id: str):
    from PIL import Image

    path = resolve_chat_image_path(image_id)
    return Image.open(path).convert("RGBA"), path


def crop_image(image_id: str, *, left: int, top: int, right: int, bottom: int) -> dict[str, Any]:
    from PIL import Image

    im, _ = load_image(image_id)
    w, h = im.size
    l = max(0, min(left, w - 1))
    t = max(0, min(top, h - 1))
    r = max(l + 1, min(right, w))
    b = max(t + 1, min(bottom, h))
    cropped = im.crop((l, t, r, b))
    return _save_result(cropped, note=f"crop {l},{t},{r},{b}")


def convert_format(image_id: str, *, target: str = "png") -> dict[str, Any]:
    from PIL import Image

    tgt = (target or "png").lower().lstrip(".")
    if tgt not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("Формат: png, jpg, webp")
    im, _ = load_image(image_id)
    if tgt in {"jpg", "jpeg"}:
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    return _save_result(im, note=f"format {tgt}", save_format=tgt.upper() if tgt != "jpg" else "JPEG")


def set_transparency(image_id: str, *, mode: str = "remove") -> dict[str, Any]:
    from PIL import Image

    im, _ = load_image(image_id)
    m = (mode or "remove").lower()
    if m == "remove":
        im = _remove_light_background(im)
    elif m == "add":
        im = _flatten_white(im)
    else:
        raise ValueError("mode: remove | add")
    return _save_result(im, note=f"transparency {m}")


def _remove_light_background(im):
    from PIL import Image

    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= 245 and g >= 245 and b >= 245:
                px[x, y] = (r, g, b, 0)
    return im


def _flatten_white(im):
    from PIL import Image

    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def _save_result(im, *, note: str, save_format: str = "PNG") -> dict[str, Any]:
    _ensure_dir()
    new_id = uuid.uuid4().hex[:12]
    out = image_path(new_id)
    fmt = save_format.upper()
    if fmt == "JPEG":
        im.save(out.with_suffix(".jpg"), format="JPEG", quality=92)
        out = out.with_suffix(".jpg")
        url = f"/api/chat-images/{new_id}?ext=jpg"
    elif fmt == "WEBP":
        im.save(out.with_suffix(".webp"), format="WEBP", quality=90)
        out = out.with_suffix(".webp")
        url = f"/api/chat-images/{new_id}?ext=webp"
    else:
        im.save(out, format="PNG")
        url = public_url(new_id)

    w, h = im.size
    return {
        "id": new_id,
        "url": url,
        "width": w,
        "height": h,
        "note": note,
        "markdown": f"![результат]({url})",
    }


def is_image_filename(name: str) -> bool:
    return Path(name or "").suffix.lower() in IMAGE_EXT
