from __future__ import annotations

import time

import httpx
import structlog

from crawler.pipeline.archive import save_failed
from crawler.pipeline.render import split_by_size
from crawler.pushers.base import BasePusher
from crawler.schema import ChannelId, PushResult
from crawler.utils.text import redact_secret


logger = structlog.get_logger()


class LarkPusher(BasePusher):
    channel = ChannelId.LARK
    MAX_BYTES = 30 * 1024

    def __init__(self, webhook_url: str | None, enabled: bool = True):
        self.webhook_url = webhook_url
        self.enabled = enabled

    def push(self, markdown: str, title: str) -> PushResult:
        if not self.enabled:
            return PushResult(self.channel, False, "channel disabled")
        if not self.webhook_url:
            save_failed("lark", markdown)
            return PushResult(self.channel, False, "LARK_WEBHOOK_URL is not configured")

        chunks = split_by_size(markdown, self.MAX_BYTES)
        sent_bytes = 0
        max_retries = 0
        for index, chunk in enumerate(chunks, start=1):
            chunk_title = title if len(chunks) == 1 else f"{title} ({index}/{len(chunks)})"
            result = self._push_one(chunk, chunk_title)
            max_retries = max(max_retries, result.retries)
            if not result.success:
                save_failed("lark", markdown)
                return PushResult(self.channel, False, result.error, sent_bytes=sent_bytes, retries=max_retries)
            sent_bytes += result.sent_bytes
        return PushResult(self.channel, True, sent_bytes=sent_bytes, retries=max_retries)

    def _push_one(self, markdown: str, title: str) -> PushResult:
        payload = {"msg_type": "text", "content": {"text": f"{title}\n\n{markdown}"}}
        retries = 0
        for attempt, backoff in enumerate((10, 30, 90), start=1):
            retries = attempt - 1
            try:
                response = httpx.post(self.webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                return PushResult(
                    self.channel,
                    True,
                    sent_bytes=len(markdown.encode("utf-8")),
                    retries=retries,
                )
            except httpx.HTTPError as exc:
                error = self._redact_error(exc)
                logger.warning("push_failed_attempt", channel=self.channel.value, attempt=attempt, error=error)
                if attempt < 3:
                    time.sleep(backoff)
                else:
                    return PushResult(self.channel, False, error, retries=retries)
        return PushResult(self.channel, False, "unreachable", retries=retries)

    def _redact_error(self, exc: Exception) -> str:
        return redact_secret(str(exc), self.webhook_url)
