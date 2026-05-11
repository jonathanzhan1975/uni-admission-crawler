from __future__ import annotations

from typing import ClassVar
from crawler.fetchers.webplus import WebplusFetcher
from crawler.schema import SourceId


class EcnuZsbFetcher(WebplusFetcher):
    DEFAULT_SOURCE_ID = SourceId.ECNU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "华东师范大学"
    BASE_URL = "https://zsb.ecnu.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = (
        "/37574/list.htm",  # 公示公告
        "/37582/list.htm",  # 招生政策
    )


class ZjuZsbFetcher(WebplusFetcher):
    DEFAULT_SOURCE_ID = SourceId.ZJU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "浙江大学"
    BASE_URL = "http://zdzsc.zju.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = (
        "/zxgg/list.htm",  # 招生资讯
        "/qjjh2/list.htm", # 强基计划
    )
    ITEM_SELECTOR = ".rightList li"


class UstcZsbFetcher(WebplusFetcher):
    DEFAULT_SOURCE_ID = SourceId.USTC_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中国科学技术大学"
    BASE_URL = "https://zsb.ustc.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = (
        "/tzgg/list.htm",  # 通知公告
        "/xwdt/list.htm",  # 新闻动态
    )
    ITEM_SELECTOR = ".wxlb_list2 li"


class OucZsbFetcher(WebplusFetcher):
    DEFAULT_SOURCE_ID = SourceId.OUC_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "中国海洋大学"
    BASE_URL = "https://bkzs.ouc.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = (
        "/17835/list.htm", # 招生快讯
        "/17836/list.htm", # 招生政策
    )
    ITEM_SELECTOR = ".news_list li"


class ScutZsbFetcher(WebplusFetcher):
    DEFAULT_SOURCE_ID = SourceId.SCUT_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "华南理工大学"
    BASE_URL = "https://admission.scut.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = (
        "/30818/list.htm", # 招生快讯
        "/30819/list.htm", # 招生政策
    )


class NeuZsbFetcher(WebplusFetcher):
    DEFAULT_SOURCE_ID = SourceId.NEU_ZSB
    DEFAULT_SOURCE_NAME = "本科招办"
    DEFAULT_UNIVERSITY = "东北大学"
    BASE_URL = "http://zs.neu.edu.cn/"
    LIST_PATHS: ClassVar[tuple[str, ...]] = (
        "/11185/list.htm", # 招生快讯
        "/11186/list.htm", # 招生政策
    )
