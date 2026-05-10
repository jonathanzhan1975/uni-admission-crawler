from __future__ import annotations

from pathlib import Path

import feedparser
import pytest

from crawler.fetchers.fudan_ao import FudanAoFetcher
from crawler.fetchers.rsshub import RsshubFetcher
from crawler.utils.http import HttpClient
from crawler.schema import SourceId


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_fudan_parse_list_normalizes_relative_url() -> None:
    html = (FIXTURES / "fudan_ao_list_v1.html").read_text(encoding="utf-8")
    fetcher = FudanAoFetcher()

    items = fetcher._parse_list(html)

    assert len(items) == 2
    assert items[0].url == "https://ao.fudan.edu.cn/info/1001.htm"
    assert items[0].title == "2026 年本科招生简章发布"
    assert not items[0].date_inferred


def test_fudan_parse_list_changed_markup_returns_empty() -> None:
    html = (FIXTURES / "fudan_ao_list_v2.html").read_text(encoding="utf-8")
    fetcher = FudanAoFetcher()

    assert fetcher._parse_list(html) == []


def test_fudan_parse_list_ignores_unexpected_li_nav() -> None:
    html = '<ul class="nav"><li><a href="/about.htm">关于我们</a></li></ul>'
    fetcher = FudanAoFetcher()

    assert fetcher._parse_list(html) == []


def test_rsshub_parse_feed_marks_missing_date_inferred() -> None:
    xml = (FIXTURES / "sjtu_jwc.xml").read_bytes()
    feed = feedparser.parse(xml)
    fetcher = RsshubFetcher(SourceId.SJTU_JWC, "教务处", "上海交通大学", "/sjtu/jwc", True, "https://rsshub.app")

    items = fetcher._parse_feed(feed.entries, 30)

    assert len(items) == 2
    assert items[0].summary == "新增专业说明"
    assert items[1].date_inferred


def test_rsshub_parse_feed_respects_max_items() -> None:
    xml = (FIXTURES / "sjtu_jwc.xml").read_bytes()
    feed = feedparser.parse(xml)
    fetcher = RsshubFetcher(SourceId.SJTU_JWC, "教务处", "上海交通大学", "/sjtu/jwc", True, "https://rsshub.app")

    items = fetcher._parse_feed(feed.entries, 1)

    assert len(items) == 1


def test_rsshub_tsinghua_titles_are_utf8() -> None:
    xml = (FIXTURES / "tsinghua_news.xml").read_bytes()
    feed = feedparser.parse(xml)
    fetcher = RsshubFetcher(SourceId.TSINGHUA_NEWS, "主新闻", "清华大学", "/tsinghua/news", True, "https://rsshub.app")

    items = fetcher._parse_feed(feed.entries, 30)

    assert items
    assert all("�" not in item.title for item in items)


def test_http_client_retries_5xx(monkeypatch) -> None:
    import httpx

    attempts = {"count": 0}
    monkeypatch.setattr("time.sleep", lambda _: None)

    def fake_get(*args, **kwargs):
        attempts["count"] += 1
        return httpx.Response(503, request=httpx.Request("GET", "https://example.com"))

    monkeypatch.setattr(httpx, "get", fake_get)

    try:
        HttpClient(retries=3).get("https://example.com")
    except httpx.HTTPStatusError:
        pass

    assert attempts["count"] == 3


def test_http_client_retries_timeout(monkeypatch) -> None:
    import httpx

    attempts = {"count": 0}
    monkeypatch.setattr("time.sleep", lambda _: None)

    def fake_get(*args, **kwargs):
        attempts["count"] += 1
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(httpx.TimeoutException):
        HttpClient(retries=3).get("https://example.com")

    assert attempts["count"] == 3


def test_fudan_fetch_archives_raw(monkeypatch, tmp_path) -> None:
    import httpx

    monkeypatch.chdir(tmp_path)
    html = (FIXTURES / "fudan_ao_list_v1.html").read_text(encoding="utf-8")

    class FakeClient:
        def get(self, _url):
            return httpx.Response(200, text=html, request=httpx.Request("GET", "https://example.com"))

    result = FudanAoFetcher(http_client=FakeClient()).fetch()

    assert result.success
    assert list((tmp_path / "data" / "raw").glob("*/*.html"))


def test_fudan_gbk_page_without_charset_is_not_garbled() -> None:
    title = "复旦大学 François 教授招生简章"
    html = f"""
    <html>
      <head><meta http-equiv="Content-Type" content="text/html; charset=gbk"></head>
      <body>
        <ul class="wp_article_list">
          <li><span>2026-05-01</span><a href="info(2026).htm">{title}</a></li>
        </ul>
      </body>
    </html>
    """.encode("gbk", errors="xmlcharrefreplace")
    fetcher = FudanAoFetcher()

    items = fetcher._parse_list_bytes(html, header_encoding=None, detected_encoding=None)

    assert items[0].title == title
    assert "�" not in items[0].title


def test_fudan_date_uses_span_not_title_date() -> None:
    html = """
    <ul class="wp_article_list">
      <li><a href="info/1.htm">2026-05-01 招生简章发布</a></li>
    </ul>
    """
    fetcher = FudanAoFetcher()

    items = fetcher._parse_list(html)

    assert items[0].date_inferred is True
