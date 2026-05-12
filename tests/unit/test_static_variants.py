from __future__ import annotations

from crawler.fetchers.static_variants import (
    PkuZsbFetcher, RucZsbFetcher, BuaaZsbFetcher,
    BitZsbFetcher, CauZsbFetcher, TjuZsbFetcher,
    WhuZsbFetcher, HustZsbFetcher, CsuZsbFetcher,
    NudtZsbFetcher, UestcZsbFetcher, LzuZsbFetcher,
    SysuZsbFetcher, CquZsbFetcher, SduZsbFetcher,
    JluZsbFetcher, NwafuZsbFetcher, NankaiZsbFetcher,
    HitwhZsbFetcher, MucZsbFetcher,
)
import pytest

@pytest.mark.live
def test_live_pku_zsb_fetcher() -> None:
    result = PkuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0
    assert any("2026" in item.title for item in result.items)

@pytest.mark.live
def test_live_ruc_zsb_fetcher() -> None:
    result = RucZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_buaa_zsb_fetcher() -> None:
    result = BuaaZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_bit_zsb_fetcher() -> None:
    result = BitZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_cau_zsb_fetcher() -> None:
    result = CauZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_tju_zsb_fetcher() -> None:
    result = TjuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_whu_zsb_fetcher() -> None:
    result = WhuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_hust_zsb_fetcher() -> None:
    result = HustZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_csu_zsb_fetcher() -> None:
    result = CsuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_nudt_zsb_fetcher() -> None:
    result = NudtZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_uestc_zsb_fetcher() -> None:
    result = UestcZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_lzu_zsb_fetcher() -> None:
    result = LzuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_sysu_zsb_fetcher() -> None:
    result = SysuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_cqu_zsb_fetcher() -> None:
    result = CquZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_sdu_zsb_fetcher() -> None:
    result = SduZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_jlu_zsb_fetcher() -> None:
    result = JluZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_nwafu_zsb_fetcher() -> None:
    result = NwafuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_nankai_zsb_fetcher() -> None:
    result = NankaiZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_hitwh_zsb_fetcher() -> None:
    result = HitwhZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0

@pytest.mark.live
def test_live_muc_zsb_fetcher() -> None:
    result = MucZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0
    assert any("2026" in item.title for item in result.items)


@pytest.mark.live
def test_live_dlut_zsb_fetcher() -> None:
    from crawler.fetchers.dlut_admissions import DlutZsbFetcher
    result = DlutZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0
    assert any("大连理工" in item.title for item in result.items)


@pytest.mark.live
def test_live_nju_zsb_fetcher() -> None:
    from crawler.fetchers.nju_admissions import NjuZsbFetcher
    result = NjuZsbFetcher().fetch(max_items=5)
    assert result.success, result.error
    assert len(result.items) > 0
