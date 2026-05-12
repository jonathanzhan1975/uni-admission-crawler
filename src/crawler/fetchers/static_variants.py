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
        self.http_client = http_client or HttpClient(verify=False)

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

class UestcZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.UESTC_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "电子科技大学"
    BASE_URL = "https://zs.uestc.edu.cn/"
    LIST_PATHS = ("/category/7.html",)
    ITEM_SELECTOR = "li.ellipsis"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = None

class LzuZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.LZU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "兰州大学"
    BASE_URL = "https://zsb.lzu.edu.cn/"
    LIST_PATHS = ("/zhaoshengdongtai/index.html",)
    ITEM_SELECTOR = "ol li, ul.news-list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class SysuZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.SYSU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中山大学"
    BASE_URL = "https://admission.sysu.edu.cn/"
    LIST_PATHS = ("/",)
    ITEM_SELECTOR = "ul.left_box li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class CquZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.CQU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "重庆大学"
    BASE_URL = "https://zhaosheng.cqu.edu.cn/"
    LIST_PATHS = ("/",)
    ITEM_SELECTOR = "ul.datenews li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class SduZsbFetcher(StaticFetcher):
    DEFAULT_SOURCE_ID = SourceId.SDU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "山东大学"
    BASE_URL = "https://www.bkzs.sdu.edu.cn/"
    LIST_PATHS = ("/",)
    ITEM_SELECTOR = "#tab_a1 li"
    TITLE_SELECTOR = ".tit a"
    DATE_SELECTOR = ".date"

class JluZsbFetcher(StaticFetcher):
    """吉林大学招办，传统 static CMS（ul.newslist > li > a[title] > span[date]）"""
    DEFAULT_SOURCE_ID = SourceId.JLU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "吉林大学"
    BASE_URL = "https://zsb.jlu.edu.cn/"
    LIST_PATHS = ("/list/2.html",)
    ITEM_SELECTOR = "ul.newslist li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class NwafuZsbFetcher(StaticFetcher):
    """西北农林招办，传统 static（ul.list > li > span[日期]+a[title][href]）"""
    DEFAULT_SOURCE_ID = SourceId.NWAFU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "西北农林科技大学"
    BASE_URL = "https://zhshw.nwsuaf.edu.cn/"
    LIST_PATHS = ("/zszn/zsdt/index.htm",)
    ITEM_SELECTOR = "ul.list li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "span"

class BnuZsbFetcher(StaticFetcher):
    """北师大招办，static CMS。结构：
    <ul class="reset">
      <li>
        <a href="tslx/qjjh/...html">2026年强基计划招生简章</a>
        <time datetime='2026-04-10'>
      </li>
    </ul>
    """
    DEFAULT_SOURCE_ID = SourceId.BNU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "北京师范大学"
    BASE_URL = "https://admission.bnu.edu.cn/"
    LIST_PATHS = ("/",)
    ITEM_SELECTOR = "ul.reset li"
    TITLE_SELECTOR = "a"
    DATE_SELECTOR = "time"


class HnuZsbFetcher(StaticFetcher):
    """湖大招办，static CMS。a 自身是 item，标题/日期在子 div 里。
    <a href="info/1186/7295.htm" class="news-item">
      <div class="news-timeDate">
        <div class="news-monthDay">08</div>
        <div class="news-year">2026-04</div>
      </div>
      <div class="news-info"><div class="news-title">标题</div>...</div>
    </a>
    """
    DEFAULT_SOURCE_ID = SourceId.HNU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "湖南大学"
    BASE_URL = "https://admi.hnu.edu.cn/"
    LIST_PATHS = ("/",)
    ITEM_SELECTOR = "a.news-item"

    def _parse_html(self, html: str) -> list[Item]:
        soup = BeautifulSoup(html, "lxml")
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        for a in soup.select(self.ITEM_SELECTOR):
            href = a.get("href", "")
            if not href:
                continue
            # 标题：news-info 里通常有 title div/span 或仅文本
            info_node = a.select_one(".news-info, .news-title")
            title = clean_text(info_node.get_text(" ", strip=True) if info_node else a.get_text(" ", strip=True))
            # 移除 news-info 里的日期/作者 prefix
            if not title or len(title) < 5:
                continue
            url = canonicalize(href, self.base_url)
            year_node = a.select_one(".news-year")
            day_node = a.select_one(".news-monthDay")
            year_month = clean_text(year_node.get_text(strip=True) if year_node else "")
            day = clean_text(day_node.get_text(strip=True) if day_node else "")
            date_text = f"{year_month}-{day}" if year_month and day else year_month
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
                needs_classification=self.needs_classification,
            ))
        return items


class XmuZsbFetcher(StaticFetcher):
    """厦大招办，static。结构：
    <div class="zszx-item-...">  (parent container)
      <div class="zszx-day">08</div>
      <div class="zszx-month">2026-05</div>
      <div class="zszx-item-title">
        <a href="info/1174/36282.htm" target="_blank" title="标题">标题</a>
      </div>
    </div>
    """
    DEFAULT_SOURCE_ID = SourceId.XMU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "厦门大学"
    BASE_URL = "https://zs.xmu.edu.cn/"
    LIST_PATHS = ("/",)
    ITEM_SELECTOR = "div.zszx-item-title"  # 仅 title div, 日期 sibling 通过 parent 找

    def _parse_html(self, html: str) -> list[Item]:
        soup = BeautifulSoup(html, "lxml")
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        for title_div in soup.select(self.ITEM_SELECTOR):
            a = title_div.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            title = clean_text(a.get("title", "") or a.get_text(" ", strip=True))
            if not title or len(title) < 5 or not href:
                continue
            url = canonicalize(href, self.base_url)
            # 日期在 parent 的 sibling .zszx-month + .zszx-day
            parent = title_div.parent
            month_node = parent.select_one(".zszx-month") if parent else None
            day_node = parent.select_one(".zszx-day") if parent else None
            ym = clean_text(month_node.get_text(strip=True) if month_node else "")
            d = clean_text(day_node.get_text(strip=True) if day_node else "")
            date_text = f"{ym}-{d}" if ym and d else ym
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
                needs_classification=self.needs_classification,
            ))
        return items


class MucZsbFetcher(StaticFetcher):
    """中央民族大学招办，结构特殊：title 在 p.dh 里，href 在父 a 上。
    <li class="ml-item">
      <a href="/content/zs/qjjh/...htm">
        <p class="dh">标题</p>
        <span>YYYY-MM-DD</span>
      </a>
    </li>
    """
    DEFAULT_SOURCE_ID = SourceId.MUC_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中央民族大学"
    BASE_URL = "https://zb.muc.edu.cn/"
    LIST_PATHS = ("/content/zs/9a649c21-f0cf-11ee-a4af-00163e36a0b0.htm",)  # 通知公告
    ITEM_SELECTOR = "li.ml-item"

    def _parse_html(self, html: str) -> list[Item]:
        soup = BeautifulSoup(html, "lxml")
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        for li in soup.select(self.ITEM_SELECTOR):
            a = li.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            p_dh = a.select_one("p.dh")
            span = a.select_one("span")
            title = clean_text(p_dh.get_text(strip=True) if p_dh else "")
            if not title or len(title) < 5 or not href:
                continue
            url = canonicalize(href, self.base_url)
            date_text = clean_text(span.get_text(strip=True) if span else "")
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
                needs_classification=self.needs_classification,
            ))
        return items


class HitwhZsbFetcher(StaticFetcher):
    """哈工大（威海）招办，自定义 static CMS：
    <div class="news-list">
      <div class="news-item">
        <a class="title" href="/home/article/details?id=NNNN">标题</a>
        <p class="date">发布时间: YYYY-MM-DD</p>
      </div>
    """
    DEFAULT_SOURCE_ID = SourceId.HITWH_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "哈尔滨工业大学（威海）"
    BASE_URL = "https://zsb.hitwh.edu.cn/"
    LIST_PATHS = ("/home/article/index?col=10",)  # 招生简章栏目
    ITEM_SELECTOR = "div.news-list > div.news-item"
    TITLE_SELECTOR = "a.title"
    DATE_SELECTOR = "p.date"


class NankaiZsbFetcher(StaticFetcher):
    """南开大学招办，自定义 CMS：a[target=_blank][href^=/20YY-MM-DD/]
    与 BIT 类似，HTML 结构不规则，需 override _parse_html 按 href 模式直接选 a 标签。
    """
    DEFAULT_SOURCE_ID = SourceId.NANKAI_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "南开大学"
    BASE_URL = "https://zsb.nankai.edu.cn/"
    LIST_PATHS = ("/Index/zhaosheng.html",)
    ITEM_SELECTOR = "a[target='_blank']"  # placeholder; _parse_html overrides

    def _parse_html(self, html: str) -> list[Item]:
        soup = BeautifulSoup(html, "lxml")
        items: list[Item] = []
        fetched_at = datetime.now(timezone.utc)
        seen_ids: set[str] = set()
        # 真实文章链接形如 /2026-04-07/1792（日期/文章ID）
        date_path_pattern = re.compile(r"^/(20\d{2}-\d{1,2}-\d{1,2})/\d+")
        for a in soup.select("a[href][target='_blank']"):
            href = a.get("href", "")
            m = date_path_pattern.match(href)
            if not m:
                continue
            title = clean_text(a.get_text(" ", strip=True) or a.get("title", ""))
            if not title or len(title) < 5:
                continue
            url = canonicalize(href, self.base_url)
            if item_id_for_url(url) in seen_ids:
                continue
            seen_ids.add(item_id_for_url(url))
            # 日期直接从 URL path 取（最稳）
            pub_date, inferred = self._extract_date(m.group(1), fetched_at)
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
                needs_classification=self.needs_classification,
            ))
        return items
