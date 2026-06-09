from __future__ import annotations


def search_web(query: str, max_results: int = 5) -> list[dict]:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": r.get("body", r.get("snippet", "")),
            }
            for r in results
        ]
    except Exception as e:
        return [{"title": "Ошибка поиска", "url": "", "snippet": str(e)}]
