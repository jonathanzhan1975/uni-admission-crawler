from __future__ import annotations

from crawler.fetchers.webplus_variants import (
    EcnuZsbFetcher, ZjuZsbFetcher, UstcZsbFetcher,
    OucZsbFetcher, ScutZsbFetcher, NeuZsbFetcher
)
import pytest

@pytest.mark.live
def test_live_ecnu_zsb_fetcher() -> None:
    result = EcnuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_zju_zsb_fetcher() -> None:
    result = ZjuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_ustc_zsb_fetcher() -> None:
    result = UstcZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_ouc_zsb_fetcher() -> None:
    result = OucZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_scut_zsb_fetcher() -> None:
    result = ScutZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_neu_zsb_fetcher() -> None:
    result = NeuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0
