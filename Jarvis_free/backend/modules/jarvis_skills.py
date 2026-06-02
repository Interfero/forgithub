"""
Песочница навыков Jarvis — вызывается через run_jarvis_skill / save_jarvis_skill_code.
"""


class CustomSkills:
    @staticmethod
    def ping_skills() -> str:
        return "Система кастомных навыков активна и готова к расширению!"

    @staticmethod
    def sync_avito_chats_month() -> str:
        """Синхронизировать чаты и сообщения Авито за последние 30 дней."""
        from modules.avito_chat_analytics import sync_chats_for_period

        r = sync_chats_for_period(days=30, max_chats=500, messages_per_chat=500)
        return (
            f"Синхронизация за {r.get('days')} дн.: "
            f"{r.get('chats_saved', 0)} чатов, {r.get('messages_saved', 0)} сообщений."
        )

    @staticmethod
    def analyze_avito_chats_month() -> str:
        """Анализ переписок за месяц (собеседование, адрес, телефон)."""
        from modules.avito_chat_analytics import analyze_chats, format_analysis_report

        data = analyze_chats(days=30)
        return format_analysis_report(data)

    @staticmethod
    def run_avito_chat_pipeline() -> str:
        """Синхронизация + анализ чатов за 30 дней."""
        from modules.avito_chat_analytics import run_full_pipeline

        r = run_full_pipeline(days=30)
        return r.get("report", "Готово.")

    @staticmethod
    def purge_avito_chat(chat_id: str) -> str:
        """Удалить переписку чата из локального архива (после выгрузки)."""
        from modules.avito_chat_analytics import purge_chat_archive

        r = purge_chat_archive(str(chat_id).strip())
        return (
            f"Чат {r['chat_id']}: удалено сообщений {r['messages_deleted']}, "
            f"карточка чата {'удалена' if r['chat_deleted'] else 'не найдена'}."
        )

    @staticmethod
    def add_insult_lexicon(phrase: str) -> str:
        """Добавить слово или фразу в словарь оскорблений Jarvis (jarvis.db, до 10 000 слотов)."""
        from modules.insult_lexicon import add_lexicon_entry

        ok, msg = add_lexicon_entry(str(phrase).strip(), source="skill")
        return msg if ok else f"Ошибка: {msg}"

    @staticmethod
    def insult_lexicon_stats() -> str:
        """Статистика словаря оскорблений (активные записи и свободные слоты)."""
        from modules.insult_lexicon import lexicon_stats

        return lexicon_stats()

    @staticmethod
    def fetch_url(url: str) -> str:
        """Открыть URL во встроенном Chromium Jarvis (headless)."""
        from modules.web_search import fetch_url_text

        u = str(url or "").strip()
        if not u.lower().startswith(("http://", "https://")):
            return "Ошибка: укажите полный URL (https://…)."
        return fetch_url_text(u, max_chars=12_000)

    @staticmethod
    def analyze_page_seo(url: str, question: str = "") -> str:
        """
        Разбор страницы: SEO, дизайн, функционал, сложность разработки.
        Одна ссылка в ответе — из аргумента url.
        """
        from modules.page_seo_audit import build_page_audit_reply
        from modules.url_page_handler import _fetch_page_safe

        u = str(url or "").strip()
        if not u.lower().startswith(("http://", "https://")):
            return "Ошибка: укажите полный URL (https://…)."
        raw = _fetch_page_safe(u, max_chars=12_000)
        return build_page_audit_reply(u, raw, str(question or ""))

    @staticmethod
    def show_page_content(url: str) -> str:
        """Показать текст страницы (без сжатия)."""
        from modules.url_page_handler import _fetch_page_safe
        from modules.page_seo_audit import build_page_audit_reply

        u = str(url or "").strip()
        if not u.lower().startswith(("http://", "https://")):
            return "Ошибка: укажите полный URL (https://…)."
        raw = _fetch_page_safe(u, max_chars=14_000)
        return build_page_audit_reply(u, raw, full_text=True)

    @staticmethod
    def browse_page(url: str) -> str:
        """Синоним fetch_url — открыть страницу и вернуть текст."""
        return CustomSkills.fetch_url(url)

    @staticmethod
    def web_search(query: str) -> str:
        """Поиск DuckDuckGo (сниппеты)."""
        from modules.web_search import search_web_text

        return search_web_text(str(query or "").strip(), max_results=5)
