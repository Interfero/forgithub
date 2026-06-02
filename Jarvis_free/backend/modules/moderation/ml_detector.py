"""
Слой 2: ML-классификатор агрессии.
Сейчас — заглушка (score=0); интерфейс готов для RuBERT/toxicity в будущем.
"""

from __future__ import annotations

import logging
import time
from typing import Protocol

_log = logging.getLogger("jarvis.moderation.ml")


class MLDetector(Protocol):
    def predict(self, text: str) -> float: ...

    def warmup(self) -> None: ...


class MLDetectorStub:
    """Консервативная заглушка: не помечает сообщения (минимум ложных срабатываний)."""

    def __init__(self) -> None:
        self._ready = False

    def warmup(self) -> None:
        self._ready = True
        _log.info("MLDetectorStub: прогрев (score всегда 0.0)")

    def predict(self, text: str) -> float:
        _ = text
        return 0.0


_detector: MLDetectorStub | None = None


def get_ml_detector() -> MLDetectorStub:
    global _detector
    if _detector is None:
        _detector = MLDetectorStub()
    return _detector


def predict_aggression_score(text: str) -> float:
    start = time.perf_counter()
    try:
        return get_ml_detector().predict(text)
    except Exception:
        _log.exception("MLDetector: ошибка predict — пропускаем слой ML")
        return 0.0
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms > 50:
            _log.warning("MLDetector.predict медленный: %.1f ms", elapsed_ms)


def warmup_ml_detector() -> None:
    get_ml_detector().warmup()
