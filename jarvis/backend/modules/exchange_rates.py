"""
Курсы валют ЦБ РФ — быстрый ответ без Chromium и Google.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 300  # 5 мин

_CURRENCY_PATTERNS: list[tuple[str, str, str]] = [
    (r"\bдоллар\w*\b|\busd\b|\$", "USD", "доллар США"),
    (r"\bевро\w*\b|\beur\b|€", "EUR", "евро"),
    (r"\bюан\w*\b|\bcny\b|\brmb\b", "CNY", "китайский юань"),
    (r"\bфунт\w*\b|\bgbp\b|£", "GBP", "британский фунт"),
    (r"\bиен\w*\b|\bjpy\b|¥", "JPY", "японская иена"),
    (r"\bтенге\w*\b|\bkzt\b", "KZT", "казахстанский тенге"),
    (r"\bлир\w*\b|\btry\b", "TRY", "турецкая лира"),
]

_RATE_QUERY = re.compile(
    r"(?:"
    r"курс|курсы|стоимость|цена|сколько\s+стоит|обмен|exchange\s+rate|"
    r"сколько\s+(?:сейчас|сегодня)"
    r")",
    re.I,
)


def user_wants_exchange_rate(text: str) -> bool:
    low = (text or "").lower().replace("ё", "е")
    if len(low.strip()) < 6:
        return False
    if not _RATE_QUERY.search(low):
        return False
    return detect_currencies(text) != []


def detect_currencies(text: str) -> list[tuple[str, str]]:
    low = (text or "").lower().replace("ё", "е")
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pattern, code, label in _CURRENCY_PATTERNS:
        if re.search(pattern, low, re.I) and code not in seen:
            seen.add(code)
            found.append((code, label))
    if not found and _RATE_QUERY.search(low):
        found.append(("USD", "доллар США"))
    return found


def _fetch_cbr_json() -> dict[str, Any]:
    from modules.http_proxy import httpx_client

    with httpx_client(timeout=20.0, proxy=None) as client:
        resp = client.get("https://www.cbr-xml-daily.ru/daily_json.js")
        resp.raise_for_status()
        return resp.json()


def get_cbr_rates(*, force: bool = False) -> dict[str, Any]:
    now = time.time()
    with _CACHE_LOCK:
        if not force and _CACHE["data"] and now - float(_CACHE["ts"]) < _CACHE_TTL:
            return _CACHE["data"]
    data = _fetch_cbr_json()
    with _CACHE_LOCK:
        _CACHE["data"] = data
        _CACHE["ts"] = now
    return data


def _format_rate(code: str, label: str, data: dict[str, Any]) -> str | None:
    valute = (data.get("Valute") or {}).get(code)
    if not valute:
        return None
    try:
        nominal = int(valute.get("Nominal") or 1)
        value = float(valute.get("Value") or 0)
        prev = float(valute.get("Previous") or value)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    per_one = value / nominal if nominal > 1 else value
    delta = per_one - (prev / nominal if nominal > 1 else prev)
    sign = "▲" if delta > 0.005 else "▼" if delta < -0.005 else "→"
    date = (data.get("Date") or "")[:10]
    unit = f"{nominal} {code}" if nominal > 1 else f"1 {code}"
    return (
        f"**{label} ({code})** — **{per_one:.4f} ₽** за 1 {code} "
        f"(официально {value:.4f} ₽ за {unit}; {sign} {abs(delta):.4f} ₽ к прошлому дню). "
        f"Дата: {date or 'сегодня'}."
    )


def format_exchange_rate_reply(text: str) -> str:
    currencies = detect_currencies(text)
    if not currencies:
        currencies = [("USD", "доллар США")]
    try:
        data = get_cbr_rates()
    except Exception as e:
        return (
            f"⚠️ Не удалось получить курс ЦБ РФ: {str(e)[:160]}. "
            "Проверьте интернет или повторите позже."
        )

    lines: list[str] = []
    for code, label in currencies[:4]:
        line = _format_rate(code, label, data)
        if line:
            lines.append(line)

    if not lines:
        return "⚠️ ЦБ РФ не вернул данные по запрошенным валютам."

    body = "\n\n".join(lines)
    sources = (
        "\n\n---\n**Источники:**\n"
        "1. [ЦБ РФ — ключевые показатели](https://www.cbr.ru/key-indicators/) ★\n"
        "2. [CBR XML Daily API](https://www.cbr-xml-daily.ru/)"
    )
    return body + sources


def try_handle_exchange_rate(text: str, history: list[dict] | None = None) -> tuple[bool, str]:
    if not user_wants_exchange_rate(text):
        return False, ""
    try:
        from modules.agent import get_runtime

        get_runtime().last_router_intent = "LOCAL_HELP"
        get_runtime().last_router_engine = "cbr_exchange"
        get_runtime().log("exchange", f"Курс ЦБ: «{(text or '')[:80]}»")
    except Exception:
        pass
    return True, format_exchange_rate_reply(text)
