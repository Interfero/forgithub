"""
Пути данных Jarvis: встроенные ресурсы exe и постоянный каталог пользователя.
Файлы предобучения (data/memory) при обновлении exe не затираются — лежат в %LOCALAPPDATA%\\Jarvis\\data.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from modules.jarvis_edition import is_free_edition


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Корень ресурсов: _MEIPASS в exe, иначе каталог backend/."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def pro_install_root() -> Path | None:
    """Корень полной установки Jarvis (для общих моделей/браузеров)."""
    override = os.getenv("JARVIS_SHARED_ROOT", "").strip()
    if override:
        return Path(override)
    sibling = bundle_root().parent.parent / "jarvis"
    if sibling.is_dir() and (sibling / "backend").is_dir():
        return sibling.resolve()
    return None


def shared_browsers_dir() -> Path:
    """Каталог Chromium/Chrome (%LOCALAPPDATA%\\Jarvis\\browsers)."""
    base = (os.getenv("LOCALAPPDATA") or "").strip() or str(Path.home())
    d = Path(base) / "Jarvis" / "browsers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    """
    GGUF Qwen и метаданные.
    """
    if is_free_edition():
        pro = pro_install_root()
        if pro:
            shared = pro / "backend" / "data" / "models"
            if shared.is_dir():
                return shared
    local = bundle_root() / "data" / "models"
    local.mkdir(parents=True, exist_ok=True)
    return local


def user_data_dir() -> Path:
    """
    Постоянные данные (чаты, настройки, memory, jarvis.db).
    Dev: backend/data; exe: %LOCALAPPDATA%/Jarvis/data
    """
    override = os.getenv("JARVIS_DATA_DIR", "").strip()
    if override:
        return Path(override)
    if is_frozen():
        base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "Jarvis" / "data"
    return bundle_root() / "data"


def bundled_data_dir() -> Path:
    return bundle_root() / "data"


def frontend_dist_dir() -> Path:
    if is_frozen():
        return bundle_root() / "frontend" / "dist"
    return bundle_root().parent / "frontend" / "dist"


def ensure_user_data_dir() -> Path:
    d = user_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def migrate_legacy_data_next_to_exe() -> int:
    """Первый запуск нового exe: перенос data/ из папки рядом с Jarvis.exe."""
    if not is_frozen():
        return 0
    legacy = Path(sys.executable).resolve().parent / "data"
    if not legacy.is_dir():
        return 0
    moved = 0
    dst_root = ensure_user_data_dir()
    for src in legacy.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(legacy)
        dst = dst_root / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        moved += 1
    return moved


def seed_memory_from_bundle() -> int:
    """Вшитые в exe файлы предобучения — только если у пользователя файла ещё нет."""
    src_root = bundled_data_dir() / "memory"
    if not src_root.is_dir():
        return 0
    dst_root = ensure_user_data_dir() / "memory"
    copied = 0
    for src in src_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        try:
            from modules.memory_store import STEREOTYPES_FILENAMES

            if (
                len(rel.parts) >= 2
                and rel.parts[0] == "conscious"
                and rel.name in STEREOTYPES_FILENAMES
            ):
                continue
        except Exception:
            pass
        dst = dst_root / rel
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1
    return copied


def seed_icq_smileys_from_bundle() -> int:
    """Каталог и PNG смайликов ICQ — в user data при первом запуске."""
    src = bundled_data_dir() / "icq_smileys"
    if not src.is_dir():
        return 0
    dst = ensure_user_data_dir() / "icq_smileys"
    copied = 0
    for src_file in src.rglob("*"):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src)
        target = dst / rel
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, target)
        copied += 1
    return copied


def bootstrap_user_data() -> dict[str, int]:
    """Вызывать при старте до sync_all_from_disk."""
    ensure_user_data_dir()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(shared_browsers_dir()))
    return {
        "migrated_legacy": migrate_legacy_data_next_to_exe(),
        "seeded_memory": seed_memory_from_bundle(),
        "seeded_icq_smileys": seed_icq_smileys_from_bundle(),
    }
