from __future__ import annotations

from crawler.fetchers.fudan_ao import FudanAoFetcher
from crawler.schema import SourceId


class FudanGsaoFetcher(FudanAoFetcher):
    DEFAULT_SOURCE_ID = SourceId.FUDAN_GSAO
    DEFAULT_SOURCE_NAME = "研招办"
    DEFAULT_UNIVERSITY = "复旦大学"
    DEFAULT_NEEDS_CLASSIFICATION = False
    BASE_URL = "https://gsao.fudan.edu.cn/"
    LIST_PATHS = ("/15014/list.htm", "/15015/list.htm")
