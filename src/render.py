"""Module 4/5 — Jinja2 → docs/index.html + docs/archive/YYYY-MM-DD.html."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import DigestedItem

_CATEGORY_ORDER = ["模型能力", "AI产品", "商业动态", "开源生态", "行业落地", "其他"]


def _format_time(value: str) -> str:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value[:19], fmt[:len(fmt)])
            return dt.strftime("%m-%d %H:%M")
        except ValueError:
            continue
    return value[:10] if value else ""


def render(items: list[DigestedItem], output_dir: str = "docs") -> str:
    templates_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["format_time"] = _format_time

    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    generated_at = now.strftime("%Y-%m-%d %H:%M")

    cat_counts: dict[str, int] = Counter(
        getattr(it, "category", "其他") or "其他" for it in items
    )
    category_pills = [
        (cat, cat_counts[cat]) for cat in _CATEGORY_ORDER if cat in cat_counts
    ]

    html = env.get_template("daily.html").render(
        date=date,
        items=items,
        category_pills=category_pills,
        generated_at=generated_at,
    )

    out_dir = Path(output_dir)
    archive_dir = out_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")

    archive_path = archive_dir / f"{date}.html"
    archive_path.write_text(html, encoding="utf-8")

    print(f"[Render] {index_path} written ({len(items)} items)")
    return str(index_path.resolve())
