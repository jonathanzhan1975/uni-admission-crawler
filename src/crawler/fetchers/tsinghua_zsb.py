from __future__ import annotations

from datetime import datetime, timezone
from typing import ClassVar

from bs4 import BeautifulSoup
import structlog

from crawler.fetchers.fudan_ao import FudanAoFetcher
from crawler.schema import Item, SourceId
from crawler.utils.text import clean_text
from crawler.utils.url import canonicalize, item_id_for_url


logger = structlog.get_logger()


class TsinghuaZsbFetcher(FudanAoFetcher):
    DEFAULT_SOURCE_ID = SourceId.TSINGHUA_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "清华大学"
    DEFAULT_NEEDS_CLASSIFICATION = False
    BASE_URL = "https://join-tsinghua.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = ("/zygg.htm",)

    def _parse_soup(self, soup: BeautifulSoup) -> list[Item]:
        nodes = soup.select(".wal.announcements .pageList li")
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        for node in nodes:
            link = node.select_one("a[href]")
            if link is None:
                continue
            name_node = link.select_one(".name")
            raw_title = link.get("title") or (
                name_node.get_text(" ", strip=True) if name_node else link.get_text(" ", strip=True)
            )
            title = clean_text(raw_title)
            href = link.get("href", "")
            if not title or not href:
                logger.warning("item_dropped", source_id=self.source_id.value, reason="missing_title_or_url")
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
        date_node = node.select_one(".time")
        return date_node.get_text(" ", strip=True) if date_node else ""
