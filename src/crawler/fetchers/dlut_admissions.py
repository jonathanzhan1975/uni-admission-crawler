from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as date_parser
import structlog

from crawler.fetchers.base import BaseFetcher
from crawler.pipeline.archive import save_raw
from crawler.schema import FetchResult, Item, SourceId
from crawler.utils.http import HttpClient
from crawler.utils.text import clean_text
from crawler.utils.time import APP_TZ
from crawler.utils.url import canonicalize, item_id_for_url


logger = structlog.get_logger()


class DlutZsbFetcher(BaseFetcher):
    """大连理工招办，SPA 站点 (zs.dlut.edu.cn) 但暴露了同源 JSON API。

    API: GET /apiV2025/portal/disclosure/zsNews/page?pageNum=1&pageSize=N&orderByColumn=&isAsc=desc
    返回：{ code: 200, data: { records: [ {resourceId, resourceTitle, resourcePublishTime, linkUrl, ...}, ... ], total: N } }

    URL 构造：优先用 record 的 linkUrl（如有，常指向微信公众号原文）；
    否则构造 https://zs.dlut.edu.cn/zsNewsDetail?resourceId={resourceId}（匹配站内详情页路径）。
    """
    source_id = SourceId.DLUT_ZSB
    source_name = "本科招办"
    university = "大连理工大学"
    needs_classification = False
    BASE_URL = "https://zs.dlut.edu.cn/"
    LIST_PATH = "/apiV2025/portal/disclosure/zsNews/page"

    def __init__(self, base_url: str | None = None, http_client: HttpClient | None = None):
        self.base_url = base_url or self.BASE_URL
        self.http_client = http_client or HttpClient()

    def fetch(self, max_items: int = 30) -> FetchResult:
        try:
            url = (
                canonicalize(self.LIST_PATH, self.base_url)
                + f"?pageNum=1&pageSize={max_items}&orderByColumn=&isAsc=desc"
            )
            response = self.http_client.get(
                url,
                headers={"Referer": f"{self.base_url.rstrip('/')}/zsNews"},
            )
            save_raw(self.source_id, response.content)
            items = self._parse_payload(response.json(), max_items)
            logger.info("fetch_success", source_id=self.source_id.value, fetched_count=len(items))
            return FetchResult(self.source_id, items, True)
        except Exception as exc:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(exc))
            return FetchResult(self.source_id, [], False, str(exc))

    def _parse_payload(self, payload: dict, max_items: int = 30) -> list[Item]:
        if payload.get("code") != 200:
            raise RuntimeError(f"dlut admissions api code={payload.get('code')}")
        records = payload.get("data", {}).get("records", [])
        if not isinstance(records, list):
            raise RuntimeError("dlut admissions api records missing")

        fetched_at = datetime.now(timezone.utc)
        items: list[Item] = []
        for row in records[:max_items]:
            title = clean_text(str(row.get("resourceTitle") or ""))
            resource_id = row.get("resourceId")
            if not title or resource_id is None:
                logger.warning("item_dropped", source_id=self.source_id.value, reason="missing_title_or_url")
                continue
            link_url = clean_text(str(row.get("linkUrl") or ""))
            url = link_url or f"/zsNewsDetail?resourceId={resource_id}"
            canonical_url = canonicalize(url, self.base_url)
            pub_date, inferred = self._parse_date(str(row.get("resourcePublishTime") or ""), fetched_at)
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
            return date_parser.parse(text).replace(tzinfo=APP_TZ), False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True
