from __future__ import annotations

from typing import ClassVar
from crawler.fetchers.base import BaseFetcher
from crawler.schema import SourceId, FetchResult, Item
from crawler.utils.http import HttpClient
from crawler.utils.text import clean_text
from crawler.utils.url import canonicalize, item_id_for_url
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from crawler.utils.time import APP_TZ
import re
from dateutil import parser as date_parser
import structlog

logger = structlog.get_logger()

class StaticFetcher(BaseFetcher):
    """Generic fetcher for static HTML lists with customizable selectors."""
    
    BASE_URL: ClassVar[str] = ""
    LIST_PATHS: ClassVar[tuple[str, ...]] = ()
    ITEM_SELECTOR: ClassVar[str] = ""
    TITLE_SELECTOR: ClassVar[str] = "a"
    DATE_SELECTOR: ClassVar[str] = "span"

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
                url = canonicalize(path, self.base_url)
                resp = self.http_client.get(url)
                items.extend(self._parse_html(resp.text))
            
            # Dedupe and limit
            seen = set()
            unique_items = []
            for item in items:
                if item.item_id not in seen:
                    unique_items.append(item)
                    seen.add(item.item_id)
            
            return FetchResult(self.source_id, unique_items[:max_items], True)
        except Exception as e:
            logger.warning("fetch_failed", source_id=self.source_id.value, error=str(e))
            return FetchResult(self.source_id, [], False, str(e))

    def _parse_html(self, html: str) -> list[Item]:
        soup = BeautifulSoup(html, "lxml")
        nodes = soup.select(self.ITEM_SELECTOR)
        items = []
        fetched_at = datetime.now(timezone.utc)
        
        for node in nodes:
            title_node = node.select_one(self.TITLE_SELECTOR)
            if not title_node or not title_node.get("href"):
                continue
            
            title = clean_text(title_node.get_text(strip=True) or title_node.get("title", ""))
            href = title_node.get("href")
            
            if not title or len(title) < 2:
                continue
                
            url = canonicalize(href, self.base_url)
            
            # Date extraction
            date_text = ""
            if self.DATE_SELECTOR:
                date_node = node.select_one(self.DATE_SELECTOR)
                if date_node:
                    date_text = date_node.get_text(strip=True)
            
            pub_date, inferred = self._extract_date(date_text, fetched_at)
            
            items.append(Item(
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
                needs_classification=self.needs_classification
            ))
        return items

    def _extract_date(self, text: str, fetched_at: datetime) -> tuple[datetime, bool]:
        if not text:
            return fetched_at, True
        match = re.search(r"(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2})", text)
        if not match:
            # Try MM-DD if current year is implied
            match = re.search(r"(\d{1,2}[-/.月]\d{1,2})", text)
            if match:
                raw = f"{datetime.now().year}-{match.group(1).replace('月', '-').replace('日', '')}"
            else:
                return fetched_at, True
        else:
            raw = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
        
        try:
            return date_parser.parse(raw).replace(tzinfo=APP_TZ), False
        except (ValueError, TypeError, OverflowError):
            return fetched_at, True

class PkuZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.PKU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "北京大学"
    BASE_URL = "https://admission.pku.edu.cn/"
    LIST_PATHS = ("/tzgg/index.htm",)
    ITEM_SELECTOR = "ul.zsxx_cont_list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span.zsxxCont_list_time"

class RucZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.RUC_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中国人民大学"
    BASE_URL = "https://rdzs.ruc.edu.cn/"
    LIST_PATHS = ("/cms/item/?cat=72&parent=1",)
    ITEM_SELECTOR = ".y_list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class BuaaZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.BUAA_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "北京航空航天大学"
    BASE_URL = "https://zs.buaa.edu.cn/"
    LIST_PATHS = ("/tzgg.htm",)
    ITEM_SELECTOR = "ul.twostage_tzgg_list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span.twostage_tzgg_time"

class BitZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.BIT_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "北京理工大学"
    BASE_URL = "https://admission.bit.edu.cn/"
    LIST_PATHS = ("/f/newsCenter/articles/0278fac54ee5438f8d16717a277d38eb",)
    ITEM_SELECTOR = "div.news-list-box, div.article-list li, div.content-box a[href*='/article/']"
    
    def _parse_html(self, html: str) -> list[Item]:
        soup = BeautifulSoup(html, "lxml")
        items = []
        fetched_at = datetime.now(timezone.utc)
        
        # BIT specific: Find links that look like articles
        links = soup.select("a[href*='/article/']")
        for a in links:
            title = clean_text(a.get_text(strip=True) or a.get("title", ""))
            if not title or len(title) < 10: continue
            url = canonicalize(a.get("href"), self.base_url)
            items.append(Item(
                item_id=item_id_for_url(url),
                university=self.university,
                source_id=self.source_id,
                source_name=self.source_name,
                title=title,
                url=url,
                pub_date=fetched_at,
                summary=None,
                fetched_at=fetched_at,
                date_inferred=True,
                needs_classification=self.needs_classification
            ))
        return items

class CauZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.CAU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中国农业大学"
    BASE_URL = "https://jwzs.cau.edu.cn/"
    LIST_PATHS = ("/col/col4528/index.html",)
    ITEM_SELECTOR = "div.list-box"
    
    def _parse_html(self, html: str) -> list[Item]:
        # CAU uses datastore XML inside HTML script tag
        items = []
        fetched_at = datetime.now(timezone.utc)
        
        # Extract records from datastore XML strings
        records = re.findall(r"<record><!\[CDATA\[(.*?)]]></record>", html, re.DOTALL)
        for rec_html in records:
            soup = BeautifulSoup(rec_html, "lxml")
            link = soup.select_one("a")
            if not link: continue
            
            title = clean_text(link.select_one(".item-tit").get_text(strip=True) if link.select_one(".item-tit") else link.get_text(strip=True))
            href = link.get("href")
            url = canonicalize(href, self.base_url)
            
            # Date in <div class="date">
            date_node = soup.select_one(".date")
            pub_date = fetched_at
            inferred = True
            if date_node:
                dt_txt = date_node.get_text(" ", strip=True)
                pub_date, inferred = self._extract_date(dt_txt, fetched_at)
                
            items.append(Item(
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
                needs_classification=self.needs_classification
            ))
        return items

class TjuZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.TJU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "天津大学"
    BASE_URL = "https://zs.tju.edu.cn/"
    LIST_PATHS = ("/ym21/bkzn/tzgg.htm",)
    ITEM_SELECTOR = "ul.clear li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class WhuZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.WHU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "武汉大学"
    BASE_URL = "https://aoff.whu.edu.cn/"
    LIST_PATHS = ("/zsxx1/tzgg.htm",)
    ITEM_SELECTOR = "li.wow.slideInUp"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class HustZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.HUST_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "华中科技大学"
    BASE_URL = "https://zsb.hust.edu.cn/"
    LIST_PATHS = ("/bkzn/tzgg.htm",)
    ITEM_SELECTOR = "li.list-item"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class CsuZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.CSU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中南大学"
    BASE_URL = "https://zhaosheng.csu.edu.cn/"
    LIST_PATHS = ("/zsjz1.htm", "/zszx/zszx.htm")
    ITEM_SELECTOR = "div.zsjz-list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class NudtZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.NUDT_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "国防科技大学"
    BASE_URL = "https://www.nudt.edu.cn/"
    LIST_PATHS = ("/bkzs/xxgk/tzgg/index.htm",)
    ITEM_SELECTOR = "ul.article_list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"
