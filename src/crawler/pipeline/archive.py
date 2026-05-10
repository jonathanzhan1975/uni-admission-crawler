from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from crawler.schema import SourceId


DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
FAILED_DIR = DATA_DIR / "failed"


def save_raw(source_id: SourceId, content: bytes | str) -> str:
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    target_dir = RAW_DIR / today
    target_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(raw).hexdigest()[:8]
    path = target_dir / f"{source_id.value}_{digest}.html"
    path.write_bytes(raw)
    return path.as_posix()


def save_failed(channel: str, markdown: str) -> str:
    FAILED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    path = FAILED_DIR / f"{today}_{channel}.md"
    path.write_text(markdown, encoding="utf-8")
    return path.as_posix()


def cleanup(retention_days: int = 30) -> int:
    if not RAW_DIR.exists():
        return 0
    cutoff = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=retention_days)
    deleted = 0
    for folder in RAW_DIR.iterdir():
        if not folder.is_dir():
            continue
        try:
            folder_date = datetime.strptime(folder.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date >= cutoff:
            continue
        for file in folder.glob("*"):
            if file.is_file():
                file.unlink()
                deleted += 1
        try:
            folder.rmdir()
        except OSError:
            pass
    return deleted

