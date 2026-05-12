from __future__ import annotations

from datetime import datetime, timezone
import re

from bs4 import BeautifulSoup
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


class XjtuZsbFetcher(BaseFetcher):
    """西交招办，static HTML 列表（webplus CMS），前置一个 JS challenge 反爬。

    Challenge 流程（服务器明文告诉客户端答案，仅过滤无脚本 bot）：
      1. GET list page → 服务器返回 challenge HTML（含 challengeId + answer 写在 JS 变量里）
      2. 从 HTML regex 提取 challengeId + answer
      3. POST /dynamic_challenge 含 {challenge_id, answer, browser_info}
         → 服务器 Set-Cookie client_id（24h 有效）
      4. 用 cookie 重 GET list page → 拿到真实 webplus 内容

    样页 URL 格式 /info/1655/6920.htm 是标准 webplus 路径。
    """
    source_id = SourceId.XJTU_ZSB
    source_name = "本科招办"
    university = "西安交通大学"
    needs_classification = False
    BASE_URL = "https://zs.xjtu.edu.cn/"
    LIST_PATH = "/zsxx1/zskx.htm"
    CHALLENGE_PATH = "/dynamic_challenge"

    CHALLENGE_ID_RE = re.compile(r'challengeId\s*=\s*"([^"]+)"')
    ANSWER_RE = re.compile(r'answer\s*=\s*(\d+)')

    def __init__(self, base_url: str | None = None, http_client: HttpClient | None = None):
        self.base_url = base_url or self.BASE_URL
        self.http_client = http_client or HttpClient()  # 未使用，留接口一致

    def fetch(self, max_items: int = 30) -> FetchResult:
        try:
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            )
            with httpx.Client(
                base_url=self.base_url.rstrip("/"),
                headers={**DEFAULT_HEADERS, "User-Agent": ua},
                timeout=10,
                follow_redirects=True,
            ) as client:
                # Step 1: GET list page → 拿到 challenge HTML
                initial = client.get(self.LIST_PATH)
                initial.raise_for_status()
                html_text = initial.text

                # 如已含真实列表（cookie 已存在或服务器降级行为），直接解析
                if "wp_article_list" in html_text or "Article_Title" in html_text:
                    save_raw(self.source_id, initial.content)
                    items = self._parse_list(html_text)
                else:
                    # Step 2: 提取 challenge 参数
                    cid_match = self.CHALLENGE_ID_RE.search(html_text)
                    ans_match = self.ANSWER_RE.search(html_text)
                    if not cid_match or not ans_match:
                        raise RuntimeError("xjtu challenge HTML missing challengeId/answer")
                    challenge_id = cid_match.group(1)
                    answer = int(ans_match.group(1))

                    # Step 3: POST challenge endpoint（echo 服务器明文给的 answer）
                    chr_resp = client.post(
                        self.CHALLENGE_PATH,
                        json={
                            "challenge_id": challenge_id,
                            "answer": answer,
                            "browser_info": {
                                "userAgent": ua,
                                "language": "zh-CN",
                                "platform": "Win32",
                                "cookieEnabled": True,
                                "hardwareConcurrency": 8,
                                "deviceMemory": 8,
                                "timezone": "Asia/Shanghai",
                            },
                        },
                    )
                    chr_resp.raise_for_status()
                    chr_payload = chr_resp.json()
                    if not chr_payload.get("success"):
                        raise RuntimeError(f"xjtu challenge response not success: {chr_payload}")
                    # cookie 自动由 httpx.Client 持久化

                    # Step 4: 重 GET list page，应返回真实内容
                    real = client.get(self.LIST_PATH)
                    real.raise_for_status()
                    save_raw(self.source_id, real.content)
                    items = self._parse_list(real.text)

            items = items[:max_items]
            logger.info("fetch_success", source_id=self.source_id.value, fetched_count=len(items))
            return FetchResult(self.source_id, items, True)
        except Exception as exc:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(exc))
            return FetchResult(self.source_id, [], False, str(exc))

    def _parse_list(self, html: str) -> list[Item]:
        """西交招生快讯页结构（实测）：
        <section class="TextList">
          <ul>
            <li>
              <a class="flex" href="../info/1655/6930.htm" title="..." target="_blank">
                <i class="zc">招生快讯</i>
                <p>标题文字</p>
                <b>2026.02.10</b>
              </a>
            </li>
          </ul>
        </section>
        相对 URL 形如 "../info/1655/6930.htm" 需要相对 LIST_PATH 解析。
        """
        soup = BeautifulSoup(html, "lxml")
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        # 选 list 范围内的 a 标签（避免 navbar 等其他 a）
        for a in soup.select("section.TextList ul li a[href], .TextList li a[href]"):
            href = a.get("href", "")
            if not href:
                continue
            # 标题优先用 a 内 <p>，否则 title attr，否则 a.get_text
            p_node = a.select_one("p")
            title = clean_text(
                p_node.get_text(" ", strip=True) if p_node
                else (a.get("title", "") or a.get_text(" ", strip=True))
            )
            if not title or len(title) < 5:
                continue
            # 相对 URL 以 LIST_PATH 为 base 解析（".." 才能 resolve 正确）
            list_url = canonicalize(self.LIST_PATH, self.base_url)
            url = canonicalize(href, list_url)
            # 日期在 <b> 内
            b_node = a.select_one("b")
            date_text = clean_text(b_node.get_text(strip=True) if b_node else "")
            pub_date, inferred = self._extract_date(date_text, fetched_at)
            items.append(
                Item(
                    item_id=item_id_for_url(url),
                    university=self.university,
                    source_id=self.source_id,
                    source_name=self.source_name,
                    title=title,
                    url=url,
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

    def _extract_date(self, text: str, fetched_at: datetime) -> tuple[datetime, bool]:
        if not text:
            return fetched_at, True
        match = re.search(r"(20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2})", text)
        if not match:
            return fetched_at, True
        raw = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        try:
            return date_parser.parse(raw).replace(tzinfo=APP_TZ), False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True
