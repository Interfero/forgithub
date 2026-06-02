"""Поиск chrome.exe при «ломаных» PLAYWRIGHT_BROWSERS_PATH."""

from __future__ import annotations

import os
from pathlib import Path


def test_find_chromium_ignores_empty_playwright_browsers_path(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "empty"))
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return
    real_root = Path(local) / "ms-playwright"
    if not any(real_root.glob("chromium-*")):
        return

    from modules.chromium_browser import _find_chromium_executable_path

    found = _find_chromium_executable_path()
    assert found
    assert Path(found).is_file()
    assert "chrome" in Path(found).name.lower()
