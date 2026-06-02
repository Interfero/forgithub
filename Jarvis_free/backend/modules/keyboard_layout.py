"""
Сопоставление латиницы (QWERTY) и кириллицы (ЙЦУКЕН) по позициям клавиш.
Помогает искать пункты меню, если пользователь не переключил раскладку.
"""

from __future__ import annotations

# US QWERTY → русская ЙЦУКЕН (нижний регистр)
# Длины строк должны совпадать (последний символ: / → . на ЙЦУКЕН)
_EN_KEYS = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./"
_RU_KEYS = "ёйцукенгшщзхъфывапролджэячсмитьбю."

if len(_EN_KEYS) != len(_RU_KEYS):
    raise ValueError(f"keyboard layout map length mismatch: {len(_EN_KEYS)} vs {len(_RU_KEYS)}")

_EN_TO_RU = str.maketrans(_EN_KEYS, _RU_KEYS)
_RU_TO_EN = str.maketrans(_RU_KEYS, _EN_KEYS)

# Транслит RU↔LAT (апи→api) — когда термин пишут кириллицей
_RU_TO_LAT_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "j",
    "з": "z",
    "и": "i",
    "й": "j",
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
    "ц": "c",
    "ч": "c",
    "ш": "s",
    "щ": "s",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "u",
    "я": "a",
}

_LAT_TO_RU_MAP = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "ж",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "ы",
    "z": "з",
}


def _norm_letters(s: str) -> str:
    return (s or "").strip().lower().replace("ё", "е")


def ru_to_latin_phonetic(text: str) -> str:
    """Русское написание латинского термина: «апи» → «api»."""
    return "".join(_RU_TO_LAT_MAP.get(ch, ch) for ch in _norm_letters(text))


def latin_to_ru_phonetic(text: str) -> str:
    """Латиница → кириллическое звучание: «api» → «апи»."""
    return "".join(_LAT_TO_RU_MAP.get(ch, ch) for ch in _norm_letters(text))


def en_to_ru_layout(text: str) -> str:
    """Как если бы те же клавиши нажали на русской раскладке."""
    return text.translate(_EN_TO_RU)


def ru_to_en_layout(text: str) -> str:
    """Как если бы те же клавиши нажали на латинской раскладке."""
    return text.translate(_RU_TO_EN)


def search_query_variants(query: str) -> list[str]:
    """
    Варианты запроса: как ввели, с переключением EN→RU и RU→EN.
    Только буквы/символы с клавиатуры; результат в нижнем регистре, ё→е.
    """
    base = _norm_letters(query)
    if not base:
        return []
    variants: set[str] = {base}
    variants.add(_norm_letters(en_to_ru_layout(base)))
    variants.add(_norm_letters(ru_to_en_layout(base)))
    variants.add(_norm_letters(ru_to_latin_phonetic(base)))
    variants.add(_norm_letters(latin_to_ru_phonetic(base)))
    return [v for v in variants if len(v) >= 1]


def text_matches_query(haystack: str, query: str) -> bool:
    """Подстрока с учётом обеих раскладок."""
    h = _norm_letters(haystack)
    if not h:
        return False
    for variant in search_query_variants(query):
        if len(variant) < 1:
            continue
        if variant in h or h in variant:
            return True
    return False
