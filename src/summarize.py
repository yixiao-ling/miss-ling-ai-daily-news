"""Module 3 — Claude AI 摘要生成，带 prompt caching 降低 token 成本。"""

from __future__ import annotations

import os
import time

import anthropic

from .schema import DigestedItem, RawItem

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1600
_SLEEP = 0.5

_VALID_CATEGORIES = {"模型能力", "AI产品", "商业动态", "开源生态", "行业落地", "其他"}

_SYSTEM_PROMPT = """\
你是一位服务于 AI 产品经理的资讯编辑。AI 产品经理的特点：懂技术原理、关注产品落地、重视商业价值、需要快速判断信息优先级。

请调用 save_digest 工具输出分析结果，各字段说明：

【中文字段】
- title_zh：如果原标题不是简体中文，翻译成简体中文并保留关键英文术语；如果已是中文，原样输出
- summary_zh：50-100字中文高度概括。必须用简体中文写，即使原文是英文也要翻译总结。不要逐句翻译原文，而是提炼出这条资讯最核心的一个结论或事实。格式：先说发生了什么（who did what），再说为什么重要（why it matters）
- so_what：100-150字影响分析。新技术→大白话解释原理+产品场景；新产品→解决什么痛点+竞品对比；商业动态→对行业格局的影响。站在AI产品经理视角，这条信息意味着什么
- eli5：2-3句极简大白话，面向完全不懂技术的人
- use_cases：2-4条具体应用场景，每条一句话
- tags：2-4个关键词标签（中英文均可）
- category：从六个分类中选一个
- importance 评分标准（面向 AI 产品经理视角打分）：
  5分 = 必看：直接影响产品决策（重大模型发布、核心API变更、行业巨头战略转向、法规政策变化）
  4分 = 重要：值得深入了解（有潜力的新工具、重要竞品动态、值得跟进的技术趋势）
  3分 = 参考：有价值但不紧急（一般性产品更新、社区讨论热点）
  2分 = 了解：背景信息，扫一眼即可
  1分 = 低优：边缘内容，与产品决策关联弱

【English fields — for bilingual display】
- title_en: English title (translate from Chinese if needed; keep as-is if already English)
- summary_en: 50-100 word English summary. Same structure as summary_zh: who did what + why it matters
- so_what_en: 100-150 word English impact analysis. Same content as so_what but in English, from an AI PM perspective
- eli5_en: 2-3 sentence plain-English ELI5 for non-technical readers
- use_cases_en: 2-4 specific use cases in English, one sentence each"""

_DIGEST_TOOL = {
    "name": "save_digest",
    "description": "保存这条资讯的双语摘要分析结果（中文 + English）",
    "input_schema": {
        "type": "object",
        "properties": {
            "title_zh": {"type": "string", "description": "简体中文标题"},
            "summary_zh": {"type": "string", "description": "50-100字中文高度概括"},
            "so_what": {"type": "string", "description": "100-150字中文影响分析"},
            "eli5": {"type": "string", "description": "2-3句中文大白话"},
            "use_cases": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4条中文应用场景",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4个关键词标签",
            },
            "category": {
                "type": "string",
                "enum": ["模型能力", "AI产品", "商业动态", "开源生态", "行业落地", "其他"],
            },
            "importance": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
            },
            "title_en": {"type": "string", "description": "English title"},
            "summary_en": {"type": "string", "description": "50-100 word English summary"},
            "so_what_en": {"type": "string", "description": "100-150 word English impact analysis"},
            "eli5_en": {"type": "string", "description": "2-3 sentence plain-English ELI5"},
            "use_cases_en": {
                "type": "array",
                "items": {"type": "string"},
                "description": "2-4 use cases in English",
            },
        },
        "required": [
            "title_zh", "summary_zh", "so_what", "eli5",
            "use_cases", "tags", "category", "importance",
            "title_en", "summary_en", "so_what_en", "eli5_en", "use_cases_en",
        ],
    },
}


def _build_user_prompt(item: RawItem) -> str:
    return (
        f"请分析以下资讯：\n"
        f"来源：{item.source_label}\n"
        f"标题：{item.title}\n"
        f"内容：{item.summary[:400]}"
    )


def _fallback(item: RawItem) -> DigestedItem:
    summary_zh = (item.summary[:150] if item.summary else item.title)
    return DigestedItem(
        raw=item,
        summary_zh=summary_zh,
        eli5="",
        use_cases=[],
        tags=[],
        importance=3,
        title_zh=item.title,
        category="其他",
        so_what="",
        title_en=item.title,
        summary_en=item.summary[:150] if item.summary else item.title,
        eli5_en="",
        so_what_en="",
        use_cases_en=[],
    )


def summarize_item(item: RawItem, client: anthropic.Anthropic) -> DigestedItem:
    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=[_DIGEST_TOOL],
            tool_choice={"type": "tool", "name": "save_digest"},
            messages=[{"role": "user", "content": _build_user_prompt(item)}],
        )
        tool_block = next(b for b in response.content if b.type == "tool_use")
        data = tool_block.input
        raw_category = str(data.get("category", "其他"))
        category = raw_category if raw_category in _VALID_CATEGORIES else "其他"
        title_zh = str(data.get("title_zh", "")) or item.title
        return DigestedItem(
            raw=item,
            summary_zh=str(data.get("summary_zh", item.title)),
            eli5=str(data.get("eli5", "")),
            use_cases=list(data["use_cases"]) if isinstance(data.get("use_cases"), list) else [],
            tags=list(data["tags"]) if isinstance(data.get("tags"), list) else [],
            importance=int(data.get("importance", 3)),
            title_zh=title_zh,
            category=category,
            so_what=str(data.get("so_what", "")),
            title_en=str(data.get("title_en", "")) or item.title,
            summary_en=str(data.get("summary_en", "")),
            eli5_en=str(data.get("eli5_en", "")),
            so_what_en=str(data.get("so_what_en", "")),
            use_cases_en=list(data["use_cases_en"]) if isinstance(data.get("use_cases_en"), list) else [],
        )
    except Exception as exc:
        print(f"[WARN] summarize failed for '{item.title[:40]}': {exc}")
        return _fallback(item)


def summarize_all(items: list[RawItem]) -> list[DigestedItem]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[WARN] ANTHROPIC_API_KEY not set — using fallback for all items.")
        return [_fallback(item) for item in items]

    client = anthropic.Anthropic()
    results: list[DigestedItem] = []
    fallback_count = 0
    n = len(items)

    for i, item in enumerate(items, 1):
        print(f"[Summarize] {i}/{n} @{item.source_label}")
        digested = summarize_item(item, client)
        results.append(digested)
        if digested.eli5 == "" and digested.tags == [] and digested.use_cases == []:
            fallback_count += 1
        if i < n:
            time.sleep(_SLEEP)

    print(f"[Summarize] done: {n} items, {fallback_count} fallback")
    return results
