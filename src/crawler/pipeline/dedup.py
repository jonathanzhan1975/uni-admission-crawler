from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3

import structlog

from crawler.schema import Item


logger = structlog.get_logger()


class Dedup:
    def __init__(self, db_path: str = "data/state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._ensure_table()
        except sqlite3.DatabaseError:
            logger.warning("dedup_db_corrupt_recreating", db_path=str(self.db_path))
            self.db_path.unlink(missing_ok=True)
            self._ensure_table()

    def filter_new(self, items: list[Item]) -> list[Item]:
        with closing(self._connect()) as conn:
            with conn:
                rows = conn.execute("SELECT item_id FROM seen").fetchall()
        seen = {row[0] for row in rows}
        return [item for item in items if item.item_id not in seen]

    def commit(self, items: list[Item]) -> None:
        if not items:
            return
        now = datetime.now(timezone.utc).isoformat()
        rows = [(item.item_id, item.university, now) for item in items]
        with closing(self._connect()) as conn:
            with conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO seen (item_id, university, first_seen_at) VALUES (?, ?, ?)",
                    rows,
                )

    def rebuild(self) -> None:
        self.db_path.unlink(missing_ok=True)
        self._ensure_table()

    def _ensure_table(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS seen (
                      item_id TEXT PRIMARY KEY,
                      university TEXT NOT NULL,
                      first_seen_at TEXT NOT NULL
                    )
                    """
                )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)
