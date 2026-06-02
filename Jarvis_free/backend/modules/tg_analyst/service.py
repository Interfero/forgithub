"""Оркестрация: статус, sync, analyze, mark-read."""

from __future__ import annotations

import uuid
from typing import Any

from modules.tg_analyst import analyzer, auth, reader, runtime, storage
from modules.tg_analyst.auth import get_auth_state
from modules.tg_analyst.models import (
    AnalystConfigIn,
    AnalystConfigOut,
    AnalystStatusOut,
    AuthPhase,
    ChatDigestOut,
    DigestsOut,
    JobStatus,
    MarkAllReadOut,
    SuggestedReply,
    SyncOut,
)

_DEFAULT_CONFIG = AnalystConfigIn()


def _config_path():
    return runtime.analyst_dir() / "config.json"


def load_config() -> AnalystConfigOut:
    import json

    path = _config_path()
    raw: dict = {}
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg = AnalystConfigIn(**{**_DEFAULT_CONFIG.model_dump(), **raw})
    return AnalystConfigOut(
        **cfg.model_dump(),
        telethon_installed=runtime.telethon_installed(),
        credentials_configured=runtime.credentials_configured(),
        session_exists=runtime.session_exists(),
    )


def save_config(body: AnalystConfigIn) -> AnalystConfigOut:
    import json

    cleaned = []
    seen: set[str] = set()
    for raw in body.blocklist_ids:
        s = str(raw).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        cleaned.append(s)
    data = body.model_dump()
    data["blocklist_ids"] = cleaned
    _config_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return load_config()


_jobs: dict[str, dict[str, Any]] = {}


def get_status() -> AnalystStatusOut:
    st = get_auth_state()
    if runtime.session_exists() and st.phase == AuthPhase.NONE:
        st.phase = AuthPhase.READY
    samples = storage.load_samples()
    active = next(
        (j for j in _jobs.values() if j.get("status") == JobStatus.RUNNING.value),
        None,
    )
    return AnalystStatusOut(
        auth_phase=st.phase,
        auth_message=st.message,
        telethon_installed=runtime.telethon_installed(),
        credentials_configured=runtime.credentials_configured(),
        session_exists=runtime.session_exists(),
        last_sync_at=samples.get("synced_at"),
        last_error=st.last_error,
        active_job=active,
    )


def mark_all_read() -> MarkAllReadOut:
    cfg = load_config()
    if get_auth_state().phase != AuthPhase.READY and not runtime.session_exists():
        return MarkAllReadOut(
            ok=False,
            message="Сначала синхронизируйте Telegram (вход по телефону)",
        )
    try:
        r = reader.mark_all_read(cfg.blocklist_ids)
        return MarkAllReadOut(
            ok=True,
            marked=r["marked"],
            skipped_blocklist=r["skipped_blocklist"],
            message=r["message"],
        )
    except Exception as e:
        return MarkAllReadOut(ok=False, message=str(e))


async def _run_sync_job(
    job_id: str,
    only_unread: bool,
    run_analyze: bool,
) -> None:
    _jobs[job_id]["status"] = JobStatus.RUNNING.value
    try:
        cfg = load_config()
        chats = await reader.fetch_samples_async(
            cfg.blocklist_ids,
            cfg.sample_hours,
            cfg.sample_limit_per_chat,
            only_unread,
        )
        synced_at = storage.save_samples(chats)
        _jobs[job_id]["progress"] = 50
        _jobs[job_id]["message"] = f"Собрано чатов: {len(chats)}"

        digests: list[dict] = []
        if run_analyze:
            for i, ch in enumerate(chats):
                analysis = await analyzer.analyze_chat(
                    ch["title"],
                    ch["messages"],
                    use_local_llm=cfg.use_local_llm,
                    ollama_base_url=cfg.ollama_base_url,
                    ollama_model=cfg.ollama_model,
                )
                digests.append(
                    {
                        "chat_id": ch["chat_id"],
                        "title": ch["title"],
                        "username": ch.get("username"),
                        "summary": analysis.get("summary", ""),
                        "topics": analysis.get("topics", []),
                        "suggested_replies": analysis.get("suggested_replies", []),
                        "message_count": len(ch["messages"]),
                        "analyzed_at": synced_at,
                        "unread_before": ch.get("unread_count", 0),
                    }
                )
                _jobs[job_id]["progress"] = 50 + int(50 * (i + 1) / max(len(chats), 1))
            storage.save_digests(digests)

        _jobs[job_id]["status"] = JobStatus.DONE.value
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["message"] = "Готово"
    except Exception as e:
        _jobs[job_id]["status"] = JobStatus.ERROR.value
        _jobs[job_id]["error"] = str(e)


def start_sync(only_unread: bool = False, run_analyze: bool = True) -> SyncOut:
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "id": job_id,
        "kind": "sync",
        "status": JobStatus.PENDING.value,
        "progress": 0,
        "message": "Запуск…",
    }

    def _worker() -> None:
        runtime.run_async(_run_sync_job(job_id, only_unread, run_analyze))

    import threading

    threading.Thread(target=_worker, name=f"tg-sync-{job_id}", daemon=True).start()
    return SyncOut(ok=True, job_id=job_id, message="Синхронизация запущена")


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def list_digests() -> DigestsOut:
    data = storage.load_digests()
    samples = storage.load_samples()
    items = []
    for raw in data.get("items", []):
        items.append(
            ChatDigestOut(
                chat_id=raw["chat_id"],
                title=raw["title"],
                username=raw.get("username"),
                summary=raw.get("summary", ""),
                topics=raw.get("topics", []),
                suggested_replies=[
                    SuggestedReply(**r) for r in raw.get("suggested_replies", [])
                ],
                message_count=raw.get("message_count", 0),
                analyzed_at=raw.get("analyzed_at"),
                unread_before=raw.get("unread_before", 0),
            )
        )
    return DigestsOut(items=items, last_sync_at=samples.get("synced_at"))
