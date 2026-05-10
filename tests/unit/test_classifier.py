from __future__ import annotations

from dataclasses import replace
import os

import pytest

from crawler.pipeline.classifier import Classifier, keyword_prefilter


def test_keyword_prefilter_hits_title(sample_item) -> None:
    assert keyword_prefilter(sample_item)


def test_keyword_known_miss_is_filtered(sample_item) -> None:
    item = replace(sample_item, title="清华大学迎接 2026 级新生入校", summary=None)

    assert not keyword_prefilter(item)


def test_classifier_trusted_source_passes_without_llm(sample_item) -> None:
    classifier = Classifier(api_key=None, prompt_path="config/prompts/classifier.txt")

    items, degraded = classifier.classify([sample_item])

    assert not degraded
    assert items[0].is_admission is True


def test_classifier_degrades_to_keyword_for_classified_source(sample_item) -> None:
    item = replace(sample_item, university="清华大学", source_name="主新闻", needs_classification=True)
    classifier = Classifier(api_key=None, prompt_path="config/prompts/classifier.txt")

    items, degraded = classifier.classify([item])

    assert degraded
    assert items[0].is_admission is True
    assert items[0].classify_degraded


def test_classifier_uses_item_needs_classification_not_source_id(sample_item) -> None:
    item = replace(sample_item, title="普通校园新闻", needs_classification=True)
    classifier = Classifier(api_key=None, prompt_path="config/prompts/classifier.txt")

    items, degraded = classifier.classify([item])

    assert not degraded
    assert items[0].is_admission is False


def test_classifier_llm_false_overrides_keyword(sample_item, monkeypatch) -> None:
    item = replace(sample_item, title="招生工作座谈会召开", needs_classification=True)
    classifier = Classifier(api_key="fake", prompt_path="config/prompts/classifier.txt")
    monkeypatch.setattr(classifier, "_classify_with_llm", lambda _: (False, "普通会议"))

    items, degraded = classifier.classify([item])

    assert not degraded
    assert items[0].is_admission is False


def test_classifier_any_llm_exception_degrades(sample_item, monkeypatch) -> None:
    item = replace(sample_item, needs_classification=True)
    classifier = Classifier(api_key="fake", prompt_path="config/prompts/classifier.txt")

    def fail(_item):
        raise ConnectionError("network down")

    monkeypatch.setattr(classifier, "_classify_with_llm", fail)

    items, degraded = classifier.classify([item])

    assert degraded
    assert items[0].is_admission is True
    assert items[0].classify_degraded


def test_prompt_substitution_allows_braces_in_title(sample_item, monkeypatch) -> None:
    item = replace(sample_item, title="招生简章 {测试}", needs_classification=True)
    classifier = Classifier(api_key="fake", prompt_path="config/prompts/classifier.txt")

    def fake_llm(_item):
        return True, "招生"

    monkeypatch.setattr(classifier, "_classify_with_llm", fake_llm)

    items, _ = classifier.classify([item])

    assert items[0].is_admission is True


def test_prefilter_filters_most_non_admission_items(sample_item) -> None:
    items = [replace(sample_item, title=f"校园新闻 {index}", summary="普通活动") for index in range(100)]

    passed = sum(1 for item in items if keyword_prefilter(item))

    assert passed <= 20


@pytest.mark.live
def test_live_llm_cost_smoke_is_optional(sample_item) -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY is not configured")
    classifier = Classifier(api_key=api_key, prompt_path="config/prompts/classifier.txt")

    items, _ = classifier.classify([replace(sample_item, needs_classification=True)])

    assert items[0].is_admission is not None
