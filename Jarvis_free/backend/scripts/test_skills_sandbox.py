"""Быстрая проверка песочницы jarvis_skills."""
from modules.code_editor import save_jarvis_skill_code
from modules.skills_runtime import list_custom_skill_methods, run_custom_skill

r = save_jarvis_skill_code("class CustomSkills\n  bad indent")
assert r["status"] == "error", r

code = '''"""
Песочница кастомных навыков Jarvis.
"""
class CustomSkills:
    @staticmethod
    def ping_skills():
        return "OK sandbox"

    @staticmethod
    def echo_test(msg: str = "") -> str:
        return f"echo: {msg}"
'''
r2 = save_jarvis_skill_code(code)
assert r2["status"] == "success", r2
print("methods:", list_custom_skill_methods())
print("run:", run_custom_skill("echo_test", "hi"))
print("OK")
