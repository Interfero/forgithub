from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["openai", "anthropic", "openrouter", "ollama"]
AgentStatus = Literal["IDLE", "Thinking...", "Searching Web..."]
BackendStatus = Literal["connected", "disconnected", "connecting"]
MessageRole = Literal["user", "assistant"]


class ToolLogEntry(BaseModel):
    id: str
    timestamp: str
    tool: str
    message: str


class MessageOut(BaseModel):
    id: str
    role: MessageRole
    content: str
    created_at: str


class ChatOut(BaseModel):
    id: str
    title: str
    updated_at: str
    messages: list[MessageOut] = Field(default_factory=list)


class ChatCreate(BaseModel):
    title: str = "Новый диалог"


class ChatUpdate(BaseModel):
    title: str


class SendMessageIn(BaseModel):
    content: str


class AppSettings(BaseModel):
    provider: Provider = "openai"
    openai_key: str = ""
    anthropic_key: str = ""
    openrouter_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "gpt-4o-mini"


class AgentStateOut(BaseModel):
    status: AgentStatus = "IDLE"
    session_tokens: int = 0
    model: str = ""
    backend_status: BackendStatus = "connected"
    tool_logs: list[ToolLogEntry] = Field(default_factory=list)


class HealthOut(BaseModel):
    ok: bool = True
    version: str = "0.2.0"


class FileOut(BaseModel):
    id: str
    name: str
    size: int
    indexed: bool
