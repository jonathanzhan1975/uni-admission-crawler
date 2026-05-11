from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import ClassVar
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import structlog

from crawler.fetchers.base import BaseFetcher
from crawler.pipeline.archive import save_raw
from crawler.schema import FetchResult, Item, SourceId
from crawler.utils.http import HttpClient
from crawler.utils.text import clean_text
from crawler.utils.url import canonicalize, item_id_for_url


logger = structlog.get_logger()
CN_TZ = ZoneInfo("Asia/Shanghai")


class WebplusFetcher(BaseFetcher):
    """Base class for schools using Webplus/Supan/static list CMS."""
    
    BASE_URL: ClassVar[str] = ""
    LIST_PATHS: ClassVar[tuple[str, ...]] = ()
    ITEM_SELECTOR: ClassVar[str] = "ul.wp_article_list > li, .news_list > li, li.news, li.cols, .list-item"
    DATE_SELECTOR: ClassVar[str] = ".news_meta, .cols_meta, time, .date, .wp_article_time, .article-date"

    DEFAULT_SOURCE_ID: ClassVar[SourceId]
    DEFAULT_SOURCE_NAME: ClassVar[str] = "本科招办"
    DEFAULT_UNIVERSITY: ClassVar[str] = ""
    DEFAULT_NEEDS_CLASSIFICATION: ClassVar[bool] = False

    def __init__(self, base_url: str | None = None, http_client: HttpClient | None = None):
        self.source_id = self.DEFAULT_SOURCE_ID
        self.source_name = self.DEFAULT_SOURCE_NAME
        self.university = self.DEFAULT_UNIVERSITY
        self.needs_classification = self.DEFAULT_NEEDS_CLASSIFICATION
        self.base_url = base_url or self.BASE_URL
        self.http_client = http_client or HttpClient()

    def fetch(self, max_items: int = 30) -> FetchResult:
        try:
            items: list[Item] = []
            for path in self.LIST_PATHS:
                response = self.http_client.get(canonicalize(path, self.base_url))
                save_raw(self.source_id, response.content)
                items.extend(self._parse_list_bytes(response.content, response.encoding, response.charset_encoding))
            items = self._dedupe_items(items)[:max_items]
            logger.info("fetch_success", source_id=self.source_id.value, fetched_count=len(items))
            return FetchResult(self.source_id, items, True)
        except Exception as exc:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(exc))
            return FetchResult(self.source_id, [], False, str(exc))

    def _parse_list_bytes(
        self,
        html: bytes,
        header_encoding: str | None = None,
        detected_encoding: str | None = None,
    ) -> list[Item]:
        encoding = self._choose_encoding(header_encoding, detected_encoding)
        soup = BeautifulSoup(html, "lxml", from_encoding=encoding)
        return self._parse_soup(soup)

    def _parse_soup(self, soup: BeautifulSoup) -> list[Item]:
        nodes = soup.select(self.ITEM_SELECTOR)
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        for node in nodes:
            # Find the best link (the first one that has text or a title)
            links = node.select("a[href]")
            link = None
            title = ""
            for l in links:
                t = clean_text(l.get_text(" ", strip=True) or l.get("title"))
                if t and len(t) > 2: # Ignore very short titles like ">>" or numbers
                    link = l
                    title = t
                    break
            
            if link is None:
                continue
            
            href = link.get("href", "")
            if not href:
                continue
                
            canonical_url = canonicalize(href, self.base_url)
            pub_date, inferred = self._extract_date(self._extract_date_text(node), fetched_at)
            items.append(
                Item(
                    item_id=item_id_for_url(canonical_url),
                    university=self.university,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    url=canonical_url,
                    pub_date=pub_date,
                    summary=None,
                    fetched_at=fetched_at,
                    date_inferred=inferred,
                    needs_classification=self.needs_classification,
                )
            )
        if not items:
            logger.warning("selector_no_match", source_id=self.source_id.value)
        return items

    def _extract_date_text(self, node) -> str:
        date_node = node.select_one(self.DATE_SELECTOR)
        if date_node is None:
            spans = node.select("span")
            date_node = spans[-1] if spans else None
        return date_node.get_text(" ", strip=True) if date_node else ""

    def _choose_encoding(self, header_encoding: str | None, detected_encoding: str | None) -> str | None:
        if header_encoding and header_encoding.lower() not in {"iso-8859-1", "latin-1"}:
            return header_encoding
        return detected_encoding

    def _dedupe_items(self, items: list[Item]) -> list[Item]:
        deduped: list[Item] = []
        seen: set[str] = set()
        for item in items:
            if item.item_id in seen:
                continue
            seen.add(item.item_id)
            deduped.append(item)
        return deduped

    def _extract_date(self, text: str, fetched_at: datetime) -> tuple[datetime, bool]:
        match = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})", text)
        if not match:
            return fetched_at, True
        raw = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        try:
            parsed = date_parser.parse(raw).replace(tzinfo=CN_TZ)
            return parsed, False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True
