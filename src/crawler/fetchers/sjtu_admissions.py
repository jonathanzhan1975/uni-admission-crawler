from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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


class SjtuAdmissionsFetcher(BaseFetcher):
    source_id = SourceId.SJTU_ADMISSIONS
    source_name = "本科招办"
    university = "上海交通大学"
    needs_classification = False
    BASE_URL = "https://admissions.sjtu.edu.cn/"
    NEWS_LIST_PATH = "/rnapi/newsList"
    IMPORTANT_SUBJECT_ID = 3810134

    def __init__(self, base_url: str | None = None, http_client: HttpClient | None = None):
        self.base_url = base_url or self.BASE_URL
        self.http_client = http_client or HttpClient()

    def fetch(self, max_items: int = 30) -> FetchResult:
        try:
            response = self.http_client.post_json(
                canonicalize(self.NEWS_LIST_PATH, self.base_url),
                {
                    "page": 1,
                    "pageSize": max_items,
                    "subjectsID": self.IMPORTANT_SUBJECT_ID,
                    "contentTitle": "",
                },
            )
            save_raw(self.source_id, response.content)
            items = self._parse_payload(response.json(), max_items)
            logger.info("fetch_success", source_id=self.source_id.value, fetched_count=len(items))
            return FetchResult(self.source_id, items, True)
        except Exception as exc:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(exc))
            return FetchResult(self.source_id, [], False, str(exc))

    def _parse_payload(self, payload: dict, max_items: int = 30) -> list[Item]:
        if payload.get("code") != 0:
            raise RuntimeError(f"sjtu admissions api code={payload.get('code')}")
        rows = payload.get("data", {}).get("list", [])
        if not isinstance(rows, list):
            raise RuntimeError("sjtu admissions api list missing")

        fetched_at = datetime.now(timezone.utc)
        items: list[Item] = []
        for row in rows[:max_items]:
            title = clean_text(str(row.get("contentTitle") or ""))
            content_id = row.get("contentsID")
            if not title or content_id is None:
                logger.warning("item_dropped", source_id=self.source_id.value, reason="missing_title_or_url")
                continue
            jump_url = clean_text(str(row.get("jumpUrl") or ""))
            url = jump_url or f"/newDetails?contentsID={content_id}"
            canonical_url = canonicalize(url, self.base_url)
            pub_date, inferred = self._parse_date(str(row.get("cTime") or ""), fetched_at)
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

    def _parse_date(self, text: str, fetched_at: datetime) -> tuple[datetime, bool]:
        if not text:
            return fetched_at, True
        try:
            return date_parser.parse(text).replace(tzinfo=CN_TZ), False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True
