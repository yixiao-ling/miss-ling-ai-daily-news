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
    summary_zh: str = ""
    eli5: str = ""
    use_cases: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    importance: int = 3
    title_zh: str = ""      # 中文标题；原文非中文时翻译，中文则原样输出
    category: str = "其他"  # 模型能力 / AI产品 / 商业动态 / 开源生态 / 行业落地 / 其他
    so_what: str = ""       # 影响分析 100-150 字，面向 AI builder（产品+算法）
    # English fields (bilingual support)
    title_en: str = ""
    summary_en: str = ""
    eli5_en: str = ""
    so_what_en: str = ""
    use_cases_en: list = field(default_factory=list)
    # 中文专属分析维度（不做英文，两种语言界面下均常显）
    org_efficiency: str = ""    # 组织效率优化参考价值
    data_annotation: str = ""   # 数据标注参考价值（音频/代码等）
