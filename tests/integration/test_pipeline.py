from __future__ import annotations

from crawler.pipeline.classifier import Classifier
from crawler.pipeline.dedup import Dedup
from crawler.pipeline.render import render


def test_classify_dedup_render_pipeline(tmp_path, sample_item) -> None:
    classifier = Classifier(api_key=None, prompt_path="config/prompts/classifier.txt")
    classified, degraded = classifier.classify([sample_item])
    new_items = Dedup(str(tmp_path / "state.db")).filter_new([item for item in classified if item.is_admission])

    markdown = render(new_items, ["复旦大学"], degraded, "test")

    assert "本科招生简章" in markdown

