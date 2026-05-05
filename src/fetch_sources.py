"""Module 1 — Source fetchers. Each returns list[RawItem]; failures are logged, not raised."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

from .schema import RawItem


# Keyword whitelists used for client-side filtering inside fetchers
# (a stricter pass happens in Module 2).
_KW_EN = ("ai", "llm", "agent", "gpt", "claude", "gemini", "model",
          "rag", "transformer", "diffusion", "ml", "machine learning",
          "neural", "openai", "anthropic")
_KW_DEV = ("ai", "agent", "llm", "gpt", "claude", "developer tool",
           "developer-tool", "automation", "copilot", "ide")
_KW_GH = ("ai", "llm", "agent", "gpt", "claude", "model", "ml",
          "machine learning", "neural", "rag", "transformer", "diffusion")
_KW_CN = ("ai", "人工智能", "大模型", "llm", "gpt", "claude", "gemini")

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


def _matches(text: str, keywords) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


# ---------------------------------------------------------------------------
# Hacker News (Algolia Search API)
# ---------------------------------------------------------------------------

def fetch_hackernews(since_hours: int = 26) -> list[RawItem]:
    """Top AI-related HN stories from the last `since_hours`, points > 50.

    Algolia's `query` is space-separated and ranked by relevance; we use a
    broad `"AI"` query and apply a stricter client-side keyword check
    afterwards (per Yixiao's confirmation).
    """
    cutoff = int(time.time()) - since_hours * 3600
    params = {
        "tags": "story",
        "query": "AI",
        "numericFilters": f"points>50,created_at_i>{cutoff}",
        "hitsPerPage": 50,
    }
    r = requests.get(
        "https://hn.algolia.com/api/v1/search",
        params=params,
        headers={"User-Agent": _USER_AGENT},
        timeout=15,
    )
    r.raise_for_status()
    hits = r.json().get("hits", [])

    items: list[RawItem] = []
    for h in hits:
        title = (h.get("title") or "").strip()
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        if not title or not url:
            continue
        # client-side keyword check (title only — HN stories rarely have summary)
        if not _matches(title, _KW_EN):
            continue

        items.append(RawItem(
            source="hn",
            source_label="Hacker News",
            title=title,
            summary="",  # HN search has no body excerpt
            url=url,
            published_at=h.get("created_at") or datetime.now(timezone.utc).isoformat(),
            score=int(h.get("points") or 0),
        ))
        if len(items) >= 15:
            break
    return items
