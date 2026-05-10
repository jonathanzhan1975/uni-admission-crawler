from __future__ import annotations

import httpx
import logging

from crawler.pushers.lark import LarkPusher
import crawler.pushers.serverchan as serverchan_module
from crawler.pushers.serverchan import ServerchanPusher


def test_serverchan_title_truncates() -> None:
    pusher = ServerchanPusher("SCT_TEST")
    title = "高" * 40

    assert pusher._truncate_title(title) == ("高" * 31) + "…"


def test_serverchan_title_normalizes_nfc_before_truncating() -> None:
    pusher = ServerchanPusher("SCT_TEST")
    title = "Cafe\u0301 François " + ("📅" * 40)

    truncated = pusher._truncate_title(title)

    assert "Café" in truncated
    assert len(truncated) == 32


def test_serverchan_code_nonzero_fails_and_writes_failed(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("time.sleep", lambda _: None)
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return httpx.Response(200, json={"code": 1}, request=httpx.Request("POST", "https://example.com"))

    monkeypatch.setattr(httpx, "post", fake_post)
    pusher = ServerchanPusher("SCT_TEST")

    result = pusher.push("body", "title")

    assert not result.success
    assert result.retries == 0
    assert len(calls) == 1
    assert list((tmp_path / "data" / "failed").glob("*_serverchan.md"))


def test_serverchan_4xx_does_not_retry(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(
            400,
            json={"code": 40001, "message": "bad request"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ServerchanPusher("SCT_TEST").push("body", "title")

    assert not result.success
    assert result.retries == 0
    assert len(calls) == 1
    assert "code=40001" in (result.error or "")


def test_serverchan_429_marks_quota_exhausted_without_retry(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls = []
    logs = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(
            429,
            json={"code": 429, "message": "daily quota limit exceeded"},
            request=httpx.Request("POST", url),
        )

    class FakeLogger:
        def warning(self, event, **kwargs):
            logs.append((event, kwargs))

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(serverchan_module, "logger", FakeLogger())

    result = ServerchanPusher("SCT_TEST").push("body", "title")

    assert not result.success
    assert result.error_kind == "quota_exhausted"
    assert result.retries == 0
    assert len(calls) == 1
    assert logs[-1][1]["error_kind"] == "quota_exhausted"


def test_serverchan_5xx_still_retries(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("time.sleep", lambda _: None)
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return httpx.Response(503, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ServerchanPusher("SCT_TEST").push("body", "title")

    assert not result.success
    assert result.retries == 2
    assert len(calls) == 3


def test_serverchan_posts_json_utf8(monkeypatch) -> None:
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(kwargs)
        return httpx.Response(200, json={"code": 0}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ServerchanPusher("SCT_TEST").push("正文 François 📅", "📅 高校招生动态")

    assert result.success
    assert captured["json"]["title"] == "📅 高校招生动态"
    assert "François 📅" in captured["json"]["desp"]
    assert "data" not in captured


def test_serverchan_http_error_redacts_sendkey(tmp_path, monkeypatch, caplog) -> None:
    sendkey = "SCT_SECRET_VALUE"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("time.sleep", lambda _: None)
    caplog.set_level(logging.WARNING)

    def fake_post(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = ServerchanPusher(sendkey).push("body", "title")

    assert not result.success
    assert sendkey not in (result.error or "")
    assert sendkey not in caplog.text


def test_disabled_pusher_is_not_success() -> None:
    result = ServerchanPusher("SCT_TEST", enabled=False).push("body", "title")

    assert not result.success
    assert result.error == "channel disabled"


def test_lark_5xx_retries_and_writes_failed(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("time.sleep", lambda _: None)

    def fake_post(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = LarkPusher("https://open.feishu.cn/webhook/secret").push("body", "title")

    assert not result.success
    assert list((tmp_path / "data" / "failed").glob("*_lark.md"))


def test_lark_splits_long_markdown(monkeypatch) -> None:
    calls = []

    def fake_post(url, **kwargs):
        calls.append(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = LarkPusher("https://open.feishu.cn/webhook/secret").push("# t\n\n## A\n" + ("x\n" * 40000), "title")

    assert result.success
    assert len(calls) >= 2


def test_lark_http_error_redacts_webhook(tmp_path, monkeypatch, caplog) -> None:
    webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/SECRET_TOKEN"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("time.sleep", lambda _: None)
    caplog.set_level(logging.WARNING)

    def fake_post(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    result = LarkPusher(webhook).push("body", "title")

    assert not result.success
    assert webhook not in (result.error or "")
    assert webhook not in caplog.text


def test_serverchan_disabled_does_not_call_http(monkeypatch) -> None:
    def fail_post(*args, **kwargs):
        raise AssertionError("disabled channel should not call HTTP")

    monkeypatch.setattr(httpx, "post", fail_post)

    result = ServerchanPusher("SCT_TEST", enabled=False).push("body", "title")

    assert not result.success
