"""Module 1 — Source fetchers. Each returns list[RawItem]; failures are logged, not raised."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

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
    """Case-insensitive keyword match with word-boundary semantics.

    - Strips dots so "A.I." becomes "ai" (and matches `\\bai\\b`).
    - Treats `-`/`_`/`/` as separators.
    - Single-token keywords match with a word boundary, optionally allowing a
      common plural suffix (model/models, agent/agents).
    - Phrases with spaces fall back to plain substring.
    """
    t = text.lower()
    t = re.sub(r"\.", "", t)
    t = re.sub(r"[_/\-]+", " ", t)
    for kw in keywords:
        if " " in kw:
            if kw in t:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}(?:s|es)?\b", t):
                return True
    return False


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


# ---------------------------------------------------------------------------
# Product Hunt (Atom feed)
# ---------------------------------------------------------------------------

def fetch_producthunt() -> list[RawItem]:
    """Latest PH launches filtered by AI / dev-tool keywords."""
    feed = feedparser.parse(
        "https://www.producthunt.com/feed",
        request_headers={"User-Agent": _USER_AGENT},
    )
    items: list[RawItem] = []
    for e in feed.entries:
        title = (e.get("title") or "").strip()
        url = (e.get("link") or "").strip()
        summary = (e.get("summary") or "").strip()
        if not title or not url:
            continue
        if not _matches(title + " " + summary, _KW_DEV):
            continue

        # Atom feeds use `published` or `updated`; both already ISO-8601 in PH
        published = e.get("published") or e.get("updated") or datetime.now(timezone.utc).isoformat()

        items.append(RawItem(
            source="producthunt",
            source_label="Product Hunt",
            title=title,
            summary=summary[:400],
            url=url,
            published_at=published,
            score=0,  # PH feed exposes no vote count
        ))
        if len(items) >= 10:
            break
    return items


# ---------------------------------------------------------------------------
# GitHub Trending (HTML scrape — no official API)
# ---------------------------------------------------------------------------

_GH_TRENDING_PAGES = (
    "https://github.com/trending/python?since=daily",
    "https://github.com/trending/javascript?since=daily",
    "https://github.com/trending?since=daily",
)


def _parse_int(s: str) -> int:
    digits = "".join(c for c in s if c.isdigit())
    return int(digits) if digits else 0


def _scrape_trending_page(url: str) -> list[tuple[str, str, int]]:
    """Return list of (full_name, description, total_stars) from one trending page."""
    r = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    out: list[tuple[str, str, int]] = []
    for box in soup.select("article.Box-row"):
        a = box.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        full_name = a["href"].lstrip("/").strip()
        desc_el = box.select_one("p")
        desc = desc_el.get_text(strip=True) if desc_el else ""
        star_el = box.select_one('a[href$="/stargazers"]')
        stars = _parse_int(star_el.get_text(strip=True)) if star_el else 0
        out.append((full_name, desc, stars))
    return out


def fetch_github_trending() -> list[RawItem]:
    """Trending repos from python/javascript/all daily pages, AI keyword filter, top 10."""
    seen: set[str] = set()
    all_repos: list[tuple[str, str, int]] = []
    for page in _GH_TRENDING_PAGES:
        try:
            repos = _scrape_trending_page(page)
        except Exception as exc:
            print(f"[github] page failed {page}: {exc}")
            continue
        for full_name, desc, stars in repos:
            if full_name in seen:
                continue
            seen.add(full_name)
            all_repos.append((full_name, desc, stars))

    matched = [r for r in all_repos if _matches((r[0] + " " + r[1]), _KW_GH)]
    matched.sort(key=lambda r: r[2], reverse=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    items: list[RawItem] = []
    for full_name, desc, stars in matched[:10]:
        items.append(RawItem(
            source="github",
            source_label="GitHub Trending",
            title=full_name,
            summary=desc[:400],
            url=f"https://github.com/{full_name}",
            published_at=today,
            score=stars,
        ))
    return items
