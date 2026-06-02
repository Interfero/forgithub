"""Локальное хранение семплов и дайджестов (JSON + опционально SQLite позже)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from modules.tg_analyst import runtime


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _paths() -> tuple[Path, Path]:
    d = runtime.analyst_dir()
    return d / "samples.json", d / "digests.json"


def save_samples(chats: list[dict[str, Any]]) -> str:
    samples_path, _ = _paths()
    payload = {"synced_at": _now(), "chats": chats}
    samples_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload["synced_at"]


def load_samples() -> dict[str, Any]:
    samples_path, _ = _paths()
    if not samples_path.is_file():
        return {"synced_at": None, "chats": []}
    return json.loads(samples_path.read_text(encoding="utf-8"))


def save_digests(items: list[dict[str, Any]]) -> None:
    _, digests_path = _paths()
    digests_path.write_text(
        json.dumps({"updated_at": _now(), "items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_digests() -> dict[str, Any]:
    _, digests_path = _paths()
    if not digests_path.is_file():
        return {"updated_at": None, "items": []}
    return json.loads(digests_path.read_text(encoding="utf-8"))
