from __future__ import annotations

import time
from collections.abc import Mapping

import httpx


DEFAULT_HEADERS = {
    "User-Agent": "uni-admission-crawler/0.1 (+https://github.com/; daily polite crawler)",
}


class HttpClient:
    def __init__(self, timeout: float = 10.0, retries: int = 3, backoffs: tuple[float, ...] = (10.0, 30.0, 90.0)):
        self.timeout = timeout
        self.retries = retries
        self.backoffs = backoffs

    def get(self, url: str, headers: Mapping[str, str] | None = None) -> httpx.Response:
        merged_headers = {**DEFAULT_HEADERS, **dict(headers or {})}
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = httpx.get(url, headers=merged_headers, timeout=self.timeout, follow_redirects=True)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                self._sleep(attempt)
        if last_error is None:
            raise RuntimeError("HTTP GET retry loop exited without an error")
        raise last_error

    def _sleep(self, attempt: int) -> None:
        if attempt < self.retries - 1:
            time.sleep(self.backoffs[min(attempt, len(self.backoffs) - 1)])
