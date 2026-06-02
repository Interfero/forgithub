"""Модели Telegram-Аналитика (режим наблюдателя)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AuthPhase(str, Enum):
    NONE = "none"
    NEED_PHONE = "need_phone"
    NEED_CODE = "need_code"
    NEED_PASSWORD = "need_password"
    READY = "ready"


class JobKind(str, Enum):
    SYNC = "sync"
    ANALYZE = "analyze"
    MARK_READ = "mark_read"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


# --- Auth ---


class AuthStartIn(BaseModel):
    phone: str = Field(..., description="Телефон в международном формате, напр. +79001234567")


class AuthStartOut(BaseModel):
    ok: bool
    phone_code_hash: str | None = None
    message: str = ""


class AuthVerifyIn(BaseModel):
    phone: str
    code: str


class AuthVerifyOut(BaseModel):
    ok: bool
    need_password: bool = False
    message: str = ""


class AuthPasswordIn(BaseModel):
    password: str


# --- Config ---


class AnalystConfigIn(BaseModel):
    blocklist_ids: list[str] = Field(default_factory=list)
    sample_hours: int = Field(24, ge=1, le=168)
    sample_limit_per_chat: int = Field(50, ge=5, le=500)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    use_local_llm: bool = True


class AnalystConfigOut(AnalystConfigIn):
    telethon_installed: bool = False
    credentials_configured: bool = False
    session_exists: bool = False


# --- Operations ---


class MarkAllReadOut(BaseModel):
    ok: bool
    marked: int = 0
    skipped_blocklist: int = 0
    message: str = ""


class SyncIn(BaseModel):
    only_unread: bool = False
    run_analyze: bool = True


class SyncOut(BaseModel):
    ok: bool
    job_id: str
    message: str = ""


class SuggestedReply(BaseModel):
    tone: str
    text: str


class ChatDigestOut(BaseModel):
    chat_id: int
    title: str
    username: str | None = None
    summary: str
    topics: list[str] = Field(default_factory=list)
    suggested_replies: list[SuggestedReply] = Field(default_factory=list)
    message_count: int = 0
    analyzed_at: str | None = None
    unread_before: int = 0


class DigestsOut(BaseModel):
    items: list[ChatDigestOut]
    last_sync_at: str | None = None


class AnalystStatusOut(BaseModel):
    auth_phase: AuthPhase
    auth_message: str = ""
    telethon_installed: bool = False
    credentials_configured: bool = False
    session_exists: bool = False
    last_sync_at: str | None = None
    last_error: str | None = None
    active_job: dict[str, Any] | None = None
