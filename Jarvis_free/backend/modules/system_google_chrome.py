"""Совместимость: Chrome Jarvis живёт в modules.jarvis_browsers."""

from modules.jarvis_browsers import (  # noqa: F401
    find_google_chrome_exe,
    find_windowed_chrome_exe,
    google_chrome_installed,
    google_chrome_status,
    install_google_chrome_windows,
    install_windowed_chrome,
    open_jarvis_ui_in_chrome,
    start_auto_install_if_needed,
    warmup_google_chrome_async,
    windowed_chrome_installed,
)
