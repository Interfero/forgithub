"""
Совместимость: сохранение навыков реализовано в chat_assistant.py.
"""

from __future__ import annotations

from modules.chat_assistant import save_jarvis_skill_code
from modules.skills_runtime import reload_jarvis_skills_module

__all__ = ["save_jarvis_skill_code", "reload_jarvis_skills_module", "skills_file_path"]


def skills_file_path():
    from pathlib import Path

    return Path(__file__).resolve().parent / "jarvis_skills.py"
