from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as date_parser
import httpx
import structlog

from crawler.fetchers.base import BaseFetcher
from crawler.pipeline.archive import save_raw
from crawler.schema import FetchResult, Item, SourceId
from crawler.utils.http import HttpClient, DEFAULT_HEADERS
from crawler.utils.text import clean_text
from crawler.utils.time import APP_TZ
from crawler.utils.url import canonicalize, item_id_for_url


logger = structlog.get_logger()


class NjuZsbFetcher(BaseFetcher):
    """南京大学招办，SPA 站点暴露同源 POST JSON API。

    API 调用方式（通过用户 F12 抓取确认）：
      POST https://bkzs.nju.edu.cn/f/newsCenter/ajax_article_list?ts={timestamp_ms}
      Form Data: pageNo=1&pageSize=N&categoryId=<UUID>
      Required Headers: Origin + Referer (front-end URL)

    详情页 URL 模式（来自用户给的 sample 页）：
      https://bkzs.nju.edu.cn/static/front/nju/basic/html_cms/frontViewArticle1.html?id={article_id}
    """
    source_id = SourceId.NJU_ZSB
    source_name = "本科招办"
    university = "南京大学"
    needs_classification = False
    BASE_URL = "https://bkzs.nju.edu.cn/"
    LIST_PATH = "/f/newsCenter/ajax_article_list"
    # 通知公告分类的 UUID（来自前端 frontList.html?id=...）
    CATEGORY_ID = "c8673b83bc704353aff9f917cc1e16b2"
    DETAIL_PATH_TEMPLATE = "/static/front/nju/basic/html_cms/frontViewArticle1.html?id={article_id}"

    def __init__(self, base_url: str | None = None, http_client: HttpClient | None = None):
        self.base_url = base_url or self.BASE_URL
        self.http_client = http_client or HttpClient()

    def fetch(self, max_items: int = 30) -> FetchResult:
        """两步流程：
          Step 1: GET /f/ajax_get_csrfToken → 服务器 Set-Cookie zhaosheng.nju.session.id
                  并在 response body 返回 {data: "TOKEN,TOKEN,TOKEN,TOKEN", jessionid: "..."}
          Step 2: POST /f/newsCenter/ajax_article_list 携带:
                  - cookie (httpx.Client 自动持久化)
                  - header csrf-token: <第一个逗号分隔的 token>
                  - header x-requested-with: XMLHttpRequest
                  - header x-requested-time: <与 URL ts 相同的 ms>
                  - form body: pageNo / pageSize / categoryId
        """
        try:
            referer = (
                f"{self.base_url.rstrip('/')}/static/front/nju/basic/html_cms/"
                f"frontList.html?id={self.CATEGORY_ID}"
            )
            with httpx.Client(
                base_url=self.base_url.rstrip("/"),
                headers={
                    **DEFAULT_HEADERS,
                    "Origin": self.base_url.rstrip("/"),
                    "Referer": referer,
                },
                timeout=10,
                follow_redirects=True,
            ) as client:
                # Step 1: 拿 csrf token + 让服务器 Set-Cookie 持久化 session
                ts1 = int(datetime.now(timezone.utc).timestamp() * 1000)
                csrf_resp = client.get(
                    f"/f/ajax_get_csrfToken?ts={ts1}",
                    headers={
                        "X-Requested-With": "XMLHttpRequest",
                        "X-Requested-Time": str(ts1),
                    },
                )
                csrf_resp.raise_for_status()
                # data 字段格式: "TOKEN,TOKEN,TOKEN,TOKEN" — 取第一个
                csrf_data = str(csrf_resp.json().get("data") or "")
                csrf_token = csrf_data.split(",")[0].strip() if csrf_data else ""
                if not csrf_token:
                    raise RuntimeError("nju csrf token missing in response.data")

                # Step 2: POST 列表 API
                ts2 = int(datetime.now(timezone.utc).timestamp() * 1000)
                list_resp = client.post(
                    f"/f/newsCenter/ajax_article_list?ts={ts2}",
                    data={
                        "pageNo": "1",
                        "pageSize": str(max_items),
                        "categoryId": self.CATEGORY_ID,
                    },
                    headers={
                        "csrf-token": csrf_token,
                        "X-Requested-With": "XMLHttpRequest",
                        "X-Requested-Time": str(ts2),
                    },
                )
                list_resp.raise_for_status()
                save_raw(self.source_id, list_resp.content)
                items = self._parse_payload(list_resp.json(), max_items)
            logger.info("fetch_success", source_id=self.source_id.value, fetched_count=len(items))
            return FetchResult(self.source_id, items, True)
        except Exception as exc:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(exc))
            return FetchResult(self.source_id, [], False, str(exc))

    def _parse_payload(self, payload: dict, max_items: int = 30) -> list[Item]:
        """实际响应结构 (经 reviewer 实测):
          payload.data.page.list = [{id, title, url, releaseDate (epoch ms), ...}]
        """
        page = payload.get("data", {}).get("page", {})
        records = page.get("list") if isinstance(page, dict) else None
        if not isinstance(records, list):
            raise RuntimeError("nju admissions api data.page.list missing")

        fetched_at = datetime.now(timezone.utc)
        items: list[Item] = []
        for row in records[:max_items]:
            title = clean_text(str(row.get("title") or ""))
            article_id = row.get("id")
            url_field = clean_text(str(row.get("url") or ""))
            if not title or not (article_id or url_field):
                logger.warning("item_dropped", source_id=self.source_id.value, reason="missing_title_or_url")
                continue
            # 优先用响应里的 url（指向 frontViewArticle1.html?id=...）
            final_url = url_field or self.DETAIL_PATH_TEMPLATE.format(article_id=article_id)
            canonical_url = canonicalize(final_url, self.base_url)
            # releaseDate 是 epoch ms
            release_ms = row.get("releaseDate")
            pub_date, inferred = self._epoch_ms_to_date(release_ms, fetched_at)
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

    def _epoch_ms_to_date(self, value, fetched_at: datetime) -> tuple[datetime, bool]:
        try:
            ms = int(value)
            return datetime.fromtimestamp(ms / 1000, tz=APP_TZ), False
        except (TypeError, ValueError, OverflowError):
            return fetched_at, True

    def _parse_date(self, text: str, fetched_at: datetime) -> tuple[datetime, bool]:
        if not text:
            return fetched_at, True
        try:
            return date_parser.parse(text).replace(tzinfo=APP_TZ), False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True
