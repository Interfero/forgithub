#!/usr/bin/env python3
"""Установка XTTS-v2 в backend/data/tts (часть Jarvis)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import voice as voice_module  # noqa: E402


def main() -> int:
    voice_module.ensure_coqui_inside_jarvis()
    ok, err = voice_module._python_ok_for_xtts()
    if not ok:
        print(f"[ОШИБКА] {err}", file=sys.stderr)
        return 1

    w, hint = voice_module.xtts_weights_in_jarvis()
    if w:
        print(f"Веса XTTS уже в Jarvis: {hint or 'backend/data/tts'}")
        if voice_module._check_xtts_importable():
            print("Библиотеки TTS тоже установлены.")
            return 0
        print("Докачиваем Python-пакеты (torch, TTS)…")

    print("Jarvis — XTTS-v2 → backend/data/tts (~1.8 ГБ весов + библиотеки)")
    result = voice_module.start_xtts_download()
    print(result.get("message", ""))
    if result.get("status") == "error":
        print(result.get("error", ""), file=sys.stderr)
        return 1
    if result.get("already_installed"):
        return 0
    print("Установка запущена в фоне. Следите в Настройках → Голос или перезапустите Jarvis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
