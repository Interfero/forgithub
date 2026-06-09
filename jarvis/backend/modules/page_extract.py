"""
Извлечение читаемого текста со страницы (без сырого HTML в чат).
Спец-логика для 2ГИС и похожих карт.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from modules.web_search import _html_to_plain

_HTML_MARKERS = re.compile(
    r"<\s*(?:html|head|body|script|style|div|meta|link)\b",
    re.I,
)

_REFUSAL_PHRASES = re.compile(
    r"зайдите\s+сами|откройте\s+(?:эту\s+)?(?:страниц|ссылк)|"
    r"в\s+браузере\s+сам|перейдите\s+на\s+сайт|"
    r"не\s+могу\s+определить|не\s+удастся\s+определить|"
    r"if you have the opportunity to open",
    re.I,
)

_ORG_COUNT_Q = re.compile(
    r"сколько|скольк|число|количеств|сколько\s+организа|"
    r"сколько\s+фирм|сколько\s+компан|организаци.*в\s+(?:этом\s+)?здан",
    re.I,
)

_PAGE_DISPUTE_RE = re.compile(
    r"обман|врёш|вреш|неправильн|не\s+то\s+число|"
    r"больше\s+организа|меньше\s+организа|"
    r"пересчитай|ещё\s+раз|еще\s+раз|проверь\s+ещ|"
    r"ты\s+ошиб|ты\s+неправ",
    re.I,
)

_FIRM_NAME_SKIP = re.compile(
    r"^(показать|ещё|еще|все|на\s+карте|2гис|поиск|меню|войти|"
    r"маршрут|поделиться|добавить|фильтр|сортиров)",
    re.I,
)


_2GIS_BROWSER_WALL = re.compile(
    r"рекомендуем\s+обновить\s+браузер|не\s+самый\s+новый\s+браузер|"
    r"polyfills\.min\.js|document\.write\s*\(|"
    r"пропустить\s+обновление|Outdated\s+Browser",
    re.I,
)


def looks_like_html(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    from modules.chromium_stealth import _HTML_IN_TEXT

    if _HTML_IN_TEXT.search(s):
        return True
    if _HTML_MARKERS.search(s[:8000]):
        return True
    if s.count("<") >= 3 and s.count(">") >= 3:
        return True
    return False


def is_2gis_browser_wall(text: str) -> bool:
    return bool(_2GIS_BROWSER_WALL.search(text or ""))


def to_plain_text(text: str, *, limit: int = 12_000) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    if looks_like_html(s):
        s = _html_to_plain(s, limit=limit)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s


def sanitize_chat_text(text: str, *, limit: int = 12_000) -> str:
    """В чат — только человекочитаемый текст."""
    s = to_plain_text(text, limit=limit)
    if is_2gis_browser_wall(s):
        return ""
    return s


def try_dismiss_2gis_browser_wall(page) -> bool:
    """Клик «Пропустить обновление» / переход к карте."""
    try:
        clicked = page.evaluate(
            """() => {
                const texts = /пропустить|перейти\\s+к\\s*2\\s*гис|skip|continue/i;
                const nodes = [...document.querySelectorAll('a, button, [role="button"]')];
                for (const el of nodes) {
                    const t = (el.innerText || el.textContent || '').trim();
                    if (texts.test(t)) { el.click(); return true; }
                }
                const link = document.querySelector('a[href*="2gis"], a[href*="skip"]');
                if (link) { link.click(); return true; }
                return false;
            }"""
        )
        if clicked:
            page.wait_for_timeout(2500)
        return bool(clicked)
    except Exception:
        return False


def message_for_2gis_wall(url: str) -> str:
    return (
        f"**По ссылке** {url}\n\n"
        "2ГИС показал заглушку «обновите браузер» — встроенный headless Chromium они "
        "режут, это **не** нехватка плагинов.\n\n"
        "Jarvis попробует системный **Google Chrome** при следующем запросе "
        "(перезапустите `restart.bat`, если Chrome установлен).\n\n"
        "Либо откройте полную ссылку на здание с **2gis.ru** (не go.2gis.com) "
        "и пришлите её снова."
    )


def is_map_heavy_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return any(x in host for x in ("2gis.", "go.2gis", "yandex.ru/maps", "google.com/maps"))


def browse_wait_ms(url: str, default: int = 2_500) -> int:
    if is_map_heavy_url(url):
        return 14_000
    return default


def user_asks_org_count(user_text: str) -> bool:
    return bool(_ORG_COUNT_Q.search(user_text or ""))


def user_disputes_page_answer(user_text: str) -> bool:
    """Шеф сомневается в прошлом ответе по ссылке — открыть страницу заново."""
    return bool(_PAGE_DISPUTE_RE.search(user_text or ""))


def summary_refuses_to_answer(text: str) -> bool:
    return bool(_REFUSAL_PHRASES.search(text or ""))


def format_2gis_extract(data: dict[str, Any]) -> str:
    lines: list[str] = []
    title = str(data.get("title") or "").strip()
    if title:
        lines.append(f"Заголовок: {title}")
    addr = str(data.get("address") or "").strip()
    if addr:
        lines.append(f"Адрес: {addr}")
    ui_n = int(data.get("ui_org_count") or 0)
    firms: list[str] = data.get("firms") or []
    firms = [str(f).strip() for f in firms if str(f).strip()]
    count = max(len(firms), ui_n) if ui_n else len(firms)
    if ui_n and ui_n != len(firms):
        lines.append(
            f"На странице указано: {ui_n}; в подгруженном списке ссылок: {len(firms)}"
        )
    if firms:
        lines.append(f"Организации в каталоге ({count}):")
        for i, name in enumerate(firms[:60], 1):
            lines.append(f"  {i}. {name[:120]}")
        if len(firms) > 60:
            lines.append(f"  … и ещё {len(firms) - 60}")
    visible = str(data.get("visible_text") or "").strip()
    if visible and len(visible) > 30:
        lines.append("\nВидимый текст:\n" + visible[:6000])
    return "\n".join(lines).strip()


def scroll_2gis_catalog(page) -> None:
    """Прокрутка списка организаций — без неё 2ГИС отдаёт ~10 карточек."""
    try:
        page.evaluate(
            """async () => {
                const pickScrollable = () => {
                    const candidates = [
                        ...document.querySelectorAll(
                            '[class*="scroll"], [class*="catalog"], [class*="list"], [class*="panel"]'
                        ),
                        document.querySelector('main'),
                        document.querySelector('[role="main"]'),
                    ].filter(Boolean);
                    for (const el of candidates) {
                        if (el.scrollHeight > el.clientHeight + 80) return el;
                    }
                    return document.scrollingElement || document.documentElement;
                };
                const el = pickScrollable();
                for (let i = 0; i < 14; i++) {
                    el.scrollTop = el.scrollHeight;
                    window.scrollTo(0, document.body.scrollHeight);
                    await new Promise((r) => setTimeout(r, 550));
                }
            }"""
        )
        page.wait_for_timeout(1200)
    except Exception:
        pass


def extract_2gis_from_page(page) -> dict[str, Any]:
    try:
        return page.evaluate(
            """() => {
                const out = {
                    title: document.title || '',
                    address: '',
                    firms: [],
                    ui_org_count: 0,
                    visible_text: '',
                };
                const skip = /^(показать|ещё|еще|все|на карте|2гис|поиск|меню|войти|маршрут|поделиться|добавить|фильтр)/i;
                const addrEl = document.querySelector('[data-address]');
                if (addrEl) out.address = addrEl.getAttribute('data-address') || '';
                const bodyText = (document.body.innerText || '').replace(/\\s+/g, ' ');
                const cnt = bodyText.match(/(\\d+)\\s*(?:организаций|организации|мест|компаний|фирм\\b|компании)/i);
                if (cnt) out.ui_org_count = parseInt(cnt[1], 10) || 0;
                const names = new Set();
                document.querySelectorAll(
                    'a[href*="/firm/"], a[href*="/branches/"], a[href*="firmId"], a[href*="/station/"]'
                ).forEach((a) => {
                    let t = (a.innerText || a.textContent || '').trim().replace(/\\s+/g, ' ');
                    if (t.length < 3 || t.length > 180 || skip.test(t)) return;
                    if (/^\\d+$/.test(t)) return;
                    names.add(t);
                });
                out.firms = [...names].slice(0, 200);
                const main = document.querySelector('main, [role="main"], #root');
                out.visible_text = (main ? main.innerText : document.body.innerText || '').slice(0, 6000);
                return out;
            }"""
        )
    except Exception:
        return {
            "title": "",
            "address": "",
            "firms": [],
            "ui_org_count": 0,
            "visible_text": "",
        }


def wait_for_map_page(page, url: str) -> None:
    if not is_map_heavy_url(url):
        return
    selectors = (
        "[data-address]",
        "a[href*='/firm/']",
        "[class*='firm']",
        "[class*='card']",
        "main",
    )
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=8_000)
            return
        except Exception:
            continue


def extract_page_text(page, url: str, *, max_chars: int = 12_000) -> tuple[str, str]:
    """Возвращает (plain_text, title)."""
    title = (page.title() or "").strip()
    if is_map_heavy_url(url):
        try_dismiss_2gis_browser_wall(page)
        wait_for_map_page(page, url)
        scroll_2gis_catalog(page)
        data = extract_2gis_from_page(page)
        scroll_2gis_catalog(page)
        data2 = extract_2gis_from_page(page)
        if len(data2.get("firms") or []) > len(data.get("firms") or []):
            data = data2
        text = format_2gis_extract(data)
        if len(text) < 50:
            try:
                raw = (page.inner_text("body") or "").strip()
            except Exception:
                raw = ""
            text = sanitize_chat_text(raw, limit=max_chars)
        else:
            text = sanitize_chat_text(text, limit=max_chars)
        if is_2gis_browser_wall(text) or (not text and raw):
            return "", title
        return text, title

    try:
        body = (page.inner_text("body") or "").strip()
    except Exception:
        body = (page.content() or "")[:max_chars]

    plain = sanitize_chat_text(body, limit=max_chars)
    return plain, title


def _parse_org_count_from_page_text(page_text: str) -> tuple[int, list[str]]:
    """Число организаций и имена из форматированного extract."""
    names = re.findall(r"^\s*\d+\.\s+(.+)$", page_text or "", re.M)
    m = re.search(r"Организации в каталоге \((\d+)\)", page_text or "")
    if m:
        return int(m.group(1)), names
    m = re.search(r"в подгруженном списке ссылок:\s*(\d+)", page_text or "")
    ui_m = re.search(r"На странице указано:\s*(\d+)", page_text or "")
    n = len(names)
    if m:
        n = max(n, int(m.group(1)))
    if ui_m:
        n = max(n, int(ui_m.group(1)))
    return n, names


def answer_org_count_from_page(
    user_text: str,
    url: str,
    page_text: str,
    *,
    recount: bool = False,
) -> str | None:
    """Ответ «сколько организаций» по данным Chromium (с оговоркой про ленивую подгрузку)."""
    if not user_asks_org_count(user_text) and not recount:
        return None
    n, names = _parse_org_count_from_page_text(page_text)
    if n <= 0 and not names:
        return None
    addr_m = re.search(r"Адрес:\s*(.+)", page_text or "")
    addr = addr_m.group(1).strip() if addr_m else ""

    head = f"**По ссылке** {url}\n\n"
    if recount:
        head += (
            "Перепроверил страницу (прокрутил каталог заново). "
            "Обманывать не собирался — headless-окно могло увидеть меньше, чем ваш браузер.\n\n"
        )
    if addr:
        head += f"**Адрес:** {addr}\n\n"

    if n == 0:
        return (
            head
            + "Список организаций в этой сессии не подгрузился. "
            "Пришлите прямую ссылку с **2gis.ru** на здание (не только go.2gis.com)."
        )

    head += (
        f"В подгруженном каталоге Chromium насчитал **{n}** "
        f"{'организацию' if n == 1 else 'организации' if 2 <= n <= 4 else 'организаций'}"
    )
    if names:
        show = names[:25]
        head += ":\n" + "\n".join(f"- {x}" for x in show)
        if len(names) > 25:
            head += f"\n- … ещё {len(names) - 25}"
    head += (
        "\n\n_Если у вас в браузере число больше — 2ГИС мог не отдать весь список "
        "автоматическому окну; тогда ориентируйтесь на свой экран._"
    )
    return head
