from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from crawler.schema import Item
from crawler.utils.text import escape_markdown
from crawler.utils.time import now_local
from crawler.utils.url import markdown_safe_url


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def render(
    items: list[Item],
    universities: list[str],
    classify_degraded: bool,
    run_id: str,
    template_path: str = "templates/daily_report.md.j2",
) -> str:
    template_ref = Path(template_path)
    template_name = str(template_ref if not template_ref.is_absolute() else template_ref.relative_to(PROJECT_ROOT))
    env = Environment(
        loader=FileSystemLoader(str(PROJECT_ROOT)),
        autoescape=select_autoescape(disabled_extensions=("j2", "md")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["md"] = escape_markdown
    env.filters["md_url"] = markdown_safe_url
    template = env.get_template(template_name)
    grouped: dict[str, dict[str, list[Item]]] = defaultdict(lambda: defaultdict(list))
    for item in sorted(items, key=lambda value: (value.university, value.source_name, value.pub_date), reverse=True):
        grouped[item.university][item.source_name].append(item)
    report_date = now_local().strftime("%Y-%m-%d")
    university_count = len({item.university for item in items})
    return template.render(
        items=items,
        grouped=grouped,
        universities=universities,
        classify_degraded=classify_degraded,
        run_id=run_id,
        report_date=report_date,
        total_count=len(items),
        university_count=university_count,
    )


def split_by_size(markdown: str, max_bytes: int) -> list[str]:
    if len(markdown.encode("utf-8")) <= max_bytes:
        return [markdown]
    chunks: list[str] = []
    current = ""
    for section in markdown.split("\n## "):
        section_text = section if section.startswith("#") else f"\n## {section}"
        candidate = current + section_text
        if current and len(candidate.encode("utf-8")) > max_bytes:
            chunks.append(current.strip())
            current = section_text
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return [part for chunk in chunks for part in _split_oversized_chunk(chunk, max_bytes)]


def _split_oversized_chunk(chunk: str, max_bytes: int) -> list[str]:
    if len(chunk.encode("utf-8")) <= max_bytes:
        return [chunk]
    parts: list[str] = []
    current = ""
    for line in chunk.splitlines(keepends=True):
        if len(line.encode("utf-8")) > max_bytes:
            if current:
                parts.append(current.strip())
                current = ""
            parts.extend(_split_long_line(line, max_bytes))
            continue
        candidate = current + line
        if current and len(candidate.encode("utf-8")) > max_bytes:
            parts.append(current.strip())
            current = line
        else:
            current = candidate
    if current.strip():
        parts.append(current.strip())
    return parts


def _split_long_line(line: str, max_bytes: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if current and len(candidate.encode("utf-8")) > max_bytes:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces
