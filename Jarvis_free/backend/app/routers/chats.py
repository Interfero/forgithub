import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app import db
from app.schemas import ChatCreate, ChatOut, ChatUpdate, MessageOut, SendMessageIn
from app.services.agent import run_agent

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=list[ChatOut])
def list_chats():
    return db.list_chats()


@router.post("", response_model=ChatOut)
def create_chat(body: ChatCreate | None = None):
    title = body.title if body else "Новый диалог"
    return db.create_chat(title)


@router.patch("/{chat_id}", response_model=ChatOut)
def update_chat(chat_id: str, body: ChatUpdate):
    chat = db.update_chat(chat_id, body.title.strip() or "Без названия")
    if not chat:
        raise HTTPException(404, "Чат не найден")
    return chat


@router.delete("/{chat_id}")
def remove_chat(chat_id: str):
    if not db.delete_chat(chat_id):
        raise HTTPException(404, "Чат не найден")
    return {"ok": True}


async def _sse_stream(chat_id: str, content: str) -> AsyncIterator[str]:
    async for event in run_agent(chat_id, content):
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/{chat_id}/messages")
async def send_message(chat_id: str, body: SendMessageIn):
    chats = db.list_chats()
    if not any(c.id == chat_id for c in chats):
        raise HTTPException(404, "Чат не найден")
    if not body.content.strip():
        raise HTTPException(400, "Пустое сообщение")

    return StreamingResponse(
        _sse_stream(chat_id, body.content.strip()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
