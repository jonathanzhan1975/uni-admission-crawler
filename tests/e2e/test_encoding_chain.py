from __future__ import annotations

from urllib.parse import unquote

import httpx

from crawler.fetchers.fudan_ao import FudanAoFetcher
from crawler.pipeline.render import render
from crawler.pushers.serverchan import ServerchanPusher


def test_encoding_chain_fetch_render_serverchan(monkeypatch) -> None:
    title = "📅 François 教授招生简章"
    html = f"""
    <html>
      <head><meta charset="gbk"></head>
      <body>
        <ul class="wp_article_list">
          <li><span>2026-05-01</span><a href="info(2026).htm">{title}</a></li>
        </ul>
      </body>
    </html>
    """.encode("gbk", errors="xmlcharrefreplace")
    item = FudanAoFetcher()._parse_list_bytes(html, header_encoding=None, detected_encoding=None)[0]
    markdown = render([item], ["复旦大学"], False, "encoding-test")
    captured: dict[str, object] = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, json={"code": 0}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ServerchanPusher("SCT_TEST").push(markdown, "📅 François 教授高校招生动态")

    payload = captured["json"]
    assert result.success is True
    assert payload["title"] == "📅 François 教授高校招生动态"
    assert "�" not in payload["title"]
    assert "📅" in payload["title"]
    assert "François" in payload["desp"]
    assert "info%282026%29.htm" in payload["desp"]
    assert unquote("info%282026%29.htm") == "info(2026).htm"
