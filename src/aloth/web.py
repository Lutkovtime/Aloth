"""Web search tool — read-only, no API keys (DuckDuckGo via ddgs)."""

from __future__ import annotations

from ddgs import DDGS


def web_search(query: str, limit: int = 5) -> str:
    """Search the web; returns title+url per result."""
    try:
        results = DDGS().text(query, max_results=limit)
    except Exception as e:  # noqa: BLE001 — network errors are expected
        return f"ошибка поиска: {e}"
    if not results:
        return "ничего не найдено"
    return "\n".join(
        f"- {r.get('title', '')} — {r.get('href', '')}" for r in results
    )


if __name__ == "__main__":  # pragma: no cover — network self-check
    out = web_search("python asyncio", limit=2)
    assert "http" in out
    print(out)
