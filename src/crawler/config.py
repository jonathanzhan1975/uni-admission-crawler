from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Literal, Optional

import yaml

from crawler.schema import ChannelId, SourceId


@dataclass
class ChannelConfig:
    enabled: bool


@dataclass
class SourceConfig:
    id: SourceId
    type: Literal["html", "rsshub"]
    university: str
    source_name: str
    needs_classification: bool
    base_url: Optional[str] = None
    rsshub_path: Optional[str] = None


@dataclass
class AppConfig:
    sources: list[SourceConfig]
    channels: dict[ChannelId, ChannelConfig]
    rsshub_base_url: str
    timezone: str
    max_items_per_source: int
    raw_retention_days: int
    lark_webhook_url: Optional[str]
    serverchan_sendkey: Optional[str]
    google_api_key: Optional[str]


def load_config(yaml_path: str = "config/config.yaml") -> AppConfig:
    with open(yaml_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    sources = [
        SourceConfig(
            id=SourceId(source["id"]),
            type=source["type"],
            university=source["university"],
            source_name=source["source_name"],
            needs_classification=bool(source["needs_classification"]),
            base_url=source.get("base_url"),
            rsshub_path=source.get("rsshub_path"),
        )
        for source in data.get("sources", [])
    ]
    channels = {
        ChannelId(channel_id): ChannelConfig(enabled=bool(value.get("enabled", False)))
        for channel_id, value in data.get("channels", {}).items()
    }
    return AppConfig(
        sources=sources,
        channels=channels,
        rsshub_base_url=data.get("rsshub_base_url", "https://rsshub.app"),
        timezone=data.get("timezone", "Asia/Shanghai"),
        max_items_per_source=int(data.get("max_items_per_source", 30)),
        raw_retention_days=int(data.get("raw_retention_days", 30)),
        lark_webhook_url=os.getenv("LARK_WEBHOOK_URL"),
        serverchan_sendkey=os.getenv("SERVERCHAN_SENDKEY"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )

