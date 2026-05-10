from __future__ import annotations

import json
from pathlib import Path

from crawler.pipeline.classifier import keyword_prefilter
from crawler.schema import Item, SourceId
from crawler.utils.url import item_id_for_url
from datetime import datetime, timezone


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _gold_items() -> list[tuple[Item, bool]]:
    rows: list[tuple[Item, bool]] = []
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
        rows.append((item, bool(payload["is_admission"])))
    return rows


def test_gold_set_has_50_items() -> None:
    assert len(_gold_items()) == 50


def test_keyword_gold_recall_and_precision() -> None:
    rows = _gold_items()
    true_positive = sum(1 for item, label in rows if keyword_prefilter(item) and label)
    false_positive = sum(1 for item, label in rows if keyword_prefilter(item) and not label)
    false_negative = sum(1 for item, label in rows if not keyword_prefilter(item) and label)

    recall = true_positive / (true_positive + false_negative)
    precision = true_positive / (true_positive + false_positive)

    assert recall >= 0.90
    assert precision >= 0.85
