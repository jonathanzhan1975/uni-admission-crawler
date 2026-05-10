from __future__ import annotations

from crawler.pipeline.dedup import Dedup
from dataclasses import replace
from crawler.utils.url import canonicalize, item_id_for_url


def test_filter_new_then_commit(tmp_path, sample_item) -> None:
    dedup = Dedup(str(tmp_path / "state.db"))

    assert dedup.filter_new([sample_item]) == [sample_item]
    dedup.commit([sample_item])
    assert dedup.filter_new([sample_item]) == []


def test_same_url_changed_title_is_duplicate(tmp_path, sample_item) -> None:
    dedup = Dedup(str(tmp_path / "state.db"))
    changed = replace(sample_item, title="标题已变化")

    dedup.commit([sample_item])

    assert dedup.filter_new([changed]) == []


def test_trailing_slash_canonical_url_dedupes(tmp_path, sample_item) -> None:
    dedup = Dedup(str(tmp_path / "state.db"))
    first_url = canonicalize("https://example.edu/foo/")
    second_url = canonicalize("https://example.edu/foo")
    first = replace(sample_item, url=first_url, item_id=item_id_for_url(first_url))
    second = replace(sample_item, url=second_url, item_id=item_id_for_url(second_url))

    dedup.commit([first])

    assert dedup.filter_new([second]) == []


def test_duplicate_commit_is_safe(tmp_path, sample_item) -> None:
    dedup = Dedup(str(tmp_path / "state.db"))

    dedup.commit([sample_item, sample_item])

    assert dedup.filter_new([sample_item]) == []


def test_missing_db_rebuilds(tmp_path, sample_item) -> None:
    db_path = tmp_path / "state.db"
    dedup = Dedup(str(db_path))
    db_path.unlink()

    dedup = Dedup(str(db_path))
    assert dedup.filter_new([sample_item]) == [sample_item]


def test_corrupt_db_rebuilds(tmp_path, sample_item) -> None:
    db_path = tmp_path / "state.db"
    db_path.write_text("not sqlite", encoding="utf-8")

    dedup = Dedup(str(db_path))

    assert dedup.filter_new([sample_item]) == [sample_item]


def test_filter_new_returns_uncommitted_items(tmp_path, sample_item) -> None:
    dedup = Dedup(str(tmp_path / "state.db"))

    assert dedup.filter_new([sample_item]) == [sample_item]
