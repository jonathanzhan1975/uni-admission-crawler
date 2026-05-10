from __future__ import annotations

import json
from pathlib import Path

from crawler.pipeline.classifier import Classifier, keyword_prefilter
from crawler.schema import Item, SourceId
from crawler.utils.url import item_id_for_url
from datetime import datetime, timezone


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _gold_items() -> list[tuple[Item, bool, bool]]:
    rows: list[tuple[Item, bool, bool]] = []
    for index, line in enumerate((FIXTURES / "classification_gold.jsonl").read_text(encoding="utf-8").splitlines()):
        payload = json.loads(line)
        url = f"https://example.edu/gold/{index}"
        item = Item(
            item_id=item_id_for_url(url),
            university="清华大学",
            source_id=SourceId.TSINGHUA_NEWS,
            source_name="主新闻",
            title=payload["title"],
            url=url,
            pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            summary=payload["summary"],
            fetched_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            needs_classification=True,
        )
        label = bool(payload["is_admission"])
        rows.append((item, label, bool(payload.get("expected_llm_decision", label))))
    return rows


def test_gold_set_has_70_items() -> None:
    assert len(_gold_items()) == 70


def test_keyword_gold_recall_and_precision() -> None:
    rows = _gold_items()
    true_positive = sum(1 for item, label, _llm in rows if keyword_prefilter(item) and label)
    false_positive = sum(1 for item, label, _llm in rows if keyword_prefilter(item) and not label)
    false_negative = sum(1 for item, label, _llm in rows if not keyword_prefilter(item) and label)

    recall = true_positive / (true_positive + false_negative)
    precision = true_positive / (true_positive + false_positive)

    assert recall >= 0.90
    assert precision >= 0.85


def test_classifier_full_pipeline_gold(monkeypatch) -> None:
    rows = _gold_items()
    decisions = {item.item_id: llm_decision for item, _label, llm_decision in rows}
    classifier = Classifier(api_key="fake", prompt_path="config/prompts/classifier.txt")
    monkeypatch.setattr(classifier, "_classify_with_llm", lambda item: (decisions[item.item_id], "gold"))

    classified, degraded = classifier.classify([item for item, _label, _llm in rows])
    predicted = {item.item_id: bool(item.is_admission) for item in classified}
    labels = {item.item_id: label for item, label, _llm in rows}
    true_positive = sum(1 for item_id, label in labels.items() if predicted[item_id] and label)
    false_positive = sum(1 for item_id, label in labels.items() if predicted[item_id] and not label)
    false_negative = sum(1 for item_id, label in labels.items() if not predicted[item_id] and label)
    recall = true_positive / (true_positive + false_negative)
    precision = true_positive / (true_positive + false_positive)

    assert degraded is False
    assert recall >= 0.90
    assert precision >= 0.85
    assert recall < 1.0
    assert precision < 1.0
