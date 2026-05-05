"""Entry point — fetch all sources and print per-source counts.

Usage:
    python src/main.py
    python src/main.py --dry-run   # same behaviour now; Claude skip added in Module 3
    python src/main.py --source hn,gh
"""

from __future__ import annotations

import argparse
from collections import Counter

from .fetch_sources import (
    fetch_hackernews,
    fetch_producthunt,
    fetch_github_trending,
    fetch_x_kol,
    fetch_rss_sources,
)
from .filter import run_filter
from .schema import DigestedItem, RawItem
from .summarize import summarize_all

_ALL_FETCHERS = {
    "hn":          ("Hacker News",   fetch_hackernews),
    "ph":          ("Product Hunt",  fetch_producthunt),
    "gh":          ("GitHub",        fetch_github_trending),
    "x":           ("X KOL",         fetch_x_kol),
    "rss":         ("RSS",           fetch_rss_sources),
}


def run(sources: list[str], dry_run: bool) -> list[RawItem] | list[DigestedItem]:
    all_items: list[RawItem] = []
    counts: dict[str, int] = {}

    for key in sources:
        label, fetcher = _ALL_FETCHERS[key]
        try:
            items = fetcher()
            counts[label] = len(items)
            all_items.extend(items)
        except Exception as exc:
            print(f"[WARNING] {label} fetch failed: {exc}")
            counts[label] = 0

    parts = " | ".join(f"[{label}] {n}" for label, n in counts.items())
    print(parts + f" | Total: {len(all_items)}")

    if dry_run:
        print("[dry-run] filter + Claude summarization skipped (Modules 2 & 3).")
        return all_items

    all_items = run_filter(all_items)
    return summarize_all(all_items)


def main() -> None:
    parser = argparse.ArgumentParser(description="Miss Ling AI 日报 — fetch layer")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip Claude API calls (no-op until Module 3)")
    parser.add_argument("--source", default="",
                        help="Comma-separated source keys to run (hn,ph,gh,x,rss). Default: all.")
    args = parser.parse_args()

    sources = [s.strip() for s in args.source.split(",") if s.strip()] if args.source else list(_ALL_FETCHERS)
    invalid = [s for s in sources if s not in _ALL_FETCHERS]
    if invalid:
        parser.error(f"Unknown sources: {invalid}. Valid: {list(_ALL_FETCHERS)}")

    run(sources, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
