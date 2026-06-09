"""
Чтение и конвертация документов внутри Jarvis: PDF, Office, изображения, текстовые форматы.
Текст из документов — через microsoft/markitdown (локально, без токенов LLM), с fallback на PyMuPDF/docx.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir
from modules.local_text_utils import extractive_summarize
from modules.markitdown_bridge import PREFERRED_SUFFIXES, get_status as markitdown_status
from modules.markitdown_bridge import try_convert_file

TEXT_SUFFIXES = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".csv",
        ".tsv",
        ".html",
        ".htm",
        ".xml",
        ".log",
        ".yaml",
        ".yml",
        ".rtf",
        ".ini",
        ".cfg",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".cs",
        ".go",
        ".rs",
        ".sql",
    }
)
IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".ico"}
)
PDF_SUFFIX = ".pdf"
DOCX_SUFFIX = ".docx"
OFFICE_SUFFIXES = frozenset(
    {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".epub"}
)
MARKDOWN_OUT_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".text"})

_MAX_READ_CHARS = 120_000
_MAX_PDF_PAGES_RENDER = 50


def workspace_dir() -> Path:
    d = user_data_dir() / "workspace" / "documents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _resolve_path(path: str) -> Path:
    raw = (path or "").strip()
    if not raw:
        raise ValueError("Укажите путь к файлу.")
    p = Path(raw).expanduser()
    try:
        return p.resolve()
    except Exception:
        return p.absolute()


def _suffix(path: Path) -> str:
    return path.suffix.lower()


def _cyrillic_font_path() -> str | None:
    win = os.environ.get("WINDIR", r"C:\Windows")
    for name in ("arial.ttf", "segoeui.ttf", "calibri.ttf", "times.ttf"):
        p = Path(win) / "Fonts" / name
        if p.is_file():
            return str(p)
    for p in (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ):
        if p.is_file():
            return str(p)
    return None


def _require_pymupdf():
    try:
        import fitz  # PyMuPDF

        return fitz
    except ImportError as e:
        raise RuntimeError(
            "Нужен PyMuPDF: pip install pymupdf pillow"
        ) from e


def _require_pillow():
    try:
        from PIL import Image

        return Image
    except ImportError as e:
        raise RuntimeError("Нужен Pillow: pip install pillow") from e


def _extract_text(path: Path, *, max_chars: int = _MAX_READ_CHARS) -> tuple[str, str]:
    """MarkItDown → узкие парсеры → ошибка. Возвращает (текст, имя_движка)."""
    suffix = _suffix(path)
    if suffix in PREFERRED_SUFFIXES or suffix in OFFICE_SUFFIXES:
        md_text = try_convert_file(path)
        if md_text:
            return md_text[:max_chars], "markitdown"
    if suffix in TEXT_SUFFIXES or suffix == "":
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars], "builtin"
    if suffix == DOCX_SUFFIX:
        from docx import Document

        doc = Document(str(path))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return text[:max_chars], "python-docx"
    if suffix == PDF_SUFFIX:
        return read_pdf_text(path, max_chars=max_chars), "pymupdf"
    raise ValueError(f"Формат {suffix} не поддерживается для чтения как текст.")


def read_text_file(path: Path, *, max_chars: int = _MAX_READ_CHARS) -> str:
    text, _ = _extract_text(path, max_chars=max_chars)
    return text


def read_pdf_text(
    path: Path,
    *,
    max_chars: int = _MAX_READ_CHARS,
    page_start: int | None = None,
    page_end: int | None = None,
) -> str:
    fitz = _require_pymupdf()
    doc = fitz.open(str(path))
    try:
        start = max(0, (page_start or 1) - 1)
        end = min(len(doc), page_end or len(doc))
        parts: list[str] = []
        total = 0
        for i in range(start, end):
            page = doc.load_page(i)
            text = (page.get_text("text") or "").strip()
            if not text:
                continue
            chunk = f"--- Страница {i + 1} ---\n{text}"
            if total + len(chunk) > max_chars:
                parts.append(chunk[: max_chars - total] + "…")
                break
            parts.append(chunk)
            total += len(chunk)
        return "\n\n".join(parts) if parts else "(Текст в PDF не извлечён — возможно, скан без OCR.)"
    finally:
        doc.close()


def _apply_summarize(
    data: dict[str, Any],
    *,
    summarize: bool,
    summary_sentences: int,
    max_chars: int,
) -> dict[str, Any]:
    if not summarize or data.get("binary"):
        return data
    text = (data.get("content") or "").strip()
    if not text:
        return data
    summary = extractive_summarize(
        text,
        max_sentences=max(2, min(summary_sentences, 12)),
        max_chars=min(4000, max_chars),
    )
    data = dict(data)
    data["summary"] = summary
    data["summarized"] = True
    data["content"] = summary
    eng = data.get("engine") or "builtin"
    data["engine"] = f"{eng}+extractive"
    data["chars"] = len(summary)
    return data


def read_document(
    path: str,
    *,
    max_chars: int = _MAX_READ_CHARS,
    page_start: int | None = None,
    page_end: int | None = None,
    summarize: bool = False,
    summary_sentences: int = 5,
) -> dict[str, Any]:
    p = _resolve_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл не найден: {p}")
    suffix = _suffix(p)

    if suffix in OFFICE_SUFFIXES | {".html", ".htm", ".epub", ".csv"}:
        text, engine = _extract_text(p, max_chars=max_chars)
        return _apply_summarize(
            {
                "path": str(p),
                "format": suffix.lstrip("."),
                "chars": len(text),
                "content": text,
                "engine": engine,
            },
            summarize=summarize,
            summary_sentences=summary_sentences,
            max_chars=max_chars,
        )

    if suffix == PDF_SUFFIX:
        if page_start is None and page_end is None:
            md_text = try_convert_file(p)
            if md_text:
                fitz = _require_pymupdf()
                with fitz.open(str(p)) as doc:
                    pages = len(doc)
                text = md_text[:max_chars]
                return _apply_summarize(
                    {
                        "path": str(p),
                        "format": "pdf",
                        "pages": pages,
                        "chars": len(text),
                        "content": text,
                        "engine": "markitdown",
                    },
                    summarize=summarize,
                    summary_sentences=summary_sentences,
                    max_chars=max_chars,
                )
        text = read_pdf_text(
            p,
            max_chars=max_chars,
            page_start=page_start,
            page_end=page_end,
        )
        fitz = _require_pymupdf()
        with fitz.open(str(p)) as doc:
            pages = len(doc)
        return _apply_summarize(
            {
                "path": str(p),
                "format": "pdf",
                "pages": pages,
                "chars": len(text),
                "content": text,
                "engine": "pymupdf",
            },
            summarize=summarize,
            summary_sentences=summary_sentences,
            max_chars=max_chars,
        )
    if suffix in IMAGE_SUFFIXES:
        Image = _require_pillow()
        with Image.open(p) as img:
            w, h = img.size
            mode = img.mode
        return {
            "path": str(p),
            "format": suffix.lstrip("."),
            "binary": True,
            "width": w,
            "height": h,
            "mode": mode,
            "message": "Изображение. Для текста используйте doc_convert в pdf/txt или OCR вне Jarvis.",
        }
    text, engine = _extract_text(p, max_chars=max_chars)
    return _apply_summarize(
        {
            "path": str(p),
            "format": suffix.lstrip(".") or "text",
            "chars": len(text),
            "content": text,
            "engine": engine,
        },
        summarize=summarize,
        summary_sentences=summary_sentences,
        max_chars=max_chars,
    )


def _default_output_path(source: Path, target_format: str) -> Path:
    fmt = target_format.lower().lstrip(".")
    if fmt in {"png", "jpg", "jpeg", "webp"}:
        base = workspace_dir() / f"{source.stem}_pages"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return workspace_dir() / f"{source.stem}.{fmt}"


def text_to_pdf(text: str, out_path: Path, *, title: str = "") -> Path:
    fitz = _require_pymupdf()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    rect = fitz.Rect(50, 50, 545, 792)
    fontfile = _cyrillic_font_path()
    if fontfile:
        page.insert_textbox(
            rect,
            (title + "\n\n" if title else "") + text,
            fontsize=11,
            fontfile=fontfile,
            align=fitz.TEXT_ALIGN_LEFT,
        )
    else:
        page.insert_textbox(rect, text, fontsize=11, align=fitz.TEXT_ALIGN_LEFT)
    doc.save(str(out_path))
    doc.close()
    return out_path


def images_to_pdf(image_paths: list[Path], out_path: Path) -> Path:
    fitz = _require_pymupdf()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for img_path in image_paths:
        img_doc = fitz.open(str(img_path))
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()
        img_pdf = fitz.open("pdf", pdf_bytes)
        doc.insert_pdf(img_pdf)
        img_pdf.close()
    doc.save(str(out_path))
    doc.close()
    return out_path


def pdf_to_images(
    path: Path,
    out_dir: Path,
    *,
    image_format: str = "png",
    dpi: int = 150,
    max_pages: int = _MAX_PDF_PAGES_RENDER,
) -> list[Path]:
    fitz = _require_pymupdf()
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = image_format.lower().lstrip(".")
    if fmt == "jpg":
        fmt = "jpeg"
    saved: list[Path] = []
    doc = fitz.open(str(path))
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            out = out_dir / f"page_{i + 1:03d}.{fmt if fmt != 'jpeg' else 'jpg'}"
            if fmt == "jpeg":
                pix.save(str(out), output="jpeg")
            else:
                pix.save(str(out))
            saved.append(out)
    finally:
        doc.close()
    return saved


def image_to_image(src: Path, dst: Path, *, target_format: str) -> Path:
    Image = _require_pillow()
    fmt = target_format.lower().lstrip(".")
    if fmt == "jpg":
        fmt = "JPEG"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        if fmt.upper() == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(dst, format=fmt.upper() if fmt != "jpg" else "JPEG")
    return dst


def convert_document(
    source: str,
    target_format: str,
    *,
    output_path: str = "",
    dpi: int = 150,
) -> dict[str, Any]:
    src = _resolve_path(source)
    if not src.is_file():
        raise FileNotFoundError(f"Файл не найден: {src}")
    fmt = (target_format or "").strip().lower().lstrip(".")
    if not fmt:
        raise ValueError("Укажите target_format (pdf, txt, png, jpg, docx…).")

    src_suffix = _suffix(src)
    out = Path(output_path).expanduser().resolve() if output_path.strip() else _default_output_path(src, fmt)

    # Office / HTML / EPUB → text/md (MarkItDown)
    if src_suffix in OFFICE_SUFFIXES | {".html", ".htm", ".epub", ".csv"} and fmt in MARKDOWN_OUT_SUFFIXES:
        text, engine = _extract_text(src)
        if not output_path.strip():
            ext = "md" if fmt in {"md", "markdown"} else "txt"
            out = workspace_dir() / f"{src.stem}.{ext}"
        out.write_text(text, encoding="utf-8")
        return {
            "ok": True,
            "source": str(src),
            "output": str(out),
            "format": fmt,
            "chars": len(text),
            "engine": engine,
        }

    # PDF → text/md
    if src_suffix == PDF_SUFFIX and fmt in MARKDOWN_OUT_SUFFIXES:
        text, engine = _extract_text(src)
        out.write_text(text, encoding="utf-8")
        return {
            "ok": True,
            "source": str(src),
            "output": str(out),
            "format": fmt,
            "chars": len(text),
            "engine": engine,
        }

    # PDF → images
    if src_suffix == PDF_SUFFIX and fmt in {"png", "jpg", "jpeg", "webp"}:
        if output_path.strip():
            out_dir = out if out.suffix == "" else out.parent
        else:
            out_dir = out
        files = pdf_to_images(src, out_dir, image_format=fmt, dpi=dpi)
        return {
            "ok": True,
            "source": str(src),
            "output_dir": str(out_dir),
            "format": fmt,
            "pages": len(files),
            "files": [str(f) for f in files],
        }

    # Images → PDF
    if src_suffix in IMAGE_SUFFIXES and fmt == "pdf":
        if not output_path.strip():
            out = workspace_dir() / f"{src.stem}.pdf"
        images_to_pdf([src], out)
        return {"ok": True, "source": str(src), "output": str(out), "format": "pdf"}

    # Text-like → PDF
    if src_suffix in TEXT_SUFFIXES | {DOCX_SUFFIX} and fmt == "pdf":
        text = read_text_file(src)
        if not output_path.strip():
            out = workspace_dir() / f"{src.stem}.pdf"
        text_to_pdf(text, out, title=src.name)
        return {"ok": True, "source": str(src), "output": str(out), "format": "pdf", "chars": len(text)}

    # Image → image
    if src_suffix in IMAGE_SUFFIXES and fmt in {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}:
        if not output_path.strip():
            ext = "jpg" if fmt == "jpeg" else fmt
            out = workspace_dir() / f"{src.stem}.{ext}"
        image_to_image(src, out, target_format=fmt)
        return {"ok": True, "source": str(src), "output": str(out), "format": fmt}

    # PDF → PDF (copy / normalize)
    if src_suffix == PDF_SUFFIX and fmt == "pdf":
        if not output_path.strip():
            out = workspace_dir() / f"{src.stem}_copy.pdf"
        shutil.copy2(src, out)
        return {"ok": True, "source": str(src), "output": str(out), "format": "pdf", "note": "копия"}

    raise ValueError(
        f"Конвертация {src_suffix or '(без расширения)'} → {fmt} не поддерживается. "
        f"Поддерживаются: текст/docx→pdf; изображения↔pdf; pdf→txt/png/jpg."
    )


def format_read_result(data: dict[str, Any], *, max_out: int = 12_000) -> str:
    if data.get("binary"):
        return (
            f"Файл: {data['path']}\n"
            f"Формат: {data.get('format')} ({data.get('width')}×{data.get('height')})\n"
            f"{data.get('message', '')}"
        )
    content = (data.get("content") or "")[:max_out]
    head = f"Файл: {data['path']}"
    if data.get("pages"):
        head += f" · страниц: {data['pages']}"
    if data.get("chars"):
        head += f" · символов: {data['chars']}"
    if data.get("engine"):
        head += f" · движок: {data['engine']}"
    if data.get("summarized"):
        head += " · краткое изложение (extractive)"
    return f"{head}\n\n{content}"


def format_convert_result(data: dict[str, Any]) -> str:
    lines = [f"✅ Конвертация: {data.get('source')}"]
    if data.get("output"):
        lines.append(f"Результат: {data['output']}")
    if data.get("output_dir"):
        lines.append(f"Каталог: {data['output_dir']} · страниц: {data.get('pages', 0)}")
    if data.get("files"):
        lines.append("Файлы:")
        for f in data["files"][:20]:
            lines.append(f"  • {f}")
        if len(data["files"]) > 20:
            lines.append(f"  … и ещё {len(data['files']) - 20}")
    if data.get("note"):
        lines.append(f"({data['note']})")
    return "\n".join(lines)


def get_document_engine_status() -> dict[str, Any]:
    md = markitdown_status()
    return {
        "markitdown": md,
        "message": md.get("message") or "",
    }


def supported_formats_help() -> str:
    md = "да" if markitdown_status().get("package_installed") else "pip install markitdown[pdf,docx,pptx,xlsx]"
    return (
        f"Чтение (MarkItDown: {md}): PDF, DOCX, PPTX, XLSX, EPUB, HTML, CSV, txt/md/json/xml/yaml.\n"
        "Конвертация:\n"
        "• pdf/docx/pptx/xlsx/epub/html → txt/md (MarkItDown, без LLM)\n"
        "• текст/docx → pdf\n"
        "• изображение (png/jpg/webp/…) → pdf\n"
        "• pdf → png/jpg (по страницам в workspace/documents)\n"
        "• изображение → png/jpg/webp\n"
        "Инструменты: doc_read, doc_convert; навыки: read_document_file, convert_document_file."
    )
