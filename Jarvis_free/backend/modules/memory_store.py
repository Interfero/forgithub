"""
Сознательное, бессознательное и контекст режимов — текстовые файлы на диске.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

# Постоянный каталог пользователя; в exe вшитые defaults — modules.app_paths.seed_memory_from_bundle
from modules.app_paths import user_data_dir

DATA_DIR = user_data_dir()
CONSCIOUS_DIR = DATA_DIR / "memory" / "conscious"
UNCONSCIOUS_DIR = DATA_DIR / "memory" / "unconscious"
MODE_STANDARD_DIR = DATA_DIR / "memory" / "modes" / "standard"
MODE_ACCOUNTANT_DIR = DATA_DIR / "memory" / "modes" / "accountant"
MODE_MARKETER_DIR = DATA_DIR / "memory" / "modes" / "marketer"
MODE_DEVELOPER_DIR = DATA_DIR / "memory" / "modes" / "developer"

STORE_DIRS: dict[str, Path] = {
    "conscious": CONSCIOUS_DIR,
    "unconscious": UNCONSCIOUS_DIR,
    "mode-standard": MODE_STANDARD_DIR,
    "mode-accountant": MODE_ACCOUNTANT_DIR,
    "mode-marketer": MODE_MARKETER_DIR,
    "mode-developer": MODE_DEVELOPER_DIR,
}

ALLOWED_EXT = {".txt", ".md", ".json"}

# Базовые правила личности — не удаляются (при отсутствии файл создаётся заново)
PROTECTED_FILES: dict[str, frozenset[str]] = {
    "unconscious": frozenset(
        {
            "personality_rules.txt",
            "jarvis_skills.txt",
            "page_seo_audit_rules.txt",
            "dialog_routing_rules.txt",
            "dry_style_rules.txt",
            "icq_smileys_rules.txt",
            "maintenance_manifest.txt",
            "insult_defense_rules.txt",
        }
    ),
    "conscious": frozenset({"Техдокументация.txt"}),
}

# Автофайлы Jarvis — не в UI чата и не в промпт (SQLite + runtime).
INTERNAL_CONSCIOUS_FILES = frozenset(
    {
        "Оскорбления_Jarvis.md",
        "Память_сессий.md",
    }
)


def is_internal_conscious_file(file_id: str) -> bool:
    return Path(file_id).name in INTERNAL_CONSCIOUS_FILES


def is_protected(store: str, file_id: str) -> bool:
    return Path(file_id).name in PROTECTED_FILES.get(store, frozenset())


def _migrate_standard_to_conscious() -> None:
    """Слияние устаревшего mode-standard в сознательное (один смысл для стандартного чата)."""
    if not MODE_STANDARD_DIR.exists():
        return
    CONSCIOUS_DIR.mkdir(parents=True, exist_ok=True)
    for p in MODE_STANDARD_DIR.iterdir():
        if p.is_file() and p.suffix.lower() in ALLOWED_EXT:
            dst = CONSCIOUS_DIR / p.name
            if not dst.exists():
                shutil.copy2(p, dst)


def _ensure_maintenance_manifest_file() -> None:
    dst = UNCONSCIOUS_DIR / "maintenance_manifest.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / "maintenance_manifest.txt"
    )
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_icq_smileys_rules_file() -> None:
    dst = UNCONSCIOUS_DIR / "icq_smileys_rules.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / "icq_smileys_rules.txt"
    )
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_dry_style_rules_file() -> None:
    dst = UNCONSCIOUS_DIR / "dry_style_rules.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / "dry_style_rules.txt"
    )
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_dialog_routing_rules_file() -> None:
    """Правила онлайн/офлайн для роутера Qwen — создаётся, если файла ещё нет у пользователя."""
    dst = UNCONSCIOUS_DIR / "dialog_routing_rules.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / "dialog_routing_rules.txt"
    )
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dst.write_text(
            "=== Кто отвечает Шефу ===\n"
            "Облако доступно → DeepSeek/Perplexity/Nano Banana и web_search, fetch_url.\n"
            "Облака нет → только локальная Qwen 2.5 14B и инструменты Jarvis.\n",
            encoding="utf-8",
        )


def _ensure_avito_listing_prompt_file() -> None:
    """Плейбук объявлений Авито для режима маркетолога."""
    dst = MODE_MARKETER_DIR / "avito_listing_prompt.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "modes"
        / "marketer"
        / "avito_listing_prompt.txt"
    )
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_page_seo_audit_rules_file() -> None:
    dst = UNCONSCIOUS_DIR / "page_seo_audit_rules.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / "page_seo_audit_rules.txt"
    )
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_insult_defense_rules_file() -> None:
    """Правила реакции на оскорбления и счётчик на аватаре — создаётся, если файла ещё нет."""
    dst = UNCONSCIOUS_DIR / "insult_defense_rules.txt"
    if dst.exists():
        return
    src = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "unconscious"
        / "insult_defense_rules.txt"
    )
    if src.is_file():
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        dst.write_text(
            "=== Оскорбления в чате ===\n"
            "Грубость в адрес Jarvis — ответ с достоинством; счётчик N/3 на аватаре; "
            "после 3 — обида ~30 мин.\n",
            encoding="utf-8",
        )


def _ensure_dirs() -> None:
    for d in STORE_DIRS.values():
        d.mkdir(parents=True, exist_ok=True)
    _migrate_standard_to_conscious()
    default_unconscious = UNCONSCIOUS_DIR / "personality_rules.txt"
    if not default_unconscious.exists():
        default_unconscious.write_text(
            "Тон: профессиональный, спокойный, как у Jarvis. Обращайся «Шеф».\n"
            "Всегда уважай конфиденциальность пользователя.\n"
            "По умолчанию отвечай коротко и по делу (1–4 предложения). "
            "Развёрнуто — только если Шеф явно просит подробно/развёрнуто/пошагово.\n"
            "Не пиши рассуждения вслух и симуляцию диалога — только итог.\n",
            encoding="utf-8",
        )
    _ensure_dialog_routing_rules_file()
    _ensure_dry_style_rules_file()
    _ensure_icq_smileys_rules_file()
    _ensure_insult_defense_rules_file()
    _ensure_maintenance_manifest_file()
    _ensure_page_seo_audit_rules_file()
    _ensure_avito_listing_prompt_file()
    default_skills = UNCONSCIOUS_DIR / "jarvis_skills.txt"
    if not default_skills.exists():
        bundle_skills = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "memory"
            / "unconscious"
            / "jarvis_skills.txt"
        )
        if bundle_skills.is_file():
            default_skills.write_text(
                bundle_skills.read_text(encoding="utf-8"), encoding="utf-8"
            )
        else:
            default_skills.write_text(
                "=== Навыки Jarvis (встроенные) ===\n"
                "Проверка систем, смена режима, краткие ответы.\n",
                encoding="utf-8",
            )


def _dir_for(store: str) -> Path:
    if store not in STORE_DIRS:
        raise ValueError(f"Unknown store: {store}")
    _ensure_dirs()
    return STORE_DIRS[store]


def list_files(store: str, *, for_chat_ui: bool = False) -> list[dict]:
    d = _dir_for(store)
    files = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.suffix.lower() in ALLOWED_EXT:
            name = p.name
            if for_chat_ui and store == "conscious" and is_internal_conscious_file(name):
                continue
            files.append(
                {
                    "id": name,
                    "name": name,
                    "size_bytes": p.stat().st_size,
                    "store": store,
                    "protected": is_protected(store, p.name),
                }
            )
    return files


def add_file(store: str, filename: str, content: bytes) -> dict:
    d = _dir_for(store)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        ext = ".txt"
        filename = Path(filename).stem + ext
    safe = "".join(c for c in filename if c.isalnum() or c in "._- ") or "file.txt"
    path = d / safe
    if path.exists():
        safe = f"{uuid.uuid4().hex[:6]}_{safe}"
        path = d / safe
    path.write_bytes(content)
    meta = {
        "id": path.name,
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "store": store,
    }
    try:
        from modules import jarvis_db

        jarvis_db.init_db()
        jarvis_db.upsert_file_from_disk(
            store,
            path.name,
            path.read_text(encoding="utf-8", errors="replace"),
            protected=is_protected(store, path.name),
            file_path=str(path),
        )
    except Exception:
        pass
    return meta


def delete_file(store: str, file_id: str) -> bool:
    if is_protected(store, file_id):
        return False
    d = _dir_for(store)
    path = d / Path(file_id).name
    if path.exists() and path.parent.resolve() == d.resolve():
        path.unlink()
        try:
            from modules import jarvis_db

            jarvis_db.delete_file(store, file_id)
        except Exception:
            pass
        return True
    return False


def read_file(store: str, file_id: str) -> dict | None:
    d = _dir_for(store)
    name = Path(file_id).name
    path = d / name
    if not path.is_file() or path.suffix.lower() not in ALLOWED_EXT:
        return None
    if path.parent.resolve() != d.resolve():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "id": name,
        "name": name,
        "content": content,
        "size_bytes": path.stat().st_size,
        "store": store,
        "protected": is_protected(store, name),
    }


def read_all_text(store: str, max_chars: int = 12000) -> str:
    try:
        from modules import jarvis_db

        jarvis_db.init_db()
        text = jarvis_db.read_store_text(store, max_chars=max_chars)
        if text.strip():
            return text
    except Exception:
        pass
    parts: list[str] = []
    total = 0
    for meta in list_files(store):
        path = _dir_for(store) / meta["name"]
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if not text:
            continue
        chunk = f"### {meta['name']}\n{text}"
        if total + len(chunk) > max_chars:
            parts.append(chunk[: max_chars - total] + "…")
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)


def read_mode_context(mode_value: str, max_chars: int = 8000) -> str:
    """Стандартный чат использует только «Сознательное» (см. build_system_message)."""
    if mode_value == "standard":
        return ""
    key_map = {
        "accountant": "mode-accountant",
        "marketer": "mode-marketer",
        "developer": "mode-developer",
    }
    key = key_map.get(mode_value)
    if not key:
        return ""
    text = read_all_text(key, max_chars=max_chars)
    if text:
        return f"\n\n[Контекст режима — файлы]\n{text}"
    return ""


def get_stores_summary(*, for_chat_ui: bool = False) -> dict:
    _ensure_dirs()
    return {
        "conscious": list_files("conscious", for_chat_ui=for_chat_ui),
        "unconscious": list_files("unconscious"),
        "mode_accountant": list_files("mode-accountant"),
        "mode_marketer": list_files("mode-marketer"),
        "mode_developer": list_files("mode-developer"),
    }
