"""
Нормализация прокси для httpx: socks4 → socks5, отключение trust_env.
"""

from __future__ import annotations

import os

import httpx

_PROXY_ENV_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
)


def normalize_proxy_url(url: str) -> str:
    """socks4 / socks:// из VPN → socks5 (httpx + socksio)."""
    u = (url or "").strip()
    low = u.lower()
    if low.startswith("socks4://"):
        return "socks5://" + u[9:]
    if low.startswith("socks://"):
        return "socks5://" + u[8:]
    return u


def env_proxy_url() -> str | None:
    for key in _PROXY_ENV_KEYS:
        v = (os.environ.get(key) or "").strip()
        if v:
            return normalize_proxy_url(v)
    return None


def httpx_client(
    *,
    timeout: httpx.Timeout | float | None = 45.0,
    proxy: str | None = "__auto__",
    trust_env: bool = False,
) -> httpx.Client:
    """
    httpx.Client без неявного trust_env.
    proxy=__auto__: взять из переменных окружения (нормализовано).
    proxy=None: только прямое соединение.
    """
    kwargs: dict = {"timeout": timeout, "trust_env": trust_env}
    if proxy == "__auto__":
        env = env_proxy_url()
        if env:
            kwargs["proxy"] = env
    elif proxy:
        kwargs["proxy"] = normalize_proxy_url(proxy)
    return httpx.Client(**kwargs)
