"""Module 2 — keyword whitelist + score threshold + URL dedup + per-source cap."""

from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .schema import RawItem

_KEYWORDS_EN = (
    "ai", "llm", "agent", "gpt", "claude", "gemini", "model",
    "machine learning", "neural", "transformer", "inference",
    "fine-tune", "rag", "embedding", "multimodal", "diffusion",
    "autonomous", "copilot", "chatbot",
)
_KEYWORDS_CN = (
    "ai", "人工智能", "大模型", "机器学习", "智能体",
    "推理", "微调", "多模态", "扩散模型",
)

_BYPASS_KEYWORD: set[str] = {"aibase"}

_SCORE_THRESHOLDS: dict[str, int] = {
    "hn": 50,
    "github": 20,
    "x": 30,
}

_PER_SOURCE_CAP = 10


def _matches(text: str, keywords: tuple) -> bool:
    """Word-boundary keyword match; strips dots, normalises separators."""
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


def keyword_filter(items: list[RawItem]) -> list[RawItem]:
    """Keep items whose title+summary matches AI keywords.

    Sources in _BYPASS_KEYWORD pass through unconditionally.
    """
    out = []
    for item in items:
        if item.source in _BYPASS_KEYWORD:
            out.append(item)
            continue
        text = item.title + " " + item.summary
        if _matches(text, _KEYWORDS_EN) or _matches(text, _KEYWORDS_CN):
            out.append(item)
    return out


def score_filter(items: list[RawItem]) -> list[RawItem]:
    """Drop items below the per-source minimum engagement threshold."""
    return [
        item for item in items
        if item.score >= _SCORE_THRESHOLDS.get(item.source, 0)
    ]


def _normalise_url(url: str) -> str:
    """Strip utm_* params and trailing path slash; lowercase scheme+host."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs_clean = {k: v for k, v in qs.items() if not k.lower().startswith("utm_")}
    query = urlencode(qs_clean, doseq=True)
    return urlunparse((scheme, netloc, path, parsed.params, query, parsed.fragment))


def dedup(items: list[RawItem]) -> list[RawItem]:
    """Deduplicate by normalised URL, keeping the highest-score item per URL.

    Items with empty URLs are kept as-is without participating in dedup.
    """
    seen: dict[str, RawItem] = {}
    empties: list[RawItem] = []
    for item in items:
        if not item.url:
            empties.append(item)
            continue
        key = _normalise_url(item.url)
        if key not in seen or item.score > seen[key].score:
            seen[key] = item
    return list(seen.values()) + empties


def truncate(items: list[RawItem], max_total: int = 40) -> list[RawItem]:
    """Cap per-source to _PER_SOURCE_CAP items, then round-robin interleave up to max_total.

    Within each source, items are sorted by score descending before capping.
    Round-robin order follows the first-appearance order of sources in items.
    """
    groups: dict[str, list[RawItem]] = defaultdict(list)
    source_order: list[str] = []
    for item in items:
        if item.source not in groups:
            source_order.append(item.source)
        groups[item.source].append(item)

    capped: dict[str, list[RawItem]] = {
        src: sorted(groups[src], key=lambda x: x.score, reverse=True)[:_PER_SOURCE_CAP]
        for src in source_order
    }

    out: list[RawItem] = []
    for round_idx in range(_PER_SOURCE_CAP):
        for src in source_order:
            bucket = capped[src]
            if round_idx < len(bucket):
                out.append(bucket[round_idx])
                if len(out) >= max_total:
                    return out
    return out


def run_filter(items: list[RawItem]) -> list[RawItem]:
    """Run all four filter stages in sequence, logging per-stage counts."""
    n0 = len(items)
    after_kw = keyword_filter(items)
    after_score = score_filter(after_kw)
    after_dedup = dedup(after_score)
    after_trunc = truncate(after_dedup)
    print(
        f"[Filter] keyword: {n0} → {len(after_kw)} | "
        f"score: {len(after_kw)} → {len(after_score)} | "
        f"dedup: {len(after_score)} → {len(after_dedup)} | "
        f"truncate: {len(after_dedup)} → {len(after_trunc)}"
    )
    return after_trunc
