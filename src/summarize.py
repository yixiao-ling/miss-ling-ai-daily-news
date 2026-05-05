"""Module 3 — Claude AI 摘要生成，带 prompt caching 降低 token 成本。"""

from __future__ import annotations

import json
import os
import re
import time

import anthropic

from .schema import DigestedItem, RawItem

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 600
_SLEEP = 0.5

_SYSTEM_PROMPT = """\
你是一位 AI 行业资讯编辑，专为技术从业者提炼每日资讯。
你的任务是分析每条资讯，输出以下 JSON 格式（不要输出任何 JSON 以外的内容，不要加 markdown 代码块）：
{
  "summary_zh": "50-100字中文核心要点，说清楚这条资讯做了什么/发生了什么",
  "eli5": "用2-3句大白话解释这个技术，像跟非技术朋友聊天一样，不用术语",
  "use_cases": ["应用场景1，一句话", "应用场景2，一句话"],
  "tags": ["标签1", "标签2", "标签3"],
  "importance": 3
}
importance 评分标准：
5分=行业重大突破（新模型发布/重要研究/巨头战略变化）
4分=值得关注的进展
3分=有参考价值的资讯
2分=一般性信息
1分=边缘内容"""


def _build_user_prompt(item: RawItem) -> str:
    return (
        f"请分析以下资讯并按格式输出：\n"
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
            messages=[{"role": "user", "content": _build_user_prompt(item)}],
        )
        raw_text = response.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            m = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if m:
                data = json.loads(m.group())
            else:
                raise
        return DigestedItem(
            raw=item,
            summary_zh=str(data.get("summary_zh", item.title)),
            eli5=str(data.get("eli5", "")),
            use_cases=list(data["use_cases"]) if isinstance(data.get("use_cases"), list) else [],
            tags=list(data["tags"]) if isinstance(data.get("tags"), list) else [],
            importance=int(data.get("importance", 3)),
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
