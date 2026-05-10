from __future__ import annotations

from abc import ABC, abstractmethod

from crawler.schema import FetchResult, SourceId


class BaseFetcher(ABC):
    source_id: SourceId
    source_name: str
    university: str
    needs_classification: bool

    @abstractmethod
    def fetch(self, max_items: int = 30) -> FetchResult:
        """Fetch and normalize one source without raising exceptions."""

