from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser
import feedparser
import structlog

from crawler.fetchers.base import BaseFetcher
from crawler.pipeline.archive import save_raw
from crawler.schema import FetchResult, Item, SourceId
from crawler.utils.http import HttpClient
from crawler.utils.text import clean_text
from crawler.utils.url import canonicalize, item_id_for_url


logger = structlog.get_logger()
CN_TZ = ZoneInfo("Asia/Shanghai")


class RsshubFetcher(BaseFetcher):
    def __init__(
        self,
        source_id: SourceId,
        source_name: str,
        university: str,
        rsshub_path: str,
        needs_classification: bool,
        base_url: str,
        http_client: HttpClient | None = None,
    ):
        self.source_id = source_id
        self.source_name = source_name
        self.university = university
        self.rsshub_path = rsshub_path
        self.needs_classification = needs_classification
        self.base_url = base_url
        self.http_client = http_client or HttpClient()

    def fetch(self, max_items: int = 30) -> FetchResult:
        try:
            url = canonicalize(self.rsshub_path, self.base_url)
            response = self.http_client.get(url)
            content = response.content
            save_raw(self.source_id, content)
            parsed = feedparser.parse(content)
            items = self._parse_feed(parsed.entries, max_items)
            logger.info("fetch_success", source_id=self.source_id.value, fetched_count=len(items))
            return FetchResult(self.source_id, items, True)
        except Exception as exc:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(exc))
            return FetchResult(self.source_id, [], False, str(exc))

    def _parse_feed(self, entries: list[object], max_items: int) -> list[Item]:
        fetched_at = datetime.now(timezone.utc)
        items: list[Item] = []
        for entry in entries[:max_items]:
            title = clean_text(getattr(entry, "title", ""))
            link = getattr(entry, "link", "")
            if not title or not link:
                logger.warning("item_dropped", source_id=self.source_id.value, reason="missing_title_or_url")
                continue
            pub_date, inferred = self._parse_date(entry, fetched_at)
            canonical_url = canonicalize(link)
            summary = clean_text(getattr(entry, "summary", "")) or None
            items.append(
                Item(
                    item_id=item_id_for_url(canonical_url),
                    university=self.university,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    url=canonical_url,
                    pub_date=pub_date,
                    summary=summary,
                    fetched_at=fetched_at,
                    date_inferred=inferred,
                    needs_classification=self.needs_classification,
                )
            )
        return items

    def _parse_date(self, entry: object, fetched_at: datetime) -> tuple[datetime, bool]:
        for attr in ("published", "updated", "created"):
            value = getattr(entry, attr, None)
            if not value:
                continue
            try:
                parsed = date_parser.parse(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=CN_TZ)
                return parsed, False
            except (ValueError, TypeError, OverflowError):
                continue
        return fetched_at, True
