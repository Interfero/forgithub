import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile

from app import db
from app.agent_state import get_agent_state
from app.config import settings
from app.schemas import FileOut
from app.services import rag

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[FileOut])
def list_uploaded_files():
    return [FileOut(**f) for f in db.list_files()]


@router.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "Нет файлов")
    state = get_agent_state()
    state.log("file.upload", f"Загрузка {len(files)} файл(ов)")
    saved: list[FileOut] = []

    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in {".pdf", ".txt", ".docx", ".md"}:
            raise HTTPException(400, f"Формат не поддерживается: {suffix}")

        fid = str(uuid.uuid4())
        dest = settings.files_path / f"{fid}{suffix}"
        content = await upload.read()
        async with aiofiles.open(dest, "wb") as f:
            await f.write(content)

        file_id = db.register_file(upload.filename or dest.name, dest, len(content))
        try:
            chunks = rag.index_file(file_id, upload.filename or dest.name, dest)
            db.mark_file_indexed(file_id)
            state.log("memory.index", f"{upload.filename}: {chunks} чанков в ChromaDB")
            indexed = True
        except Exception as e:
            state.log("memory.index", f"Ошибка индексации {upload.filename}: {e}")
            indexed = False

        saved.append(
            FileOut(
                id=file_id,
                name=upload.filename or dest.name,
                size=len(content),
                indexed=indexed,
            )
        )

    return {"files": saved}
