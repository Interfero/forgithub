"""
Импорт ругательств из внешних источников в insult_lexicon и profanity_list.txt.

Источники (клонировать в backend/data/):
  - _tmp_rbw  https://github.com/Vasiliy-Makogon/RussianBadWords
  - _tmp_tg   https://github.com/WhenYouAreStrange/TG-Profanity-Bot
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.insult_lexicon import (
    MAX_LEXICON_SLOTS,
    _normalize,
    bulk_import_phrases,
    ensure_lexicon_ready,
    lexicon_stats_dict,
    reload_lexicon_cache,
)

DATA = ROOT / "data"
RBW_PHP = DATA / "_tmp_rbw" / "dictionaries" / "ProfanityWordsValidator.php"
TG_JSON = DATA / "_tmp_tg" / "profanity_list.json"
TG_TXT = DATA / "_tmp_tg" / "all.txt"
PROFANITY_OUT = DATA / "profanity_list.txt"

_PHP_WORD_RE = re.compile(r"'([^']{2,80})'")
_CYR_RE = re.compile(r"[а-яё]", re.I)


def _parse_php_words(path: Path) -> list[str]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return [w.strip().lower() for w in _PHP_WORD_RE.findall(text) if w.strip()]


def _parse_tg_json(path: Path) -> list[str]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [str(x).strip().lower() for x in data if str(x).strip()]


def _parse_txt(path: Path) -> list[str]:
    if not path.is_file():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        w = line.strip().lower()
        if w and not w.startswith("#"):
            out.append(w)
    return out


def _filter_phrase(w: str) -> bool:
    w = w.strip()
    if len(w) < 3 or len(w) > 80:
        return False
    if _CYR_RE.search(w):
        return True
    # латиница — только явные корни (транслит TG)
    if re.fullmatch(r"[a-z0-9\-]+", w) and len(w) >= 4:
        return True
    return False


def collect_all() -> dict[str, str]:
    """normalized -> original phrase (prefer cyrillic form)."""
    merged: dict[str, str] = {}
    sources = [
        ("rbw", _parse_php_words(RBW_PHP)),
        ("tg_json", _parse_tg_json(TG_JSON)),
        ("tg_txt", _parse_txt(TG_TXT)),
    ]
    for src, words in sources:
        for raw in words:
            if not _filter_phrase(raw):
                continue
            norm = _normalize(raw)
            if not norm:
                continue
            if norm not in merged or (_CYR_RE.search(raw) and not _CYR_RE.search(merged[norm])):
                merged[norm] = raw
    return merged


def write_profanity_file(phrases: dict[str, str], max_lines: int = 2500) -> int:
    """Кириллические слова для moderation rule_engine (консервативный слой)."""
    lines = [
        "# Список мата для ModerationRuleEngine (пополняется import_profanity_lexicon.py)",
        "# Jarvis не использует эти слова в ответах — только распознаёт в речи Шефа.",
    ]
    cyr = sorted({p for p in phrases.values() if _CYR_RE.search(p)}, key=len)
    for w in cyr[:max_lines]:
        lines.append(w)
    PROFANITY_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(cyr[:max_lines])


def main() -> None:
    ensure_lexicon_ready()
    phrases = collect_all()
    print(f"Collected unique phrases: {len(phrases)}")
    items = [(p, "import_rbw" if _CYR_RE.search(p) else "import_tg") for p in phrases.values()]
    stats = bulk_import_phrases(items, max_total=MAX_LEXICON_SLOTS)
    print("Lexicon import:", stats)
    n_prof = write_profanity_file(phrases)
    print(f"profanity_list.txt lines (cyrillic): {n_prof}")
    reload_lexicon_cache()
    print("Final:", lexicon_stats_dict())


if __name__ == "__main__":
    main()
