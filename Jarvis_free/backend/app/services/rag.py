from __future__ import annotations

from pathlib import Path

import chromadb

from app.config import settings
from app.services.file_parser import chunk_text, extract_text

_collection = None


def _collection_client():
    global _collection
    if _collection is None:
        settings.data_path.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(settings.data_path / "chroma"))
        _collection = client.get_or_create_collection(
            name="jarvis_docs",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index_file(file_id: str, filename: str, path: Path) -> int:
    text = extract_text(path)
    chunks = chunk_text(text)
    if not chunks:
        return 0
    col = _collection_client()
    ids = [f"{file_id}_{i}" for i in range(len(chunks))]
    documents = chunks
    metadatas = [{"file_id": file_id, "filename": filename, "chunk": i} for i in range(len(chunks))]
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


def search(query: str, n_results: int = 5) -> list[dict]:
    col = _collection_client()
    if col.count() == 0:
        return []
    res = col.query(query_texts=[query], n_results=min(n_results, max(1, col.count())))
    out: list[dict] = []
    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    dists = res.get("distances") or [[]]
    for doc, meta, dist in zip(docs[0], metas[0], dists[0]):
        out.append(
            {
                "text": doc,
                "filename": (meta or {}).get("filename", "?"),
                "distance": dist,
            }
        )
    return out
