from __future__ import annotations

from abc import ABC, abstractmethod

from crawler.schema import ChannelId, PushResult


class BasePusher(ABC):
    channel: ChannelId
    enabled: bool

    @abstractmethod
    def push(self, markdown: str, title: str) -> PushResult:
        """Push rendered markdown without raising exceptions."""

