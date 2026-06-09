"""
Компиляция и запуск кода внутри Jarvis (изолированный каталог workspace/compile).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from modules.app_paths import user_data_dir

_MAX_SOURCE_BYTES = 512_000
_DEFAULT_TIMEOUT = 120
_MAX_TIMEOUT = 300

LANG_BY_SUFFIX = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".bat": "batch",
    ".cmd": "batch",
    ".ps1": "powershell",
}


def workspace_dir() -> Path:
    d = user_data_dir() / "workspace" / "compile"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def detect_language(source: str, filename: str = "", language: str = "") -> str:
    lang = (language or "").strip().lower()
    if lang:
        aliases = {
            "py": "python",
            "python3": "python",
            "node": "javascript",
            "nodejs": "javascript",
            "js": "javascript",
            "ts": "typescript",
            "c++": "cpp",
            "csharp": "csharp",
            "c#": "csharp",
            "ps": "powershell",
            "pwsh": "powershell",
            "sh": "shell",
            "bash": "shell",
        }
        return aliases.get(lang, lang)
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in LANG_BY_SUFFIX:
            return LANG_BY_SUFFIX[ext]
    src = (source or "").lstrip()
    if src.startswith("#!"):
        line = src.split("\n", 1)[0].lower()
        if "python" in line:
            return "python"
        if "node" in line:
            return "javascript"
        if "pwsh" in line or "powershell" in line:
            return "powershell"
        if "bash" in line or "sh" in line:
            return "shell"
    return "python"


def _truncate_output(text: str, limit: int = 16_000) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n… (вывод обрезан)"


def _run_process(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env or os.environ.copy(),
        )
        elapsed = round(time.time() - started, 2)
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": _truncate_output(proc.stdout),
            "stderr": _truncate_output(proc.stderr),
            "elapsed_sec": elapsed,
            "command": " ".join(argv),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": _truncate_output(getattr(e, "stdout", "") or ""),
            "stderr": _truncate_output((getattr(e, "stderr", "") or "") + f"\nТаймаут {timeout} с."),
            "elapsed_sec": timeout,
            "command": " ".join(argv),
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Команда не найдена: {argv[0]}",
            "elapsed_sec": 0,
            "command": " ".join(argv),
        }


def compile_and_run(
    source: str,
    *,
    language: str = "",
    filename: str = "",
    run_after_compile: bool = True,
    timeout: int = _DEFAULT_TIMEOUT,
    stdin_data: str = "",
) -> dict[str, Any]:
    if not (source or "").strip():
        raise ValueError("Пустой исходный код.")
    if len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
        raise ValueError(f"Лимит исходника: {_MAX_SOURCE_BYTES // 1024} КБ.")

    lang = detect_language(source, filename, language)
    timeout = max(5, min(int(timeout or _DEFAULT_TIMEOUT), _MAX_TIMEOUT))
    work = workspace_dir() / f"run_{int(time.time())}_{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)

    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "java": ".java",
        "c": ".c",
        "cpp": ".cpp",
        "csharp": ".cs",
        "go": ".go",
        "rust": ".rs",
        "batch": ".bat",
        "powershell": ".ps1",
        "shell": ".sh",
    }
    ext = Path(filename).suffix if filename else ext_map.get(lang, ".txt")
    if not ext or ext == ".txt":
        ext = ext_map.get(lang, ".txt")
    src_name = Path(filename).name if filename else f"main{ext}"
    src_path = work / src_name
    src_path.write_text(source, encoding="utf-8")

    steps: list[dict[str, Any]] = []
    artifacts: list[str] = []

    def step(name: str, result: dict[str, Any]) -> bool:
        steps.append({"step": name, **result})
        return bool(result.get("ok"))

    py = sys.executable

    if lang == "python":
        if run_after_compile:
            r = _run_process([py, str(src_path)], cwd=work, timeout=timeout)
            step("run", r)
        else:
            r = _run_process([py, "-m", "py_compile", str(src_path)], cwd=work, timeout=timeout)
            step("py_compile", r)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "javascript":
        node = _which("node")
        if not node:
            return _fail(lang, "Node.js не найден в PATH. Установите Node.js или используйте Python.")
        if run_after_compile:
            r = _run_process([node, str(src_path)], cwd=work, timeout=timeout)
            step("run", r)
        else:
            r = _run_process([node, "--check", str(src_path)], cwd=work, timeout=timeout)
            step("syntax_check", r)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "typescript":
        tsc = _which("tsc")
        node = _which("node")
        if not tsc:
            return _fail(lang, "TypeScript (tsc) не найден. npm install -g typescript")
        r = _run_process([tsc, str(src_path), "--outDir", str(work)], cwd=work, timeout=timeout)
        if not step("compile", r):
            return _pack_result(lang, src_path, steps, artifacts, work)
        js_out = work / (src_path.stem + ".js")
        if js_out.is_file():
            artifacts.append(str(js_out))
        if run_after_compile and node and js_out.is_file():
            r2 = _run_process([node, str(js_out)], cwd=work, timeout=timeout)
            step("run", r2)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "java":
        javac = _which("javac")
        java = _which("java")
        if not javac:
            return _fail(lang, "javac не найден. Установите JDK.")
        r = _run_process([javac, str(src_path)], cwd=work, timeout=timeout)
        if not step("compile", r):
            return _pack_result(lang, src_path, steps, artifacts, work)
        class_name = src_path.stem
        artifacts.append(str(work / f"{class_name}.class"))
        if run_after_compile and java:
            r2 = _run_process([java, "-cp", str(work), class_name], cwd=work, timeout=timeout)
            step("run", r2)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "c":
        cc = _which("gcc") or _which("clang")
        if not cc:
            return _fail(lang, "gcc/clang не найден.")
        out_exe = work / (src_path.stem + (".exe" if platform.system() == "Windows" else ""))
        r = _run_process([cc, str(src_path), "-O2", "-o", str(out_exe)], cwd=work, timeout=timeout)
        if not step("compile", r):
            return _pack_result(lang, src_path, steps, artifacts, work)
        artifacts.append(str(out_exe))
        if run_after_compile and out_exe.is_file():
            r2 = _run_process([str(out_exe)], cwd=work, timeout=timeout)
            step("run", r2)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "cpp":
        cxx = _which("g++") or _which("clang++")
        if not cxx:
            return _fail(lang, "g++/clang++ не найден.")
        out_exe = work / (src_path.stem + (".exe" if platform.system() == "Windows" else ""))
        r = _run_process([cxx, str(src_path), "-O2", "-o", str(out_exe)], cwd=work, timeout=timeout)
        if not step("compile", r):
            return _pack_result(lang, src_path, steps, artifacts, work)
        artifacts.append(str(out_exe))
        if run_after_compile and out_exe.is_file():
            r2 = _run_process([str(out_exe)], cwd=work, timeout=timeout)
            step("run", r2)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "csharp":
        csc = _which("csc")
        dotnet = _which("dotnet")
        if dotnet:
            proj = work / "App.csproj"
            proj.write_text(
                '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
                "<OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>"
                "</PropertyGroup></Project>",
                encoding="utf-8",
            )
            r = _run_process(["dotnet", "run", "--project", str(proj)], cwd=work, timeout=timeout)
            step("dotnet_run", r)
            return _pack_result(lang, src_path, steps, artifacts, work)
        if csc:
            out_exe = work / (src_path.stem + ".exe")
            r = _run_process([csc, "/nologo", str(src_path), f"/out:{out_exe}"], cwd=work, timeout=timeout)
            step("compile", r)
            if out_exe.is_file():
                artifacts.append(str(out_exe))
            return _pack_result(lang, src_path, steps, artifacts, work)
        return _fail(lang, "Нужен dotnet SDK или csc в PATH.")

    if lang == "go":
        go = _which("go")
        if not go:
            return _fail(lang, "go не найден в PATH.")
        if run_after_compile:
            r = _run_process([go, "run", str(src_path)], cwd=work, timeout=timeout)
            step("go_run", r)
        else:
            r = _run_process([go, "build", "-o", str(work / "main"), str(src_path)], cwd=work, timeout=timeout)
            step("go_build", r)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "rust":
        rustc = _which("rustc")
        if not rustc:
            return _fail(lang, "rustc не найден.")
        out_exe = work / ("main.exe" if platform.system() == "Windows" else "main")
        r = _run_process([rustc, str(src_path), "-O", "-o", str(out_exe)], cwd=work, timeout=timeout)
        step("compile", r)
        if out_exe.is_file():
            artifacts.append(str(out_exe))
        if run_after_compile and out_exe.is_file():
            r2 = _run_process([str(out_exe)], cwd=work, timeout=timeout)
            step("run", r2)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "batch":
        r = _run_process(["cmd", "/c", str(src_path)], cwd=work, timeout=timeout)
        step("run", r)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "powershell":
        pwsh = _which("pwsh") or _which("powershell")
        if not pwsh:
            return _fail(lang, "PowerShell не найден.")
        r = _run_process([pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(src_path)], cwd=work, timeout=timeout)
        step("run", r)
        return _pack_result(lang, src_path, steps, artifacts, work)

    if lang == "shell":
        bash = _which("bash") or _which("sh")
        if not bash:
            return _fail(lang, "bash/sh не найден.")
        r = _run_process([bash, str(src_path)], cwd=work, timeout=timeout)
        step("run", r)
        return _pack_result(lang, src_path, steps, artifacts, work)

    return _fail(lang, f"Язык «{lang}» не поддерживается.")


def _fail(language: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "language": language,
        "error": message,
        "steps": [],
        "artifacts": [],
        "workdir": "",
    }


def _pack_result(
    language: str,
    src_path: Path,
    steps: list[dict[str, Any]],
    artifacts: list[str],
    work: Path,
) -> dict[str, Any]:
    ok = all(s.get("ok") for s in steps) if steps else False
    return {
        "ok": ok,
        "language": language,
        "source": str(src_path),
        "workdir": str(work),
        "steps": steps,
        "artifacts": artifacts,
    }


def format_run_result(data: dict[str, Any]) -> str:
    if data.get("error"):
        return f"❌ {data['error']}"
    lines = [
        f"Язык: {data.get('language')}",
        f"Каталог: {data.get('workdir')}",
        f"Исходник: {data.get('source')}",
    ]
    for s in data.get("steps") or []:
        status = "OK" if s.get("ok") else "ERR"
        lines.append(f"\n[{status}] {s.get('step')}: {s.get('command', '')}")
        if s.get("stdout"):
            lines.append(f"stdout:\n{s['stdout']}")
        if s.get("stderr"):
            lines.append(f"stderr:\n{s['stderr']}")
    if data.get("artifacts"):
        lines.append("\nАртефакты:")
        for a in data["artifacts"]:
            lines.append(f"  • {a}")
    lines.append(f"\nИтог: {'успех' if data.get('ok') else 'ошибка'}")
    return "\n".join(lines)


def supported_languages_help() -> str:
    return (
        "Языки: python, javascript (node), typescript (tsc), java, c, cpp, csharp (dotnet/csc), "
        "go, rust, batch, powershell, shell.\n"
        "Инструмент: code_compile_run. Навык: compile_and_run_code."
    )
