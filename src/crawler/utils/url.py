from __future__ import annotations

from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


TRACKING_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"from", "spm", "source"}


def canonicalize(url: str, base_url: str | None = None) -> str:
    absolute = urljoin(base_url or "", url.strip())
    parts = urlsplit(absolute)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith(TRACKING_PREFIXES) and key not in TRACKING_PARAMS
    ]
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(query_pairs, doseq=True),
            "",
        )
    )


def item_id_for_url(url: str) -> str:
    return sha256(url.encode("utf-8")).hexdigest()


def markdown_safe_url(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29")
