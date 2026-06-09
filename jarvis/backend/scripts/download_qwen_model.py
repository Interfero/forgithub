#!/usr/bin/env python3
"""Скачать Qwen 2.5 14B (GGUF) в backend/data/models — часть установки Jarvis."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import qwen_embedded as qe  # noqa: E402


def main() -> int:
    def progress(pct: int, msg: str) -> None:
        print(f"[{pct:3d}%] {msg}", flush=True)

    if not qe.llama_importable():
        print(
            "[ПРЕДУПРЕЖДЕНИЕ] llama-cpp-python пока не установлен — "
            "файл модели всё равно скачается; для ответов в ОЗУ нужен start.bat.",
            flush=True,
        )

    app_models = qe.model_path().resolve()
    print(f"Jarvis — загрузка {qe.MODEL_LABEL} Instruct (GGUF Q4_K_M, ~9 ГБ)")
    print("Модель ставится ВНУТРЬ приложения Jarvis, не «просто на компьютер»:")
    print(f"  {app_models}")
    print("(каталог backend/data/models в папке Jarvis — часть установки приложения)")
    print("Рекомендуется от 16 ГБ ОЗУ для комфортной работы 14B на CPU.")
    print()

    result = qe.download_model(on_progress=progress)
    if result.get("ok"):
        print()
        print(result.get("message", "Готово"))
        if result.get("skipped"):
            print("(уже была на диске)")
        return 0
    msg = result.get("message", "Ошибка загрузки")
    print(msg, file=sys.stderr)
    qe.mark_download_error(str(msg)[:240])
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        qe.mark_download_error(f"Сбой загрузки: {str(e)[:200]}")
        raise
