from fastapi import APIRouter

from app.agent_state import get_agent_state
from app.db import load_settings
from app.schemas import AgentStateOut

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/status", response_model=AgentStateOut)
def agent_status():
    s = get_agent_state()
    cfg = load_settings()
    return AgentStateOut(
        status=s.status,
        session_tokens=s.session_tokens,
        model=s.model or cfg.default_model,
        backend_status="connected",
        tool_logs=s.tool_logs,
    )
