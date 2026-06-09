"""
Каталог навыков Hugging Face в data/hf_skills/ (manifest + файлы).
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir
from modules.hf_hub_client import download_repo_files, validate_repo_id

REGISTRY_NAME = "registry.json"


def skills_root() -> Path:
    d = user_data_dir() / "hf_skills"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _registry_path() -> Path:
    return skills_root() / REGISTRY_NAME


def _load_registry() -> dict[str, Any]:
    p = _registry_path()
    if not p.is_file():
        return {"skills": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("skills"), list):
            return data
    except Exception:
        pass
    return {"skills": []}


def _save_registry(data: dict[str, Any]) -> None:
    p = _registry_path()
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _skill_dir(skill_id: str) -> Path:
    sid = (skill_id or "").strip()
    if not sid or ".." in sid or "/" in sid or "\\" in sid:
        raise ValueError("Некорректный skill_id")
    return skills_root() / sid


def summarize_registry() -> dict[str, Any]:
    reg = _load_registry()
    skills = reg.get("skills") or []
    total_bytes = 0
    enabled = 0
    for s in skills:
        total_bytes += int(s.get("size_bytes") or 0)
        if s.get("enabled"):
            enabled += 1
    return {
        "installed_count": len(skills),
        "enabled_count": enabled,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 1),
    }


def list_installed() -> list[dict[str, Any]]:
    return list(_load_registry().get("skills") or [])


def get_skill(skill_id: str) -> dict[str, Any] | None:
    for s in list_installed():
        if s.get("id") == skill_id:
            return s
    return None


def install_skill(
    repo_id: str,
    *,
    repo_type: str = "model",
    revision: str = "main",
    filenames: list[str] | None = None,
    allow_patterns: list[str] | None = None,
    label: str = "",
) -> dict[str, Any]:
    rid = validate_repo_id(repo_id)
    skill_id = uuid.uuid4().hex[:12]
    root = _skill_dir(skill_id)
    files_dir = root / "files"
    saved = download_repo_files(
        rid,
        repo_type=repo_type,
        revision=revision,
        filenames=filenames,
        allow_patterns=allow_patterns,
        local_dir=files_dir,
    )
    size_bytes = sum(p.stat().st_size for p in saved if p.is_file())
    rel_files = [str(p.relative_to(root)).replace("\\", "/") for p in saved]
    integration = _guess_integration(repo_type, rel_files)
    manifest = {
        "id": skill_id,
        "repo_id": rid,
        "repo_type": repo_type,
        "revision": revision,
        "label": label or rid,
        "files": rel_files,
        "size_bytes": size_bytes,
        "integration": integration,
        "enabled": True,
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    reg = _load_registry()
    reg.setdefault("skills", []).append(manifest)
    _save_registry(reg)
    return manifest


def _guess_integration(repo_type: str, files: list[str]) -> str:
    low = " ".join(files).lower()
    if repo_type == "dataset":
        return "rag_dataset"
    if any(low.endswith(ext) for ext in (".gguf", ".bin")):
        return "gguf_model"
    if any(low.endswith(ext) for ext in (".safetensors", ".pt", ".pth")):
        return "weights"
    if any(low.endswith(ext) for ext in (".py", ".json", ".md", ".txt")):
        return "files"
    return "artifact"


def set_enabled(skill_id: str, enabled: bool) -> dict[str, Any]:
    reg = _load_registry()
    skills = reg.get("skills") or []
    found = None
    for s in skills:
        if s.get("id") == skill_id:
            s["enabled"] = bool(enabled)
            found = s
            break
    if not found:
        raise ValueError("Навык не найден")
    _save_registry(reg)
    mpath = _skill_dir(skill_id) / "manifest.json"
    if mpath.is_file():
        mpath.write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    return found


def remove_skill(skill_id: str) -> bool:
    reg = _load_registry()
    skills = reg.get("skills") or []
    new_skills = [s for s in skills if s.get("id") != skill_id]
    if len(new_skills) == len(skills):
        return False
    reg["skills"] = new_skills
    _save_registry(reg)
    root = _skill_dir(skill_id)
    if root.is_dir():
        import shutil

        shutil.rmtree(root, ignore_errors=True)
    return True


def enabled_skills_context() -> str:
    lines = ["[Hugging Face — установленные навыки]"]
    items = [s for s in list_installed() if s.get("enabled")]
    if not items:
        lines.append("Пока нет активных навыков HF. hf_search → hf_download_skill.")
        return "\n".join(lines)
    for s in items:
        lines.append(
            f"• {s.get('label') or s.get('repo_id')} ({s.get('integration')}) — "
            f"repo {s.get('repo_id')}, id={s.get('id')}"
        )
    lines.append("Инструменты: hf_search, hf_download_skill, hf_list_skills, hf_enable_skill.")
    return "\n".join(lines)
