"""
Стандартный отчёт «проверка систем» Jarvis — по живым индикаторам, без выдумок LLM.
Структура совпадает с меню Настроек и панелью индикаторов (не устаревшие названия).
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

_HEALTH_MARKER = "<!-- jarvis-health-report -->"

_SYSTEM_CHECK = re.compile(
    r"(?:"
    r"провер\w*(?:\s+.{0,30})?(?:систем|jarvis|компонент|сервис|индикатор)|"
    r"диагност\w*(?:\s+.{0,20})?(?:jarvis|систем)?|"
    r"статус\s+(?:систем|компонент|jarvis|индикатор)|"
    r"(?:какие|что)\s+(?:из\s+)?(?:систем|компонент).{0,25}(?:не\s+)?работа|"
    r"отч[её]т\s+о\s+(?:состояни|проверк).{0,20}систем"
    r")",
    re.I,
)


def is_health_report_message(content: str) -> bool:
    return _HEALTH_MARKER in (content or "")


def parse_system_health_request(text: str) -> bool:
    raw = (text or "").strip()
    if len(raw) > 300:
        return False
    return bool(_SYSTEM_CHECK.search(raw))


def _icon(level: str) -> str:
    return {"ok": "🟢", "warn": "🟡", "err": "🔴", "off": "⚪"}.get(level, "⚪")


def _esc(text: str, limit: int = 140) -> str:
    s = html.escape((text or "—").replace("\n", " ").strip())
    if len(s) <= limit:
        return s
    cut = s[:limit]
    if " " in cut[80:]:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _short_voice_detail(detail: str) -> str:
    s = detail.strip()
    if len(s) <= 120:
        return s
    if "temp_build" in s or "TTS" in s:
        return "Ошибка сборки/копирования XTTS (см. логи start.bat)"
    return s[:117] + "…"


def _section_table(title: str, rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return ""
    body = []
    for level, name, detail in rows:
        d = _short_voice_detail(detail) if "озвучк" in name.lower() or "xtts" in name.lower() else detail
        body.append(
            "<tr>"
            f'<td class="jh-status">{_icon(level)}</td>'
            f'<td class="jh-name">{_esc(name, 48)}</td>'
            f'<td class="jh-detail">{_esc(d, 120)}</td>'
            "</tr>"
        )
    return (
        f'<section class="jh-section">'
        f'<h3 class="jh-section-title">{html.escape(title)}</h3>'
        '<table class="jh-table">'
        "<colgroup>"
        '<col class="jh-col-status" />'
        '<col class="jh-col-name" />'
        '<col class="jh-col-detail" />'
        "</colgroup>"
        "<thead><tr>"
        '<th class="jh-status">Статус</th>'
        '<th class="jh-name">Компонент</th>'
        '<th class="jh-detail">Состояние</th>'
        "</tr></thead>"
        f"<tbody>{''.join(body)}</tbody>"
        "</table></section>"
    )


def build_system_health_report() -> str:
    from modules.health_report_rows import collect_health_report_sections

    sections = collect_health_report_sections()
    all_rows: list[tuple[str, str, str]] = []
    for key in (
        "core",
        "readiness",
        "api_keys",
        "telegram",
        "avito",
        "telephony",
        "mail",
        "voice",
        "session",
    ):
        all_rows.extend(sections.get(key) or [])

    ok_n = sum(1 for lv, _, _ in all_rows if lv == "ok")
    warn_n = sum(1 for lv, _, _ in all_rows if lv == "warn")
    err_n = sum(1 for lv, _, _ in all_rows if lv == "err")
    off_n = sum(1 for lv, _, _ in all_rows if lv == "off")

    ts = datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")

    if err_n > 0:
        verdict_class = "jh-verdict-err"
        verdict = f"Есть ошибки ({err_n} компонент с 🔴). Нужны действия."
    elif warn_n > 0:
        verdict_class = "jh-verdict-warn"
        verdict = f"Есть замечания ({warn_n} компонент с 🟡). Остальное работает."
    elif ok_n >= 3:
        verdict_class = "jh-verdict-ok"
        verdict = "Всё в норме — критических сбоев нет."
    else:
        verdict_class = "jh-verdict-info"
        verdict = "Часть сервисов не настроена — см. строки с ⚪."

    sections_html = "".join(
        [
            _section_table("🧠 Ядро Jarvis", sections["core"]),
            _section_table("📊 Линейки готовности (экран аватара)", sections["readiness"]),
            _section_table("☁️ API-ключи", sections["api_keys"]),
            _section_table("✈️ Коннектор Телеграм", sections["telegram"]),
            _section_table("🟢 Коннектор Авито", sections["avito"]),
            _section_table("📞 Jarvis-ATS", sections["telephony"]),
            _section_table("📬 Почтовый клиент", sections["mail"]),
            _section_table("🎙️ Голос и озвучка", sections["voice"]),
            _section_table("💬 Сессия и память", sections["session"]),
        ]
    )

    footer_hint = ""
    if err_n or warn_n:
        footer_hint = (
            '<p class="jh-hint">Те же блоки, что в <strong>Настройках</strong> и на '
            "<strong>панели индикаторов</strong> — напишите, что настроить, подскажу шаги.</p>"
        )

    report_html = (
        f"{_HEALTH_MARKER}"
        '<div class="jarvis-health-report">'
        '<header class="jh-header">'
        "<h2>🛡️ Проверка систем Jarvis</h2>"
        f'<p class="jh-meta">Снимок индикаторов: <strong>{html.escape(ts)}</strong> · '
        "меню Настроек и панель статуса</p>"
        "</header>"
        f"{sections_html}"
        '<section class="jh-verdict">'
        '<h3 class="jh-section-title">📋 Итоговый статус</h3>'
        f'<div class="jh-verdict-box {verdict_class}">'
        f'<p class="jh-verdict-text">{html.escape(verdict)}</p>'
        f'<p class="jh-verdict-stats">Сводка: 🟢 {ok_n} · 🟡 {warn_n} · 🔴 {err_n} · '
        f"⚪ {off_n} · всего {len(all_rows)}</p>"
        "</div>"
        '<p class="jh-legend">🟢 работает · 🟡 частично / загрузка · 🔴 ошибка · '
        "⚪ выкл. или не настроено.</p>"
        f"{footer_hint}"
        "</section>"
        "</div>"
    )

    return report_html


def try_handle_system_health(user_text: str) -> tuple[bool, str]:
    if not parse_system_health_request(user_text):
        return False, ""
    return True, build_system_health_report()
