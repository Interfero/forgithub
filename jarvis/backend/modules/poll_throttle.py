"""
Троттлинг опросов коннекторов и backoff при недоступности backend.
"""

from __future__ import annotations

import time
import threading

CONNECTOR_INTERVAL_KEYED_SEC = 1.0
CONNECTOR_INTERVAL_UNKEYED_SEC = 60.0

_lock = threading.Lock()
_ollama_cache: tuple[bool, bool, str | None, str | None] | None = None
_ollama_cache_at = 0.0


def connector_interval_sec(keys_configured: bool) -> float:
    return CONNECTOR_INTERVAL_KEYED_SEC if keys_configured else CONNECTOR_INTERVAL_UNKEYED_SEC


def get_cached_ollama_status(
    *,
    keys_configured: bool,
    probe,
) -> tuple[bool, bool, str | None, str | None]:
    """Не чаще 1 с (ключи есть) или 60 с (ключей нет)."""
    global _ollama_cache, _ollama_cache_at
    interval = connector_interval_sec(keys_configured)
    now = time.time()
    with _lock:
        if _ollama_cache is not None and (now - _ollama_cache_at) < interval:
            return _ollama_cache
    result = probe()
    with _lock:
        _ollama_cache = result
        _ollama_cache_at = now
    return result


def invalidate_ollama_cache() -> None:
    global _ollama_cache, _ollama_cache_at
    with _lock:
        _ollama_cache = None
        _ollama_cache_at = 0.0
