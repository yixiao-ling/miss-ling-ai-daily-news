"""Module 3 — DeepSeek AI 摘要生成（OpenAI 兼容接口，DeepSeek 自带上下文缓存）。"""

from __future__ import annotations

import json
import os
import time

from openai import OpenAI

from .schema import DigestedItem, RawItem

_MODEL = "deepseek-chat"
_BASE_URL = "https://api.deepseek.com"
_MAX_TOKENS = 1600
_SLEEP = 0.5

_VALID_CATEGORIES = {"模型能力", "AI产品", "商业动态", "开源生态", "行业落地", "其他"}

_SYSTEM_PROMPT = """\
你是一位服务于 AI builder 的资讯编辑。AI builder 同时具备产品与算法两种视角：既懂模型/算法原理与工程实现可行性，也关注产品落地、商业价值与信息优先级，能从一条资讯里同时看出「技术上怎么做到的」和「产品上能做成什么」。

请调用 save_digest 工具输出分析结果，各字段说明：

【中文字段】
- title_zh：如果原标题不是简体中文，翻译成简体中文并保留关键英文术语；如果已是中文，原样输出
- summary_zh：50-100字中文高度概括。必须用简体中文写，即使原文是英文也要翻译总结。不要逐句翻译原文，而是提炼出这条资讯最核心的一个结论或事实。格式：先说发生了什么（who did what），再说为什么重要（why it matters）
- so_what：100-150字影响分析。站在 AI builder（产品+算法）视角：新技术→既解释算法/工程原理，也点出产品场景；新产品→解决什么痛点+技术实现路径+竞品对比；商业动态→对行业格局与技术选型的影响。这条信息对一个既做产品又懂算法的人意味着什么
- eli5：2-3句极简大白话，面向完全不懂技术的人
- use_cases：2-4条具体应用场景，每条一句话
- tags：2-4个关键词标签（中英文均可）
- category：从六个分类中选一个
- org_efficiency：80-120字中文，分析这条资讯对【组织效率优化】的参考价值——它能优化什么流程、岗位协作或自动化哪类工作，对团队/组织如何提效有何启发。若与组织效率无直接关联，简要说明「参考价值有限」并给出最贴近的一点引申
- data_annotation：80-120字中文，分析这条资讯对【数据标注】（音频、代码等）的参考价值。锚点示例：音频标注 = 给定一段音频 + 3 段 ASR 候选转录文本，让大模型判断哪段才是真实转录并打标签。请思考这条资讯能否提升标注质量/效率、能否用于自动判别候选、对标注流程或标注模型有何启发。若无关联，简要说明
- importance 评分标准（面向 AI builder 视角打分，兼顾产品价值与技术/算法含量）：
  5分 = 必看：直接影响产品决策或技术选型（重大模型发布、核心API变更、关键算法突破、行业巨头战略转向、法规政策变化）
  4分 = 重要：值得深入了解（有潜力的新工具/新方法、重要竞品动态、值得跟进的技术或算法趋势）
  3分 = 参考：有价值但不紧急（一般性产品更新、社区讨论热点）
  2分 = 了解：背景信息，扫一眼即可
  1分 = 低优：边缘内容，与产品决策和技术实践关联弱

【English fields — for bilingual display】
- title_en: English title (translate from Chinese if needed; keep as-is if already English)
- summary_en: 50-100 word English summary. Same structure as summary_zh: who did what + why it matters
- so_what_en: 100-150 word English impact analysis. Same content as so_what but in English, from an AI builder (product + algorithm) perspective
- eli5_en: 2-3 sentence plain-English ELI5 for non-technical readers
- use_cases_en: 2-4 specific use cases in English, one sentence each"""

_DIGEST_TOOL = {
    "type": "function",
    "function": {
        "name": "save_digest",
        "description": "保存这条资讯的双语摘要分析结果（中文 + English）",
        "parameters": {
            "type": "object",
            "properties": {
                "title_zh": {"type": "string", "description": "简体中文标题"},
                "summary_zh": {"type": "string", "description": "50-100字中文高度概括"},
                "so_what": {"type": "string", "description": "100-150字中文影响分析，AI builder 视角"},
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
                "org_efficiency": {"type": "string", "description": "80-120字中文，对组织效率优化的参考价值"},
                "data_annotation": {"type": "string", "description": "80-120字中文，对数据标注（音频/代码等）的参考价值"},
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
                "org_efficiency", "data_annotation",
                "title_en", "summary_en", "so_what_en", "eli5_en", "use_cases_en",
            ],
        },
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
        org_efficiency="",
        data_annotation="",
    )


def summarize_item(item: RawItem, client: OpenAI) -> DigestedItem:
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(item)},
            ],
            tools=[_DIGEST_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_digest"}},
        )
        # OpenAI 风格：function arguments 是 JSON 字符串，需 json.loads（DeepSeek 同此）
        data = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
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
            org_efficiency=str(data.get("org_efficiency", "")),
            data_annotation=str(data.get("data_annotation", "")),
        )
    except Exception as exc:
        print(f"[WARN] summarize failed for '{item.title[:40]}': {exc}")
        return _fallback(item)


def summarize_all(items: list[RawItem]) -> list[DigestedItem]:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("[WARN] DEEPSEEK_API_KEY not set — using fallback for all items.")
        return [_fallback(item) for item in items]

    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=_BASE_URL)
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
