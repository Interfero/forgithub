"""
Предпочтения Шефа: игры, книги, передачи, YouTube — jarvis.db (namespace user_prefs).
Сопоставление кириллица ↔ латиница для имён игр и медиа.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher

PREFS_NAMESPACE = "user_prefs"

_CATEGORY_LABELS = {
    "game": "игра",
    "book": "книга",
    "show": "передача",
    "youtube": "YouTube",
    "channel": "канал",
    "media": "медиа",
}

# Известные пары (латиница ↔ кириллица) — дополняются при сохранении
_KNOWN_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    ("helldivers 2", "helldivers ii", "helldivers", "хелдайверс 2", "хелдайверс", "хел дайверс", "хелдайвер"),
    ("helldivers", "helldivers 1", "хелдайверс", "хелдайвер"),
    ("steam", "стим", "steampowered", "store.steampowered"),
    ("cyberpunk 2077", "киберпанк", "cyberpunk", "сайберпанк"),
    ("elden ring", "элден ринг", "eldenring"),
    ("baldur's gate 3", "baldurs gate 3", "бaldur", "бaldurs gate", "бaldur's gate"),
)

_REMEMBER_RE = re.compile(
    r"(?:"
    r"запомни(?:\s+что)?|"
    r"сохрани(?:\s+в\s+память)?|"
    r"запиши(?:\s+в\s+память)?|"
    r"добавь(?:\s+в\s+(?:любим|избранн))?"
    r")\s*[:—\-]?\s*(.+)",
    re.I | re.S,
)

_CATEGORY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "game",
        re.compile(
            r"^(?:"
            r"(?:моя\s+)?(?:любимая\s+)?(?:игра|game)(?:\s+сейчас)?|"
            r"(?:я\s+)?(?:играю\s+в|играю|прохожу|прохожу\s+игру)|"
            r"игра\s+(?:называется|это)"
            r")\s*[:—\-]?\s*(.+)$",
            re.I | re.S,
        ),
    ),
    (
        "book",
        re.compile(
            r"^(?:"
            r"(?:моя\s+)?(?:любимая\s+)?(?:книга|book)|"
            r"(?:я\s+)?(?:читаю|читаю\s+книгу)"
            r")\s*[:—\-]?\s*(.+)$",
            re.I | re.S,
        ),
    ),
    (
        "show",
        re.compile(
            r"^(?:"
            r"(?:моя\s+)?(?:любимая\s+)?(?:передача|сериал|фильм|шоу|show|series)"
            r")\s*[:—\-]?\s*(.+)$",
            re.I | re.S,
        ),
    ),
    (
        "youtube",
        re.compile(
            r"^(?:"
            r"(?:любимый\s+)?(?:канал\s+)?(?:на\s+)?(?:youtube|ютуб|ютюб)|"
            r"youtube\s*[-—]?\s*канал"
            r")\s*[:—\-]?\s*(.+)$",
            re.I | re.S,
        ),
    ),
    (
        "channel",
        re.compile(
            r"^(?:"
            r"(?:любимый\s+)?(?:телеграм\s*[-—]?\s*)?канал|"
            r"канал\s+в\s+телеграм"
            r")\s*[:—\-]?\s*(.+)$",
            re.I | re.S,
        ),
    ),
)

_GAME_FOLLOWUP = re.compile(
    r"(?:"
    r"в\s+(?:этой\s+)?игре|"
    r"про\s+(?:неё|нее|игру|босса|моба|класс|билд|миссию|квест)|"
    r"желчн\w*\s+титан|"
    r"bile\s+titan|"
    r"титан|"
    r"босс|"
    r"билд|"
    r"как\s+(?:убить|пройти|фармить|крафт)"
    r")",
    re.I,
)

_LATIN_TO_CYR = str.maketrans(
    {
        "a": "а",
        "b": "б",
        "c": "к",
        "d": "д",
        "e": "е",
        "g": "г",
        "h": "х",
        "i": "и",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "o": "о",
        "p": "п",
        "r": "р",
        "s": "с",
        "t": "т",
        "u": "у",
        "v": "в",
        "x": "кс",
        "y": "й",
        "z": "з",
    }
)


@dataclass
class UserPreference:
    category: str
    canonical: str
    aliases: list[str] = field(default_factory=list)
    url: str = ""
    notes: str = ""

    def slug(self) -> str:
        base = re.sub(r"[^a-z0-9а-яё]+", "_", self.canonical.lower())[:40].strip("_")
        return base or "item"

    def all_names(self) -> list[str]:
        names = [self.canonical, *self.aliases]
        out: list[str] = []
        seen: set[str] = set()
        for n in names:
            k = _norm_key(n)
            if k and k not in seen:
                seen.add(k)
                out.append(n.strip())
        return out


def _norm_key(s: str) -> str:
    t = (s or "").lower().replace("ё", "е")
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _pseudo_cyrillic(s: str) -> str:
    return (s or "").lower().translate(_LATIN_TO_CYR)


def _pseudo_latin(s: str) -> str:
    table = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    out = []
    for ch in (s or "").lower():
        out.append(table.get(ch, ch))
    return "".join(out)


def name_match_score(a: str, b: str) -> float:
    ka, kb = _norm_key(a), _norm_key(b)
    if not ka or not kb:
        return 0.0
    if ka == kb or ka in kb or kb in ka:
        return 1.0
    variants = {
        ka,
        kb,
        _pseudo_cyrillic(ka),
        _pseudo_cyrillic(kb),
        _pseudo_latin(ka),
        _pseudo_latin(kb),
    }
    for va in variants:
        for vb in variants:
            if va == vb or (len(va) >= 4 and len(vb) >= 4 and (va in vb or vb in va)):
                return 0.95
    return SequenceMatcher(None, ka, kb).ratio()


def expand_alias_variants(name: str) -> list[str]:
    """Дополнительные написания для fuzzy-поиска."""
    base = _norm_key(name)
    if not base:
        return []
    variants = {name.strip(), base, _pseudo_cyrillic(base), _pseudo_latin(base)}
    for group in _KNOWN_ALIAS_GROUPS:
        group_norm = [_norm_key(x) for x in group]
        if any(name_match_score(base, g) >= 0.88 for g in group_norm):
            variants.update(group)
            variants.update(group_norm)
    return sorted({v for v in variants if v and len(v) >= 2}, key=len, reverse=True)


def _pref_to_cell_key(pref: UserPreference) -> str:
    return f"{pref.category}_{pref.slug()}"


def _serialize_pref(pref: UserPreference) -> str:
    return json.dumps(asdict(pref), ensure_ascii=False)


def _deserialize_pref(raw: str) -> UserPreference | None:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return UserPreference(
            category=str(data.get("category") or "media"),
            canonical=str(data.get("canonical") or "").strip(),
            aliases=[str(x) for x in (data.get("aliases") or []) if str(x).strip()],
            url=str(data.get("url") or "").strip(),
            notes=str(data.get("notes") or "").strip(),
        )
    except Exception:
        return None


def load_all_preferences() -> list[UserPreference]:
    from modules import jarvis_db

    jarvis_db.init_db()
    rows = jarvis_db.list_cells(namespace=PREFS_NAMESPACE, mode_code=None)
    out: list[UserPreference] = []
    for row in rows:
        pref = _deserialize_pref(row["content"])
        if pref and pref.canonical:
            out.append(pref)
    return out


def save_preference(pref: UserPreference) -> None:
    from modules import jarvis_db

    jarvis_db.init_db()
    aliases = list(dict.fromkeys(pref.aliases + expand_alias_variants(pref.canonical)))
    url = pref.url
    low = _norm_key(pref.canonical)
    if pref.category == "game" and not url:
        if "helldivers" in low or "хелдайвер" in low:
            url = "https://store.steampowered.com/app/553850/"
    pref = UserPreference(
        category=pref.category,
        canonical=pref.canonical,
        aliases=aliases[:24],
        url=url,
        notes=pref.notes,
    )
    jarvis_db.set_cell(
        mode_code=None,
        namespace=PREFS_NAMESPACE,
        cell_key=_pref_to_cell_key(pref),
        content=_serialize_pref(pref),
        source="user_prefs",
    )


def parse_remember_preference(user_text: str) -> UserPreference | None:
    m = _REMEMBER_RE.search(user_text or "")
    if not m:
        return None
    body = m.group(1).strip()
    if len(body) < 2:
        return None

    for category, pat in _CATEGORY_PATTERNS:
        cm = pat.match(body)
        if cm:
            canonical = cm.group(1).strip().strip(".")
            canonical = re.sub(r"\s+", " ", canonical)
            if len(canonical) < 2:
                return None
            return UserPreference(
                category=category,
                canonical=canonical[:120],
                aliases=expand_alias_variants(canonical)[:16],
            )

    # «запомни: Helldivers 2» без категории — если похоже на игру
    low = body.lower()
    if any(w in low for w in ("игра", "game", "steam", "стим", "прохожу", "играю")):
        name = re.sub(r"(?i)(?:игра|game)\s*[:—\-]?\s*", "", body).strip()
        if len(name) >= 2:
            return UserPreference(
                category="game",
                canonical=name[:120],
                aliases=expand_alias_variants(name)[:16],
            )
    return None


def try_handle_remember_preference(user_text: str) -> tuple[bool, str]:
    pref = parse_remember_preference(user_text)
    if not pref:
        return False, ""

    save_preference(pref)
    cat = _CATEGORY_LABELS.get(pref.category, pref.category)
    alias_preview = ", ".join(pref.aliases[:6])
    lines = [
        f"Запомнил **{cat}**: **{pref.canonical}**.",
        "",
        f"Буду понимать и латиницу, и кириллицу: {alias_preview}.",
    ]
    if pref.category == "game":
        lines.append("")
        lines.append(
            "Можешь спрашивать «желчный титан», «хелдайверс», «helldivers» — "
            "свяжу с этой игрой. Для интернета подключу **Steam** и стереотипы."
        )
    lines.append("")
    lines.append(
        "Ещё: **запомни: любимая книга …** · **запомни: канал на ютуб …** · "
        "**запомни: любимая передача …**"
    )
    return True, "\n".join(lines)


def find_preferences_in_text(text: str, *, min_score: float = 0.82) -> list[tuple[UserPreference, str, float]]:
    prefs = load_all_preferences()
    if not prefs or not (text or "").strip():
        return []

    blob = _norm_key(text)
    tokens = re.findall(r"[a-z0-9а-яё]{3,}", blob)
    found: list[tuple[UserPreference, str, float]] = []

    for pref in prefs:
        best_name = ""
        best_score = 0.0
        for name in pref.all_names():
            nk = _norm_key(name)
            if nk in blob:
                score = 1.0
            else:
                score = max(
                    (name_match_score(tok, name) for tok in tokens),
                    default=0.0,
                )
                if len(nk) >= 5:
                    score = max(score, name_match_score(blob, name))
            if score > best_score:
                best_score = score
                best_name = name
        if best_score >= min_score:
            found.append((pref, best_name, best_score))

    found.sort(key=lambda x: -x[2])
    return found


def _detect_active_game_from_history(history: list[dict] | None) -> str:
    for msg in reversed(history or []):
        if msg.get("role") != "user":
            continue
        hits = find_preferences_in_text(msg.get("content") or "", min_score=0.85)
        for pref, _, score in hits:
            if pref.category == "game" and score >= 0.85:
                return pref.canonical
    return ""


def enrich_user_text_with_preferences(
    user_text: str,
    history: list[dict] | None = None,
) -> str:
    """Подмешать контекст игр/медиа; кириллица ↔ латиница."""
    from modules.dialog_session import get_dialog_session
    from modules.agent import get_runtime
    from modules.operation_stream import append_thinking

    raw = (user_text or "").strip()
    if not raw:
        return raw

    sess = get_dialog_session(get_runtime())
    hints: list[str] = []

    hits = find_preferences_in_text(raw, min_score=0.82)
    for pref, matched, score in hits[:3]:
        label = _CATEGORY_LABELS.get(pref.category, pref.category)
        hints.append(
            f"«{matched}» → **{pref.canonical}** ({label}, совпадение {int(score * 100)}%)"
        )
        if pref.category == "game":
            sess["active_game"] = pref.canonical
            sess["last_topic"] = pref.canonical

    active = (sess.get("active_game") or "").strip()
    if not hits and active and _GAME_FOLLOWUP.search(raw):
        hints.append(
            f"Короткий игровой вопрос без названия — активная игра сессии: **{active}**"
        )
        append_thinking(f"Игра сессии: «{active}» для «{raw[:48]}…»")
    elif not active:
        active = _detect_active_game_from_history(history)
        if active and _GAME_FOLLOWUP.search(raw):
            sess["active_game"] = active
            hints.append(f"Из истории чата: речь про игру **{active}**")
            append_thinking(f"История → игра «{active}»")

    if not hints:
        return raw

    append_thinking("Предпочтения: " + "; ".join(h[:60] for h in hints))
    block = "[Контекст предпочтений Шефа]\n" + "\n".join(f"- {h}" for h in hints)
    block += (
        "\n\nОтвечай про эту игру/медиа; не проси заново полное название, "
        "если совпадение уже найдено. Для фактов из интернета — web_research / Steam."
    )
    return f"{block}\n\n{raw}"


def preferences_prompt_block(*, max_items: int = 12) -> str:
    prefs = load_all_preferences()
    if not prefs:
        return (
            "Пока пусто. Шеф может написать: **запомни: любимая игра Helldivers 2**, "
            "**запомни: книга …**, **запомни: канал на ютуб …** — сохранится навсегда в jarvis.db.\n"
            "Имена игр понимай и на кириллице, и на латинице (хелдайверс = Helldivers)."
        )
    lines = [
        "Используй при ответах; сопоставляй кириллицу и латиницу.",
        "Короткий игровой вопрос без названия — опирайся на «активную игру» сессии.",
        "",
    ]
    for pref in prefs[:max_items]:
        cat = _CATEGORY_LABELS.get(pref.category, pref.category)
        aliases = ", ".join(pref.aliases[:8])
        line = f"• **{pref.canonical}** ({cat})"
        if aliases:
            line += f" — также: {aliases}"
        if pref.url:
            line += f" · {pref.url}"
        if pref.notes:
            line += f" · {pref.notes}"
        lines.append(line)
    return "\n".join(lines)


def preferences_layer_instruction() -> str:
    return (
        "\n\n[Предпочтения Шефа]\n"
        "Игры, книги, передачи, YouTube — в блоке ниже и в jarvis.db.\n"
        "«хелдайверс» / «Helldivers» / «helldivers 2» — одна сущность, если сохранено.\n"
        "«желчный титан», «билд», «босс» без названия игры — продолжай тему активной игры сессии.\n"
        "Новое: **запомни: любимая игра …** · **запомни: книга …** · **запомни: канал на ютуб …**\n"
    )
