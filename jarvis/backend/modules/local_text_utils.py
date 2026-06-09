"""
Локальная обработка текста без LLM: чанки, поиск, extractive-суммаризация.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_RU_STOP = frozenset(
    {
        "и",
        "в",
        "на",
        "с",
        "по",
        "для",
        "к",
        "у",
        "о",
        "от",
        "до",
        "из",
        "что",
        "как",
        "это",
        "не",
        "но",
        "а",
        "же",
        "ли",
        "бы",
        "то",
        "все",
        "всё",
        "его",
        "её",
        "их",
        "мы",
        "вы",
        "он",
        "она",
        "они",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "to",
        "of",
        "in",
        "on",
        "for",
    }
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[\wа-яё]+", (text or "").lower()) if len(t) > 1]


def chunk_text(text: str, *, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        if end >= n:
            break
        start = max(0, end - overlap)
    return chunks


def _bm25_score(query_terms: list[str], doc_terms: list[str], *, avg_dl: float, df: Counter, n_docs: int) -> float:
    if not query_terms or not doc_terms:
        return 0.0
    k1, b = 1.2, 0.75
    tf = Counter(doc_terms)
    dl = len(doc_terms)
    score = 0.0
    for term in set(query_terms):
        if term in _RU_STOP:
            continue
        freq = tf.get(term, 0)
        if freq == 0:
            continue
        idf = math.log(1 + (n_docs - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
        denom = freq + k1 * (1 - b + b * dl / max(avg_dl, 1))
        score += idf * (freq * (k1 + 1)) / max(denom, 1e-9)
    return score


def search_top_chunks(
    query: str,
    chunks: list[str],
    *,
    top_k: int = 3,
) -> list[tuple[int, str, float]]:
    """BM25-подобный поиск релевантных фрагментов."""
    if not chunks:
        return []
    q_terms = tokenize(query)
    if not q_terms:
        return [(i, c, 0.0) for i, c in enumerate(chunks[:top_k])]

    doc_tokens = [tokenize(c) for c in chunks]
    df: Counter = Counter()
    for terms in doc_tokens:
        for t in set(terms):
            df[t] += 1
    n_docs = len(chunks)
    avg_dl = sum(len(t) for t in doc_tokens) / max(n_docs, 1)

    scored: list[tuple[int, str, float]] = []
    for i, (chunk, terms) in enumerate(zip(chunks, doc_tokens)):
        scored.append((i, chunk, _bm25_score(q_terms, terms, avg_dl=avg_dl, df=df, n_docs=n_docs)))
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[: max(1, top_k)]


def extractive_summarize(text: str, *, max_sentences: int = 5, max_chars: int = 2500) -> str:
    """Краткое изложение без нейросети — по частоте значимых слов."""
    raw = (text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars and raw.count(".") + raw.count("!") + raw.count("?") <= max_sentences:
        return raw[:max_chars]

    sentences = re.split(r"(?<=[.!?…])\s+", raw)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    if not sentences:
        return raw[:max_chars]

    word_freq: Counter = Counter()
    for s in sentences:
        for w in tokenize(s):
            if w not in _RU_STOP:
                word_freq[w] += 1

    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        terms = [w for w in tokenize(s) if w not in _RU_STOP]
        if not terms:
            continue
        score = sum(word_freq[w] for w in terms) / len(terms)
        if i == 0:
            score *= 1.15
        scored.append((score, i, s))

    if not scored:
        return raw[:max_chars]

    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = sorted(scored[:max_sentences], key=lambda x: x[1])
    out = " ".join(s for _, _, s in picked)
    return out[:max_chars]
