"""
Антидетект для headless Chromium / системного Chrome (Playwright).
2ГИС и др. отсекают «устаревший браузер» без этих настроек.
"""

from __future__ import annotations

import re
from typing import Any

STEALTH_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  } catch (e) {}
  try {
    delete navigator.__proto__.webdriver;
  } catch (e) {}
  try {
    window.chrome = window.chrome || { runtime: {}, loadTimes: function(){}, csi: function(){} };
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'plugins', {
      get: () => [1, 2, 3, 4, 5],
    });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'languages', {
      get: () => ['ru-RU', 'ru', 'en-US', 'en'],
    });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
  } catch (e) {}
  try {
    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
  } catch (e) {}
  try {
    const brands = [
      { brand: 'Chromium', version: '131' },
      { brand: 'Google Chrome', version: '131' },
      { brand: 'Not_A Brand', version: '24' },
    ];
    Object.defineProperty(navigator, 'userAgentData', {
      get: () => ({
        brands,
        mobile: false,
        platform: 'Windows',
        getHighEntropyValues: async () => ({
          architecture: 'x86',
          bitness: '64',
          brands,
          fullVersionList: brands,
          mobile: false,
          model: '',
          platform: 'Windows',
          platformVersion: '10.0.0',
        }),
      }),
    });
  } catch (e) {}
  try {
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
      parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
  } catch (e) {}
})();
"""


def realistic_chrome_user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )


def chromium_launch_args() -> list[str]:
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-infobars",
        "--window-size=1920,1080",
        "--lang=ru-RU",
        "--disable-features=IsolateOrigins,site-per-process",
    ]


def system_browser_channel() -> str | None:
    """Не используем channel=chrome (системный Windows). Только exe внутри Jarvis."""
    return None


def chromium_launch_kwargs(
    *,
    prefer_system_chrome: bool = False,
    windowed: bool = False,
) -> dict[str, Any]:
    """Параметры launch через executable_path в Jarvis/browsers."""
    from modules.jarvis_browsers import (
        find_headless_chromium_exe,
        find_windowed_chrome_exe,
    )

    del prefer_system_chrome
    exe = find_windowed_chrome_exe() if windowed else find_headless_chromium_exe()
    if windowed and not exe:
        raise RuntimeError(
            "Chrome Jarvis не установлен. start.bat или install-google-chrome.bat."
        )
    kw: dict[str, Any] = {
        "headless": not windowed,
        "ignore_default_args": ["--enable-automation"],
        "args": chromium_launch_args(),
    }
    if exe:
        kw["executable_path"] = exe
    return kw


def browser_context_options() -> dict[str, Any]:
    return {
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
        "user_agent": realistic_chrome_user_agent(),
        "viewport": {"width": 1920, "height": 1080},
        "screen": {"width": 1920, "height": 1080},
        "device_scale_factor": 1,
        "color_scheme": "light",
        "java_script_enabled": True,
        "extra_http_headers": {
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
        },
    }


def apply_stealth_to_context(context) -> None:
    context.add_init_script(STEALTH_INIT_SCRIPT)


def apply_stealth_to_page(page) -> None:
    page.add_init_script(STEALTH_INIT_SCRIPT)


def strip_chromium_wrapper(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    lines = s.splitlines()
    while lines and (
        lines[0].startswith("**Встроенный Chromium")
        or lines[0].startswith("URL:")
        or lines[0].startswith("Заголовок:")
        or lines[0].strip() == ""
    ):
        lines.pop(0)
    while lines and (
        lines[-1].startswith("_Страница открыта")
        or lines[-1].startswith("_Загрузка через HTTP")
        or lines[-1].strip() == ""
    ):
        lines.pop()
    return "\n".join(lines).strip()


_HTML_IN_TEXT = re.compile(r"<\s*script|</\s*script|document\.write\s*\(", re.I)
