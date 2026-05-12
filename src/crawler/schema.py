from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import json
from typing import Optional


class SourceId(str, Enum):
    FUDAN_AO = "S-01"
    FUDAN_GSAO = "S-02"
    SJTU_JWC = "S-03"
    SJTU_YZB = "S-04"
    TSINGHUA_NEWS = "S-05"
    TSINGHUA_ZSB = "S-06"
    SJTU_ADMISSIONS = "S-07"
    ECNU_ZSB = "S-08"
    ZJU_ZSB = "S-09"
    USTC_ZSB = "S-10"
    OUC_ZSB = "S-11"
    SCUT_ZSB = "S-12"
    NEU_ZSB = "S-13"
    PKU_ZSB = "S-14"
    RUC_ZSB = "S-15"
    BUAA_ZSB = "S-16"
    BIT_ZSB = "S-17"
    CAU_ZSB = "S-18"
    TJU_ZSB = "S-19"
    WHU_ZSB = "S-20"
    HUST_ZSB = "S-21"
    CSU_ZSB = "S-22"
    NUDT_ZSB = "S-23"
    UESTC_ZSB = "S-24"
    LZU_ZSB = "S-25"
    SYSU_ZSB = "S-26"
    CQU_ZSB = "S-27"
    SDU_ZSB = "S-28"
    BNU_ZSB = "S-29"
    HNU_ZSB = "S-30"
    XJTU_ZSB = "S-31"
    XMU_ZSB = "S-32"
    JLU_ZSB = "S-33"
    SEU_ZSB = "S-34"
    NWAFU_ZSB = "S-35"
    NANKAI_ZSB = "S-36"
    HITSZ_ZSB = "S-37"
    HITWH_ZSB = "S-38"
    MUC_ZSB = "S-39"
    DLUT_ZSB = "S-40"


class ChannelId(str, Enum):
    LARK = "CH-1"
    SERVERCHAN = "CH-2"


@dataclass(frozen=True)
class Item:
    item_id: str
    university: str
    source_id: SourceId
    source_name: str
    title: str
    url: str
    pub_date: datetime
    summary: Optional[str]
    fetched_at: datetime
    date_inferred: bool = False
    needs_classification: bool = False
    is_admission: Optional[bool] = None
    classify_reason: Optional[str] = None
    classify_degraded: bool = False


@dataclass
class FetchResult:
    source_id: SourceId
    items: list[Item]
    success: bool
    error: Optional[str] = None


@dataclass
class PushResult:
    channel: ChannelId
    success: bool
    error: Optional[str] = None
    sent_bytes: int = 0
    retries: int = 0
    error_kind: Optional[str] = None


@dataclass
class RunReport:
    run_id: str
    started_at: datetime
    fetch_results: list[FetchResult]
    classified_count: int
    deduped_count: int
    push_results: list[PushResult]
    classify_degraded: bool

    def to_json(self) -> str:
        def default(value: object) -> object:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Enum):
                return value.value
            raise TypeError(f"Unsupported JSON type: {type(value)!r}")

        return json.dumps(asdict(self), ensure_ascii=False, default=default)
