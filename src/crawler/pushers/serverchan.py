from __future__ import annotations

import time
import unicodedata
from typing import Any

import httpx
import structlog

from crawler.pipeline.archive import save_failed
from crawler.pushers.base import BasePusher
from crawler.schema import ChannelId, PushResult
from crawler.utils.text import redact_secret, truncate_utf8


logger = structlog.get_logger()


class ServerchanPusher(BasePusher):
    channel = ChannelId.SERVERCHAN
    # Server Chan documents this limit as 32 characters. We count Python codepoints;
    # emoji may count differently server-side, so keep the generated default title short.
    MAX_TITLE_CHARS = 32
    MAX_DESP_BYTES = 32 * 1024
    API_URL = "https://sctapi.ftqq.com/{sendkey}.send"
    RETRY_BACKOFFS = (10, 30, 90)

    def __init__(self, sendkey: str | None, enabled: bool = True):
        self.sendkey = sendkey
        self.enabled = enabled

    def push(self, markdown: str, title: str) -> PushResult:
        if not self.enabled:
            return PushResult(self.channel, False, "channel disabled")
        if not self.sendkey:
            save_failed("serverchan", markdown)
            return PushResult(self.channel, False, "SERVERCHAN_SENDKEY is not configured")

        safe_title = self._truncate_title(title)
        safe_markdown = truncate_utf8(markdown, self.MAX_DESP_BYTES, "\n\n...完整内容见飞书")
        url = self.API_URL.format(sendkey=self.sendkey)
        retries = 0
        for attempt, backoff in enumerate(self.RETRY_BACKOFFS, start=1):
            retries = attempt - 1
            try:
                response = httpx.post(url, json={"title": safe_title, "desp": safe_markdown}, timeout=10)
                payload = self._response_json(response)
                if response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    error = self._format_response_error(response, payload)
                    error_kind = self._error_kind(response, payload)
                    logger.warning(
                        "push_failed_attempt",
                        channel=self.channel.value,
                        attempt=attempt,
                        error=error,
                        error_kind=error_kind,
                    )
                    save_failed("serverchan", markdown)
                    return PushResult(self.channel, False, error, retries=retries, error_kind=error_kind)
                if payload.get("code") == 0:
                    return PushResult(
                        self.channel,
                        True,
                        sent_bytes=len(safe_markdown.encode("utf-8")),
                        retries=retries,
                    )
                error = self._format_response_error(response, payload)
                error_kind = self._error_kind(response, payload)
                logger.warning(
                    "push_failed_attempt",
                    channel=self.channel.value,
                    attempt=attempt,
                    error=error,
                    error_kind=error_kind,
                )
                save_failed("serverchan", markdown)
                return PushResult(self.channel, False, error, retries=retries, error_kind=error_kind)
            except httpx.HTTPStatusError as exc:
                error = self._redact_error(exc)
                logger.warning("push_failed_attempt", channel=self.channel.value, attempt=attempt, error=error)
                if attempt < len(self.RETRY_BACKOFFS):
                    time.sleep(backoff)
                else:
                    save_failed("serverchan", markdown)
                    return PushResult(self.channel, False, error, retries=retries)
            except httpx.RequestError as exc:
                error = self._redact_error(exc)
                logger.warning("push_failed_attempt", channel=self.channel.value, attempt=attempt, error=error)
                if attempt < len(self.RETRY_BACKOFFS):
                    time.sleep(backoff)
                else:
                    save_failed("serverchan", markdown)
                    return PushResult(self.channel, False, error, retries=retries)
        return PushResult(self.channel, False, "unreachable", retries=retries)

    def _truncate_title(self, title: str) -> str:
        title = unicodedata.normalize("NFC", title)
        if len(title) <= self.MAX_TITLE_CHARS:
            return title
        return title[: self.MAX_TITLE_CHARS - 1] + "…"

    def _redact_error(self, exc: Exception) -> str:
        message = str(exc)
        if isinstance(exc, httpx.HTTPStatusError):
            response_text = exc.response.text.strip()
            if response_text:
                message = f"{message}; response={response_text[:500]}"
        return redact_secret(message, self.sendkey)

    def _response_json(self, response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _format_response_error(self, response: httpx.Response, payload: dict[str, Any]) -> str:
        code = payload.get("code")
        message = payload.get("message") or payload.get("error") or response.text.strip()
        error = f"serverchan status={response.status_code}"
        if code is not None:
            error = f"{error} code={code}"
        if message:
            error = f"{error} message={str(message)[:500]}"
        return redact_secret(error, self.sendkey)

    def _error_kind(self, response: httpx.Response, payload: dict[str, Any]) -> str | None:
        if response.status_code == 429:
            return "quota_exhausted"
        code = str(payload.get("code") or "")
        message = str(payload.get("message") or payload.get("error") or "")
        quota_markers = ("quota", "limit", "rate", "次数", "额度", "限额", "超过", "too many")
        if any(marker in message.lower() for marker in quota_markers):
            return "quota_exhausted"
        if code in {"429", "40029", "45009", "45011"}:
            return "quota_exhausted"
        return None
