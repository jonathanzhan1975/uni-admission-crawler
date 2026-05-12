from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx


DEFAULT_HEADERS = {
    "User-Agent": "uni-admission-crawler/0.1 (+https://github.com/; daily polite crawler)",
}


class HttpClient:
    def __init__(self, timeout: float = 10.0, retries: int = 3, backoffs: tuple[float, ...] = (10.0, 30.0, 90.0), verify: bool = True):
        self.timeout = timeout
        self.retries = retries
        self.backoffs = backoffs
        self.verify = verify

    def get(self, url: str, headers: Mapping[str, str] | None = None) -> httpx.Response:
        merged_headers = {**DEFAULT_HEADERS, **dict(headers or {})}
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = httpx.get(url, headers=merged_headers, timeout=self.timeout, follow_redirects=True, verify=self.verify)
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                self._sleep(attempt)
        if last_error is None:
            raise RuntimeError("HTTP GET retry loop exited without an error")
        raise last_error

    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        merged_headers = {**DEFAULT_HEADERS, **dict(headers or {})}
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = httpx.post(
                    url,
                    json=dict(payload),
                    headers=merged_headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                    verify=self.verify,
                )
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                self._sleep(attempt)
        if last_error is None:
            raise RuntimeError("HTTP POST retry loop exited without an error")
        raise last_error

    def post_form(
        self,
        url: str,
        data: Mapping[str, str],
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        """POST application/x-www-form-urlencoded (some APIs require form, not JSON)."""
        merged_headers = {**DEFAULT_HEADERS, **dict(headers or {})}
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = httpx.post(
                    url,
                    data=dict(data),
                    headers=merged_headers,
                    timeout=self.timeout,
                    follow_redirects=True,
                    verify=self.verify,
                )
                response.raise_for_status()
                return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                self._sleep(attempt)
        if last_error is None:
            raise RuntimeError("HTTP POST retry loop exited without an error")
        raise last_error

    def _sleep(self, attempt: int) -> None:
        if attempt < self.retries - 1:
            time.sleep(self.backoffs[min(attempt, len(self.backoffs) - 1)])
