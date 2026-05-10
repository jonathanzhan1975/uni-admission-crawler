from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from crawler import main as crawler_main
from crawler.config import AppConfig, ChannelConfig, SourceConfig
from crawler.pipeline.dedup import Dedup
from crawler.schema import ChannelId, FetchResult, PushResult, SourceId


class FakeFetcher:
    def __init__(self, result: FetchResult):
        self.result = result

    def fetch(self, max_items: int = 30) -> FetchResult:
        return self.result


class FakePusher:
    def __init__(self, channel: ChannelId, success: bool, enabled: bool = True):
        self.channel = channel
        self.success = success
        self.enabled = enabled

    def push(self, markdown: str, title: str) -> PushResult:
        return PushResult(self.channel, self.success, None if self.success else "failed")


def _config() -> AppConfig:
    return AppConfig(
        sources=[
            SourceConfig(SourceId.FUDAN_AO, "html", "复旦大学", "本科招办", False, base_url="https://ao.fudan.edu.cn/"),
            SourceConfig(SourceId.SJTU_JWC, "rsshub", "上海交通大学", "教务处", True, rsshub_path="/sjtu/jwc"),
            SourceConfig(SourceId.TSINGHUA_NEWS, "rsshub", "清华大学", "主新闻", True, rsshub_path="/tsinghua/news"),
        ],
        channels={ChannelId.SERVERCHAN: ChannelConfig(True), ChannelId.LARK: ChannelConfig(False)},
        rsshub_base_url="https://rsshub.app",
        timezone="Asia/Shanghai",
        max_items_per_source=30,
        raw_retention_days=30,
        lark_webhook_url=None,
        serverchan_sendkey="SCT_TEST",
        google_api_key=None,
    )


@pytest.fixture
def isolated_dedup(monkeypatch, tmp_path):
    db_path = tmp_path / "state.db"
    monkeypatch.setattr(crawler_main, "Dedup", lambda *_a, **_kw: Dedup(str(db_path)))
    return db_path


def test_e2e_cold_start_commits_after_success(monkeypatch, isolated_dedup, sample_item) -> None:
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.FUDAN_AO, [sample_item], True))])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, True)])

    report = crawler_main.run(_config())

    assert report.deduped_count == 1
    assert Dedup(str(isolated_dedup)).filter_new([sample_item]) == []


def test_e2e_incremental_run_dedups(monkeypatch, isolated_dedup, sample_item) -> None:
    Dedup(str(isolated_dedup)).commit([sample_item])
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.FUDAN_AO, [sample_item], True))])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, True)])

    report = crawler_main.run(_config())

    assert report.deduped_count == 0


def test_e2e_single_source_failure_isolated(monkeypatch, isolated_dedup, sample_item) -> None:
    failed = FetchResult(SourceId.FUDAN_AO, [], False, "blocked")
    ok = FetchResult(SourceId.SJTU_JWC, [replace(sample_item, needs_classification=True)], True)
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(failed), FakeFetcher(ok)])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, True)])

    report = crawler_main.run(_config())

    assert report.fetch_results[0].success is False
    assert report.deduped_count == 1


def test_e2e_llm_degraded_still_pushes(monkeypatch, isolated_dedup, sample_item) -> None:
    item = replace(sample_item, needs_classification=True)
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.TSINGHUA_NEWS, [item], True))])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, True)])

    report = crawler_main.run(_config())

    assert report.classify_degraded is True
    assert report.push_results[0].success is True


def test_e2e_all_channels_failed_does_not_commit(monkeypatch, isolated_dedup, sample_item) -> None:
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.FUDAN_AO, [sample_item], True))])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, False)])

    report = crawler_main.run(_config())

    assert report.push_results[0].success is False
    assert Dedup(str(isolated_dedup)).filter_new([sample_item]) == [sample_item]


def test_e2e_single_channel_failure_still_commits_if_another_succeeds(monkeypatch, isolated_dedup, sample_item) -> None:
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.FUDAN_AO, [sample_item], True))])
    monkeypatch.setattr(
        crawler_main,
        "_build_pushers",
        lambda _cfg: [FakePusher(ChannelId.LARK, False), FakePusher(ChannelId.SERVERCHAN, True)],
    )

    report = crawler_main.run(_config())

    assert [result.success for result in report.push_results].count(True) == 1
    assert Dedup(str(isolated_dedup)).filter_new([sample_item]) == []


def test_main_exits_when_all_enabled_channels_fail(monkeypatch, isolated_dedup, sample_item) -> None:
    cfg = _config()
    monkeypatch.setattr(crawler_main, "load_config", lambda: cfg)
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.FUDAN_AO, [sample_item], True))])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, False)])

    with pytest.raises(SystemExit):
        crawler_main.main()


def test_main_writes_report_file(monkeypatch, isolated_dedup, sample_item, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = _config()
    monkeypatch.setattr(crawler_main, "load_config", lambda: cfg)
    monkeypatch.setattr(crawler_main, "_build_fetchers", lambda _cfg: [FakeFetcher(FetchResult(SourceId.FUDAN_AO, [sample_item], True))])
    monkeypatch.setattr(crawler_main, "_build_pushers", lambda _cfg: [FakePusher(ChannelId.SERVERCHAN, True)])

    crawler_main.main()

    assert (tmp_path / "data" / "last_run.json").exists()
