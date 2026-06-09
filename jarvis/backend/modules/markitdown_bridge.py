"""
Обёртка над microsoft/markitdown — локальное извлечение текста без LLM.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

_instance = None
_lock = threading.Lock()
_error: str | None = None

# Форматы, где MarkItDown даёт лучший результат, чем узкие парсеры
PREFERRED_SUFFIXES = frozenset(
    {
        ".pdf",
        ".docx",
        ".doc",
        ".pptx",
        ".ppt",
        ".xlsx",
        ".xls",
        ".epub",
        ".html",
        ".htm",
        ".csv",
        ".json",
        ".xml",
        ".zip",
    }
)


def package_installed() -> bool:
    try:
        import markitdown  # noqa: F401

        return True
    except ImportError:
        return False


def get_status() -> dict[str, Any]:
    return {
        "package_installed": package_installed(),
        "ready": package_installed(),
        "error": _error,
        "message": (
            "MarkItDown готов (локальное извлечение текста)"
            if package_installed()
            else "Установите: pip install \"markitdown[pdf,docx,pptx,xlsx]\""
        ),
        "formats": sorted(PREFERRED_SUFFIXES),
    }


def _engine():
    global _instance, _error
    with _lock:
        if _instance is not None:
            return _instance
        if _error:
            raise RuntimeError(_error)
    try:
        from markitdown import MarkItDown

        eng = MarkItDown(enable_plugins=False)
        with _lock:
            _instance = eng
        return eng
    except Exception as e:
        with _lock:
            _error = str(e)
        raise


def convert_file_to_text(path: Path) -> str:
    """Файл → markdown/текст локально, без вызова нейросети."""
    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")
    if not package_installed():
        raise RuntimeError(
            'MarkItDown не установлен: pip install "markitdown[pdf,docx,pptx,xlsx]"'
        )
    eng = _engine()
    result = eng.convert_local(str(path))
    text = (getattr(result, "text_content", None) or getattr(result, "markdown", None) or "").strip()
    if not text:
        raise RuntimeError(f"MarkItDown не извлёк текст из {path.name}")
    return text


def try_convert_file(path: Path) -> str | None:
    """Без исключения — для цепочки fallback в document_tools."""
    try:
        return convert_file_to_text(path)
    except Exception:
        return None


def try_convert_html(html: str, *, max_chars: int = 12_000) -> tuple[str, str] | None:
    """HTML → markdown/текст. Возвращает (текст, engine) или None."""
    raw = (html or "").strip()
    if len(raw) < 40:
        return None
    if not package_installed():
        return None
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".html",
            delete=False,
            encoding="utf-8",
            errors="replace",
        ) as tmp:
            tmp.write(raw)
            tmp_path = Path(tmp.name)
        try:
            text = convert_file_to_text(tmp_path)[:max_chars]
            if text:
                return text, "markitdown"
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception:
        return None
    return None
