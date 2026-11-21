from __future__ import annotations

from dataclasses import replace

from crawler.schema import Item


KEYWORDS: list[str] = [
    "招生",
    "录取",
    "报考",
    "本科专业",
    "新增专业",
    "招生简章",
    "强基",
    "综评",
    "选拔",
    "转专业",
    "高考",
    "报名",
]

EXCLUDED_KEYWORDS: list[str] = [
    "研究生",
    "推免",
    "复试",
    "调剂",
    "考研",
    "博士",
    "硕士",
    "MBA",
    "MPA",
]

def keyword_prefilter(item: Item) -> bool:
    text = f"{item.title}\n{item.summary or ''}"
    if any(keyword in text for keyword in EXCLUDED_KEYWORDS):
        return False
    return any(keyword in text for keyword in KEYWORDS)


class Classifier:
    """Local admission keyword filter; does not call external AI services."""

    def classify(self, items: list[Item]) -> tuple[list[Item], bool]:
        classified = []
        for item in items:
            admitted = not item.needs_classification or keyword_prefilter(item)
            reason = "source_trusted" if not item.needs_classification else (
                "keyword_match" if admitted else "keyword_prefilter_miss"
            )
            classified.append(replace(item, is_admission=admitted, classify_reason=reason, classify_degraded=False))
        return classified, False
