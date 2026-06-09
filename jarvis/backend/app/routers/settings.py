from fastapi import APIRouter

from app import db
from app.schemas import AppSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return key
    return key[:7] + "••••••••"


def _is_masked(value: str) -> bool:
    return "•" in value


@router.get("", response_model=AppSettings)
def get_settings():
    s = db.load_settings()
    return AppSettings(
        provider=s.provider,
        openai_key=_mask_key(s.openai_key) if s.openai_key else "",
        anthropic_key=_mask_key(s.anthropic_key) if s.anthropic_key else "",
        openrouter_key=_mask_key(s.openrouter_key) if s.openrouter_key else "",
        ollama_base_url=s.ollama_base_url,
        default_model=s.default_model,
    )


@router.put("", response_model=AppSettings)
def put_settings(body: AppSettings):
    current = db.load_settings()
    merged = AppSettings(
        provider=body.provider,
        openai_key=body.openai_key if not _is_masked(body.openai_key) else current.openai_key,
        anthropic_key=body.anthropic_key if not _is_masked(body.anthropic_key) else current.anthropic_key,
        openrouter_key=body.openrouter_key if not _is_masked(body.openrouter_key) else current.openrouter_key,
        ollama_base_url=body.ollama_base_url,
        default_model=body.default_model,
    )
    db.save_settings(merged)
    return get_settings()
