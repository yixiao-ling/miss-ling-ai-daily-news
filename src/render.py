"""Module 4/5 — Jinja2 → docs/index.html + docs/archive/YYYY-MM-DD.html."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .schema import DigestedItem

_SOURCE_ORDER = ["hn", "github", "ph", "x", "36kr", "huxiu", "aibase"]
_SOURCE_LABELS = {
    "hn":     "Hacker News",
    "github": "GitHub",
    "ph":     "Product Hunt",
    "x":      "X KOL",
    "36kr":   "36氪",
    "huxiu":  "虎嗅",
    "aibase": "AIbase",
}


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

    source_counts: dict[str, int] = dict(Counter(it.raw.source_label for it in items))

    # Build ordered filter pills: (source_key, source_label, count)
    source_key_counts: dict[str, int] = Counter(it.raw.source for it in items)
    source_pills = []
    for key in _SOURCE_ORDER:
        if key in source_key_counts:
            source_pills.append((key, _SOURCE_LABELS.get(key, key), source_key_counts[key]))
    # append any sources not in our fixed order
    for key, count in source_key_counts.items():
        if key not in _SOURCE_ORDER:
            source_pills.append((key, key, count))

    html = env.get_template("daily.html").render(
        date=date,
        items=items,
        source_counts=source_counts,
        source_pills=source_pills,
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
