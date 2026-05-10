from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crawler.schema import Item, SourceId
from crawler.utils.url import item_id_for_url


@pytest.fixture
def sample_item() -> Item:
    url = "https://example.edu/a/1"
    return Item(
        item_id=item_id_for_url(url),
        university="复旦大学",
        source_id=SourceId.FUDAN_AO,
        source_name="本科招办",
        title="2026 年本科招生简章发布",
        url=url,
        pub_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        summary=None,
        fetched_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

