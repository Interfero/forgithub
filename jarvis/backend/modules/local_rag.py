"""
Локальный поиск по загруженным документам — top-K чанков без полного текста в LLM.
"""

from __future__ import annotations

from pathlib import Path

from modules.local_text_utils import chunk_text, search_top_chunks


def search_in_text(
    query: str,
    text: str,
    *,
    source: str = "",
    top_k: int = 3,
    chunk_size: int = 900,
) -> list[dict]:
    chunks = chunk_text(text, chunk_size=chunk_size)
    hits = search_top_chunks(query, chunks, top_k=top_k)
    return [
        {
            "source": source,
            "chunk_index": idx,
            "score": round(score, 3),
            "text": chunk.strip(),
        }
        for idx, chunk, score in hits
        if chunk.strip()
    ]


def search_uploaded_files(
    query: str,
    file_paths: list[Path | str],
    *,
    top_k: int = 3,
    max_read_chars: int = 80_000,
) -> list[dict]:
    from modules.document_tools import read_document

    q = (query or "").strip()
    all_hits: list[dict] = []

    for fp in file_paths:
        p = Path(fp)
        if not p.is_file():
            continue
        try:
            doc = read_document(str(p), max_chars=max_read_chars)
            text = doc.get("content") or ""
        except Exception:
            continue
        if not text.strip():
            continue
        hits = search_in_text(q, text, source=p.name, top_k=top_k)
        all_hits.extend(hits)

    all_hits.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_hits[:top_k]


def format_rag_results(hits: list[dict], *, query: str = "") -> str:
    if not hits:
        if query.strip():
            return f"_По запросу «{query[:80]}» релевантных фрагментов не найдено._"
        return "_Локальные документы не загружены или текст не извлечён._"

    lines = ["**Релевантные фрагменты (локальный поиск, top-3):**", ""]
    for i, h in enumerate(hits, 1):
        src = h.get("source") or "документ"
        score = h.get("score", 0)
        text = (h.get("text") or "").strip()
        lines.append(f"### {i}. {src} (score {score})")
        lines.append(text)
        lines.append("")
    lines.append("_Полный файл — `doc_read`; кратко — `doc_read` с `summarize: true`._")
    return "\n".join(lines).strip()
