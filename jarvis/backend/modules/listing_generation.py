"""
Генерация текстов объявлений (Авито, Юла, Циан и т.п.) — отдельно от API Авито.
Плейбук: memory/modes/marketer/avito_listing_prompt.txt
"""

from __future__ import annotations

from pathlib import Path

_LISTING_STRONG: tuple[str, ...] = (
    "создай объявление",
    "сгенерируй объявление",
    "напиши объявление",
    "составь объявление",
    "текст объявления",
    "текст для авито",
    "объявление на авито",
    "описание для авито",
    "заголовок для авито",
    "карточку товара",
    "карточку на авито",
    "продаю на авито",
    "продам на авито",
    "объявление для юлы",
    "текст для юлы",
    "описание для циан",
)

_LISTING_WEAK: tuple[str, ...] = (
    "объявлен",
    "авито",
    "юла",
    "циан",
    "заголовок для",
    "описание товар",
    "карточк",
    "seo-текст",
    "утп",
    "копирайт",
)

_LISTING_VERBS: tuple[str, ...] = (
    "создай",
    "напиши",
    "сгенерир",
    "составь",
    "помоги с текст",
    "сделай текст",
    "оформи",
    "подготовь",
)


def wants_listing_generation(text: str) -> bool:
    """Запрос на маркетинговый текст объявления (не API/метрики Авито)."""
    low = (text or "").lower().strip()
    if not low:
        return False
    if any(s in low for s in _LISTING_STRONG):
        return True
    if any(w in low for w in _LISTING_WEAK) and any(v in low for v in _LISTING_VERBS):
        return True
    if "объявлен" in low and any(
        w in low for w in ("текст", "заголов", "описан", "продам", "продаю", "товар")
    ):
        return True
    return False


def _bundle_listing_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "memory"
        / "modes"
        / "marketer"
        / "avito_listing_prompt.txt"
    )


def load_avito_listing_playbook(max_chars: int = 14000) -> str:
    """Текст плейбука из mode-marketer или из вшитого bundle."""
    from modules.memory_store import MODE_MARKETER_DIR, read_file

    path = MODE_MARKETER_DIR / "avito_listing_prompt.txt"
    if path.is_file():
        raw = path.read_text(encoding="utf-8", errors="replace")
    else:
        bundle = _bundle_listing_path()
        raw = bundle.read_text(encoding="utf-8", errors="replace") if bundle.is_file() else ""

    raw = (raw or "").strip()
    if not raw:
        return ""
    if len(raw) > max_chars:
        raw = raw[: max_chars - 20] + "\n…[обрезано]"
    return raw


def listing_system_extra(user_text: str) -> str:
    """Блок для system prompt при генерации объявления."""
    if not wants_listing_generation(user_text):
        return ""
    playbook = load_avito_listing_playbook()
    if not playbook:
        return ""
    return (
        "[Генерация объявления — приоритет]\n"
        "Следуй плейбуку ниже **строго**. Это маркетинговый текст, не API Авито.\n"
        "Если данных мало — **3–5 коротких вопросов**, без готового объявления.\n"
        "Если данных достаточно — выдай формат из плейбука (заголовки, текст, FAQ, SEO).\n"
        "Тело объявления: **800–1200 символов**. Без ссылок и мессенджеров.\n\n"
        f"{playbook}"
    )
