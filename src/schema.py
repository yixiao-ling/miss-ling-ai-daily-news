"""Core data schemas for Miss Ling AI Daily.

RawItem: a single piece of content fetched from a source, before AI enrichment.
DigestedItem: a RawItem after Claude has produced summary/eli5/use_cases/tags/importance.
"""

from dataclasses import dataclass, field


@dataclass
class RawItem:
    source: str          # "hn" | "producthunt" | "github" | "x" | "36kr" | "huxiu" | "aibase"
    source_label: str    # display label, e.g. "Hacker News", "X @sama", "36氪"
    title: str
    summary: str         # original excerpt or truncated body (<= 400 chars)
    url: str
    published_at: str    # ISO 8601 string
    score: int           # interaction count: HN points / GH stars / X likes / 0 for sources without one


@dataclass
class DigestedItem:
    raw: RawItem
    summary_zh: str          # Claude-generated, 50-100 字
    eli5: str                # 大白话, 2-3 句
    use_cases: list          # 应用场景, 2-4 条
    tags: list               # 关键词标签, 2-4 个
    importance: int          # 1-5
