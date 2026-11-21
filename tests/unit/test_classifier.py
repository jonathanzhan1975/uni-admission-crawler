from dataclasses import replace

from crawler.pipeline.classifier import Classifier, keyword_prefilter


def test_trusted_source_passes(sample_item):
    items, degraded = Classifier().classify([sample_item])
    assert items[0].is_admission is True
    assert degraded is False


def test_general_news_is_filtered(sample_item):
    item = replace(sample_item, title="普通校园活动", summary=None, needs_classification=True)
    items, degraded = Classifier().classify([item])
    assert items[0].is_admission is False
    assert degraded is False


def test_admission_news_passes_without_api_key(sample_item, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "unused-sentinel")
    item = replace(sample_item, needs_classification=True)
    items, degraded = Classifier().classify([item])
    assert items[0].is_admission is True
    assert items[0].classify_reason == "keyword_match"
    assert items[0].classify_degraded is False
    assert degraded is False


def test_graduate_admission_is_excluded(sample_item):
    item = replace(sample_item, title="博士研究生招生专业目录", summary="报考须知", needs_classification=True)
    items, _ = Classifier().classify([item])
    assert not keyword_prefilter(item)
    assert items[0].is_admission is False
