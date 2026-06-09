"""
Динамическая загрузка песочницы jarvis_skills и каталог методов для промпта.
"""

from __future__ import annotations

import importlib
from typing import Any


def reload_jarvis_skills_module():
    """Перезагрузить modules.jarvis_skills без рестарта FastAPI."""
    from modules import jarvis_skills

    return importlib.reload(jarvis_skills)


def list_custom_skill_methods() -> list[str]:
    mod = reload_jarvis_skills_module()
    methods: list[str] = []
    for name in dir(mod.CustomSkills):
        if name.startswith("_"):
            continue
        attr = getattr(mod.CustomSkills, name, None)
        if callable(attr):
            methods.append(name)
    return sorted(set(methods))


def run_custom_skill(method: str, *args: Any, **kwargs: Any) -> str:
    """Вызвать @staticmethod CustomSkills по имени."""
    mod = reload_jarvis_skills_module()
    name = (method or "").strip()
    if not name or name.startswith("_"):
        raise ValueError("Недопустимое имя метода.")
    fn = getattr(mod.CustomSkills, name, None)
    if fn is None or not callable(fn):
        raise ValueError(f"Метод CustomSkills.{name} не найден.")
    result = fn(*args, **kwargs)
    return str(result) if result is not None else ""


def skills_context_for_prompt() -> str:
    """Краткий каталог навыков для системного промпта."""
    try:
        mod = reload_jarvis_skills_module()
        ping = mod.CustomSkills.ping_skills()
        methods = list_custom_skill_methods()
    except Exception as e:
        return f"Песочница навыков: ошибка загрузки ({e})."

    lines = [
        "---",
        "[Песочница навыков — modules/jarvis_skills.py]",
        f"Статус: {ping}",
        "Методы CustomSkills: " + (", ".join(methods) if methods else "(нет)"),
        "Перезапись файла: инструмент save_jarvis_skill_code (полный текст файла с class CustomSkills).",
        "Проверка: jarvis_skills_ping. Список: list_jarvis_skills. Вызов: run_jarvis_skill.",
    ]
    try:
        from modules.hf_skills_store import enabled_skills_context

        lines.append("")
        lines.append(enabled_skills_context())
    except Exception:
        pass
    return "\n".join(lines)
