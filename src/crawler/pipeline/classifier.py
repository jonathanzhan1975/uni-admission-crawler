from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Optional

import structlog

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
    "马拉松",
]

MODEL_NAME = "gemini-2.5-flash"
logger = structlog.get_logger()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def keyword_prefilter(item: Item) -> bool:
    text = f"{item.title}\n{item.summary or ''}"
    if any(keyword in text for keyword in EXCLUDED_KEYWORDS):
        return False
    return any(keyword in text for keyword in KEYWORDS)


class Classifier:
    def __init__(self, api_key: Optional[str], prompt_path: str):
        self.api_key = api_key
        self.prompt_path = prompt_path
        self.prompt_template = self._load_prompt(prompt_path)

    def classify(self, items: list[Item]) -> tuple[list[Item], bool]:
        classified: list[Item] = []
        degraded = False
        for item in items:
            if not item.needs_classification:
                classified.append(replace(item, is_admission=True, classify_reason="source_trusted"))
                continue
            if not keyword_prefilter(item):
                classified.append(replace(item, is_admission=False, classify_reason="keyword_prefilter_miss"))
                continue
            if not self.api_key:
                degraded = True
                classified.append(
                    replace(
                        item,
                        is_admission=True,
                        classify_reason="keyword_only_no_api_key",
                        classify_degraded=True,
                    )
                )
                continue
            try:
                is_admission, reason = self._classify_with_llm(item)
                classified.append(replace(item, is_admission=is_admission, classify_reason=reason))
            except Exception as exc:
                degraded = True
                logger.warning("classifier_degraded", source_id=item.source_id.value, error=str(exc))
                classified.append(
                    replace(item, is_admission=True, classify_reason="keyword_only_llm_failed", classify_degraded=True)
                )
        return classified, degraded

    def _classify_with_llm(self, item: Item) -> tuple[bool, str]:
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError("google-genai is not installed") from exc

        prompt = (
            self.prompt_template.replace("{title}", item.title)
            .replace("{summary}", item.summary or "")
            .replace("{url}", item.url)
        )
        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = getattr(response, "text", "") or ""
        payload = self._extract_json(text)
        return bool(payload["is_admission"]), str(payload.get("reason", ""))

    def _extract_json(self, value: str) -> dict[str, object]:
        start = value.find("{")
        end = value.rfind("}")
        if start < 0 or end < start:
            raise ValueError("LLM response did not contain JSON")
        return json.loads(value[start : end + 1])

    def _load_prompt(self, path: str) -> str:
        prompt_path = Path(path)
        if not prompt_path.is_absolute() and not prompt_path.exists():
            prompt_path = PROJECT_ROOT / prompt_path
        with open(prompt_path, "r", encoding="utf-8") as file:
            return file.read()
