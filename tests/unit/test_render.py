from __future__ import annotations

from crawler.pipeline.render import render, split_by_size


def test_render_includes_empty_university(sample_item) -> None:
    markdown = render([sample_item], ["复旦大学", "清华大学"], False, "test-run")

    assert "## 复旦大学" in markdown
    assert "## 清华大学" in markdown
    assert "今日无更新" in markdown
    assert "共 1 条新消息" in markdown


def test_render_all_empty_still_outputs_skeleton() -> None:
    markdown = render([], ["复旦大学", "上海交通大学", "清华大学"], True, "test-run")

    assert "共 0 条新消息" in markdown
    assert markdown.count("今日无更新") == 3
    assert "LLM 不可用" in markdown


def test_render_escapes_markdown_title(sample_item) -> None:
    from dataclasses import replace

    item = replace(sample_item, title="招生 [简章] *发布*")

    markdown = render([item], ["复旦大学"], False, "test-run")

    assert r"招生 \[简章\] \*发布\*" in markdown


def test_render_escapes_parentheses_in_markdown_url(sample_item) -> None:
    from dataclasses import replace

    item = replace(sample_item, url="https://example.edu/info(2026).htm")

    markdown = render([item], ["复旦大学"], False, "test-run")

    assert "https://example.edu/info%282026%29.htm" in markdown


def test_split_by_size_returns_chunks_under_limit() -> None:
    markdown = "# title\n\n## A\n" + ("x" * 100) + "\n## B\n" + ("y" * 100)

    chunks = split_by_size(markdown, 130)

    assert len(chunks) >= 2
    assert all(len(chunk.encode("utf-8")) <= 130 for chunk in chunks)
