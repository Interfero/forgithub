"""
Hugging Face Hub: токен, поиск репозиториев, скачивание артефактов в data/hf_skills/.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from modules.app_paths import bundle_root, user_data_dir

_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_MAX_DOWNLOAD_BYTES = int(os.getenv("JARVIS_HF_MAX_BYTES", str(10 * 1024**3)))
_JARVIS_DOWNLOAD_FILES = 5
_WEIGHT_SUFFIXES = (
    ".safetensors",
    ".gguf",
    ".bin",
    ".onnx",
    ".h5",
    ".pt",
    ".pth",
    ".msgpack",
)


def token_paths() -> list[Path]:
    root = bundle_root()
    return [
        root / "config" / "huggingface.key",
        user_data_dir() / "huggingface.key",
    ]


def load_token() -> str:
    for env_name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        v = (os.getenv(env_name) or "").strip()
        if v:
            return v
    for path in token_paths():
        if path.is_file():
            t = path.read_text(encoding="utf-8").strip()
            if t and not t.startswith("#"):
                return t
    return ""


def token_configured() -> bool:
    t = load_token()
    return t.startswith("hf_") and len(t) >= 20


def mask_token() -> str:
    t = load_token()
    if not t or len(t) < 12:
        return ""
    return t[:8] + "••••••••"


def _api():
    from huggingface_hub import HfApi

    token = load_token() or None
    return HfApi(token=token)


def validate_repo_id(repo_id: str) -> str:
    rid = (repo_id or "").strip()
    if not _REPO_ID_RE.match(rid):
        raise ValueError("repo_id должен быть вида author/name")
    return rid


def _split_query_terms(query: str) -> list[str]:
    parts = re.split(r"[\s,]+", (query or "").strip())
    terms: list[str] = []
    seen: set[str] = set()
    for part in parts:
        token = part.strip()
        if len(token) < 2:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(token)
    return terms


def _row_to_item(row: Any, rt: str) -> dict[str, Any] | None:
    rid = getattr(row, "id", None) or getattr(row, "modelId", "") or ""
    if not rid:
        return None
    return {
        "repo_id": rid,
        "repo_type": rt,
        "author": getattr(row, "author", None) or rid.split("/")[0],
        "downloads": getattr(row, "downloads", None),
        "likes": getattr(row, "likes", None),
        "tags": list(getattr(row, "tags", []) or [])[:8],
        "private": bool(getattr(row, "private", False)),
        "gated": bool(getattr(row, "gated", False)),
    }


def _search_hub_once(api: Any, query: str, rt: str, limit: int) -> list[dict[str, Any]]:
    if rt == "dataset":
        rows = api.list_datasets(search=query, limit=limit)
    elif rt == "space":
        rows = api.list_spaces(search=query, limit=limit)
    else:
        rows = api.list_models(search=query, limit=limit)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_item(row, rt)
        if item:
            out.append(item)
    return out


def _score_repo(item: dict[str, Any], terms: list[str]) -> tuple[int, int]:
    rid = (item.get("repo_id") or "").lower()
    author = ((item.get("author") or rid.split("/")[0]) or "").lower()
    tags = " ".join(item.get("tags") or []).lower()
    blob = f"{rid} {author} {tags}"

    matched_terms = 0
    score = 0
    for term in terms:
        tl = term.lower()
        if tl == author or rid.startswith(f"{tl}/"):
            score += 40
            matched_terms += 1
        elif tl in rid or tl in tags:
            score += 24
            matched_terms += 1
        elif tl in blob:
            score += 12
            matched_terms += 1

    # Сначала больше совпавших слов, потом детальный score.
    return matched_terms * 1000 + score, matched_terms


def _pick_download_files(repo_id: str, *, repo_type: str, revision: str = "main") -> list[str]:
    return list_files(repo_id, repo_type=repo_type, revision=revision)[:_JARVIS_DOWNLOAD_FILES]


def estimate_repo_sizes(
    repo_id: str,
    *,
    repo_type: str = "model",
    revision: str = "main",
) -> dict[str, Any]:
    rid = validate_repo_id(repo_id)
    api = _api()
    rt = repo_type if repo_type in ("model", "dataset", "space") else "model"

    download_files = _pick_download_files(rid, repo_type=rt, revision=revision)
    jarvis_download_bytes = 0
    if download_files:
        for path_info in api.get_paths_info(
            rid,
            paths=download_files,
            repo_type=rt,
            revision=revision,
        ):
            jarvis_download_bytes += int(path_info.size or 0)

    repo_total_bytes = 0
    main_file_bytes = 0
    main_file_name: str | None = None
    for entry in api.list_repo_tree(rid, repo_type=rt, revision=revision, recursive=True):
        path = getattr(entry, "path", None)
        size = getattr(entry, "size", None)
        if not path or size is None:
            continue
        size_i = int(size)
        repo_total_bytes += size_i
        lower = path.lower()
        if lower.endswith(_WEIGHT_SUFFIXES) and size_i > main_file_bytes:
            main_file_bytes = size_i
            main_file_name = path

    return {
        "jarvis_download_bytes": jarvis_download_bytes,
        "jarvis_download_files": len(download_files),
        "repo_total_bytes": repo_total_bytes,
        "main_file_bytes": main_file_bytes,
        "main_file_name": main_file_name,
    }


def _enrich_items_with_sizes(items: list[dict[str, Any]], repo_type: str) -> list[dict[str, Any]]:
    if not items:
        return items

    size_map: dict[str, dict[str, Any]] = {}

    def worker(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        rid = item["repo_id"]
        try:
            return rid, estimate_repo_sizes(rid, repo_type=repo_type)
        except Exception:
            return rid, {}

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(worker, item) for item in items]
        for future in as_completed(futures, timeout=45):
            try:
                rid, sizes = future.result()
                if sizes:
                    size_map[rid] = sizes
            except Exception:
                continue

    enriched: list[dict[str, Any]] = []
    for item in items:
        merged = {**item, **size_map.get(item["repo_id"], {})}
        enriched.append(merged)
    return enriched


def search_hub_result(
    query: str,
    *,
    repo_type: str = "model",
    limit: int = 12,
) -> dict[str, Any]:
    q = (query or "").strip()
    if len(q) < 2:
        return {"items": [], "search_mode": "empty", "terms": []}

    api = _api()
    rt = repo_type if repo_type in ("model", "dataset", "space") else "model"
    cap = max(1, min(limit, 20))

    exact = _search_hub_once(api, q, rt, cap)
    if exact:
        items = _enrich_items_with_sizes(exact[:cap], rt)
        return {"items": items, "search_mode": "exact", "terms": [q]}

    terms = _split_query_terms(q)
    if len(terms) <= 1:
        return {"items": [], "search_mode": "exact", "terms": terms}

    merged: dict[str, dict[str, Any]] = {}
    per_term = max(cap, 8)
    for term in sorted(terms, key=len, reverse=True):
        for item in _search_hub_once(api, term, rt, per_term):
            rid = item["repo_id"]
            if rid not in merged:
                merged[rid] = item

    ranked = sorted(
        merged.values(),
        key=lambda item: (
            -_score_repo(item, terms)[0],
            -(item.get("downloads") or 0),
            item["repo_id"],
        ),
    )
    items = _enrich_items_with_sizes(ranked[:cap], rt)
    return {
        "items": items,
        "search_mode": "multi_term",
        "terms": terms,
    }


def search_hub(
    query: str,
    *,
    repo_type: str = "model",
    limit: int = 12,
) -> list[dict[str, Any]]:
    return search_hub_result(query, repo_type=repo_type, limit=limit)["items"]


def list_files(repo_id: str, *, repo_type: str = "model", revision: str = "main") -> list[str]:
    rid = validate_repo_id(repo_id)
    api = _api()
    rt = repo_type if repo_type in ("model", "dataset", "space") else "model"
    return api.list_repo_files(rid, repo_type=rt, revision=revision)


def download_repo_files(
    repo_id: str,
    *,
    repo_type: str = "model",
    revision: str = "main",
    filenames: list[str] | None = None,
    local_dir: Path,
    allow_patterns: list[str] | None = None,
) -> list[Path]:
    from huggingface_hub import hf_hub_download

    rid = validate_repo_id(repo_id)
    rt = repo_type if repo_type in ("model", "dataset", "space") else "model"
    token = load_token() or None
    local_dir.mkdir(parents=True, exist_ok=True)

    if filenames:
        names = [f.strip() for f in filenames if f.strip()]
    elif allow_patterns:
        names = list_files(rid, repo_type=rt, revision=revision)
        import fnmatch

        picked: list[str] = []
        for name in names:
            if any(fnmatch.fnmatch(name, pat) for pat in allow_patterns):
                picked.append(name)
        names = picked[:20]
    else:
        names = list_files(rid, repo_type=rt, revision=revision)[:5]

    if not names:
        raise ValueError("Не найдено файлов для скачивания")

    saved: list[Path] = []
    for name in names:
        path = hf_hub_download(
            repo_id=rid,
            filename=name,
            repo_type=rt,
            revision=revision,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            token=token,
        )
        p = Path(path)
        if p.stat().st_size > _MAX_DOWNLOAD_BYTES:
            p.unlink(missing_ok=True)
            raise ValueError(
                f"Файл {name} больше лимита {_MAX_DOWNLOAD_BYTES // (1024**3)} ГБ"
            )
        saved.append(p)
    return saved


def status_payload() -> dict[str, Any]:
    from modules.hf_skills_store import skills_root, summarize_registry

    root = skills_root()
    reg = summarize_registry()
    return {
        "token_configured": token_configured(),
        "token_mask": mask_token() if token_configured() else "",
        "skills_dir": str(root),
        "max_download_gb": round(_MAX_DOWNLOAD_BYTES / (1024**3), 1),
        **reg,
    }
