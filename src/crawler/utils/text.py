from __future__ import annotations

import re


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def escape_markdown(value: str) -> str:
    escaped = value.replace("\\", "\\\\")
    for char in ("[", "]", "*", "_", "`"):
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def truncate_utf8(value: str, max_bytes: int, suffix: str = "") -> str:
    raw = value.encode("utf-8")
    if len(raw) <= max_bytes:
        return value
    suffix_bytes = suffix.encode("utf-8")
    budget = max(0, max_bytes - len(suffix_bytes))
    cut = raw[:budget]
    while cut:
        try:
            return cut.decode("utf-8") + suffix
        except UnicodeDecodeError:
            cut = cut[:-1]
    return suffix


def redact_secret(value: str, *secrets: str | None) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted
