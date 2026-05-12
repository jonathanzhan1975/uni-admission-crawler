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


class TongjiZsbFetcher(BaseFetcher):
    """同济大学招办，Nuxt SPA 站点（bkzs.tongji.edu.cn）但用第三方 SaaS
    `edudata.cn` 作为内容后端。API 命名为 RPC 风格（`.` 分隔）。

    API 调用方式（通过用户 F12 抓取确认）：
      POST https://ag-tongji-pc.edudata.cn/youzy.youz.cc.page.contentpage.query
      Headers: Origin/Referer: https://bkzs.tongji.edu.cn (CORS)
      Body (JSON):
        {
          "keyword": null,
          "categoryName": null,
          "collegeMenuIds": ["625e231cc703f31c0b2b4f88"],
          "order": "top_sort_pd_desc",
          "pageIndex": 1,
          "pageSize": 20
        }

    `collegeMenuIds` 中的 UUID 是同济招办「通知公告」分类 ID（一个数组，POC 仅订 1 个）。
    """
    source_id = SourceId.TONGJI_ZSB
    source_name = "本科招办"
    university = "同济大学"
    needs_classification = False
    BASE_URL = "https://bkzs.tongji.edu.cn/"
    API_URL = "https://ag-tongji-pc.edudata.cn/youzy.youz.cc.page.contentpage.query"
    CATEGORY_ID = "625e231cc703f31c0b2b4f88"  # 招办公告分类

    def __init__(self, base_url: str | None = None, http_client: HttpClient | None = None):
        self.base_url = base_url or self.BASE_URL
        self.http_client = http_client or HttpClient()

    def fetch(self, max_items: int = 30) -> FetchResult:
        try:
            payload = {
                "keyword": None,
                "categoryName": None,
                "collegeMenuIds": [self.CATEGORY_ID],
                "order": "top_sort_pd_desc",
                "pageIndex": 1,
                "pageSize": max_items,
            }
            response = self.http_client.post_json(
                self.API_URL,
                payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Origin": self.base_url.rstrip("/"),
                    "Referer": self.base_url,
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/147.0.0.0 Safari/537.36"
                    ),
                    # YouZi 平台租户标识；U-Sign 是客户端 JS 算的 MD5 动态签名，
                    # 这里不带，赌服务器不实际校验。若仍 401 则 known_degraded。
                    "U-Dfs": "pc.tongji",
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
        """JSON 结构待第一次成功响应后确认；这里覆盖几种 RPC 风格 SaaS 常见结构。"""
        # 常见外层: {data: {list: [...]}} or {data: {records: [...]}} or {result: [...]}
        records = (
            payload.get("data", {}).get("list")
            or payload.get("data", {}).get("records")
            or payload.get("data", {}).get("items")
            or payload.get("data", {}).get("rows")
            or payload.get("data")  # 顶层就是数组
            or payload.get("list")
            or payload.get("result")
            or []
        )
        if isinstance(records, dict):
            # 可能是 {list: [...], total: N} 包一层
            records = (
                records.get("list")
                or records.get("records")
                or records.get("items")
                or records.get("rows")
                or []
            )
        if not isinstance(records, list):
            raise RuntimeError(f"tongji api list missing, keys: {list(payload.keys())}")

        fetched_at = datetime.now(timezone.utc)
        items: list[Item] = []
        for row in records[:max_items]:
            # 兼容常见字段名
            title = clean_text(str(
                row.get("title") or row.get("name") or row.get("contentTitle") or row.get("subject") or ""
            ))
            article_id = (
                row.get("id") or row.get("contentId") or row.get("articleId") or row.get("uuid")
            )
            if not title or article_id is None:
                logger.warning("item_dropped", source_id=self.source_id.value, reason="missing_title_or_url")
                continue
            # URL 拼接：通常详情页是 bkzs.tongji.edu.cn 前端路由
            link_field = clean_text(str(row.get("url") or row.get("linkUrl") or row.get("link") or ""))
            if link_field and link_field.startswith("http"):
                final_url = link_field
            else:
                # 同济前端详情页路由（猜测，待真实 sample URL 验证）
                final_url = f"/article/{article_id}"
            canonical_url = canonicalize(final_url, self.base_url)
            # 日期：可能是 epoch ms 或 ISO string
            date_field = (
                row.get("publishDate")
                or row.get("publishTime")
                or row.get("releaseDate")
                or row.get("releaseTime")
                or row.get("createTime")
                or row.get("pd")  # top_sort_pd_desc 暗示 pd 字段
            )
            pub_date, inferred = self._parse_date_flexible(date_field, fetched_at)
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

    def _parse_date_flexible(self, value, fetched_at: datetime) -> tuple[datetime, bool]:
        if value is None or value == "":
            return fetched_at, True
        # epoch ms
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value) / 1000, tz=APP_TZ), False
            except (OverflowError, OSError, ValueError):
                return fetched_at, True
        # ISO string
        try:
            return date_parser.parse(str(value)).replace(tzinfo=APP_TZ), False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True
