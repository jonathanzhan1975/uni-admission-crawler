from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

import structlog

from crawler.config import AppConfig, load_config
from crawler.fetchers.base import BaseFetcher
from crawler.fetchers.fudan_ao import FudanAoFetcher
from crawler.fetchers.fudan_gsao import FudanGsaoFetcher
from crawler.fetchers.rsshub import RsshubFetcher
from crawler.logging_setup import setup_logging
from crawler.pipeline import archive
from crawler.pipeline.classifier import Classifier
from crawler.pipeline.dedup import Dedup
from crawler.pipeline.render import render
from crawler.pushers.base import BasePusher
from crawler.pushers.lark import LarkPusher
from crawler.pushers.serverchan import ServerchanPusher
from crawler.schema import ChannelId, RunReport, SourceId
from crawler.utils.time import now_local


logger = structlog.get_logger()


def run(config: AppConfig) -> RunReport:
    started_at = datetime.now(timezone.utc)
    run_id = os.getenv("GITHUB_RUN_ID") or started_at.strftime("%Y%m%d%H%M%S")

    fetchers = _build_fetchers(config)
    fetch_results = [fetcher.fetch(config.max_items_per_source) for fetcher in fetchers]
    all_items = [item for result in fetch_results if result.success for item in result.items]

    classifier = Classifier(config.google_api_key, "config/prompts/classifier.txt")
    classified_items, degraded = classifier.classify(all_items)
    admission_items = [item for item in classified_items if item.is_admission]

    dedup = Dedup()
    new_items = dedup.filter_new(admission_items)
    universities = list(dict.fromkeys(source.university for source in config.sources))
    markdown = render(new_items, universities, degraded, run_id)
    title = f"📅 高校招生动态 · {now_local().strftime('%m-%d')}（共 {len(new_items)} 条）"

    pushers = _build_pushers(config)
    enabled_pushers = [pusher for pusher in pushers if pusher.enabled]
    push_results = []
    if enabled_pushers:
        with ThreadPoolExecutor(max_workers=len(enabled_pushers)) as executor:
            futures = [executor.submit(pusher.push, markdown, title) for pusher in enabled_pushers]
            for future in as_completed(futures):
                push_results.append(future.result())
    else:
        logger.warning("no_enabled_channels")

    if any(result.success for result in push_results):
        dedup.commit(new_items)

    archive.cleanup(config.raw_retention_days)
    report = RunReport(
        run_id=run_id,
        started_at=started_at,
        fetch_results=fetch_results,
        classified_count=len(classified_items),
        deduped_count=len(new_items),
        push_results=push_results,
        classify_degraded=degraded,
    )
    logger.info(
        "run_finished",
        run_id=run_id,
        fetched_count=len(all_items),
        classified_count=len(classified_items),
        deduped_count=len(new_items),
        pushed_count=sum(1 for result in push_results if result.success),
        errors=[result.error for result in push_results if result.error],
    )
    return report


def _build_fetchers(config: AppConfig) -> list[BaseFetcher]:
    fetchers: list[BaseFetcher] = []
    for source in config.sources:
        if source.id == SourceId.FUDAN_AO:
            fetchers.append(FudanAoFetcher(source.base_url))
        elif source.id == SourceId.FUDAN_GSAO:
            fetchers.append(FudanGsaoFetcher(source.base_url))
        elif source.type == "rsshub" and source.rsshub_path:
            fetchers.append(
                RsshubFetcher(
                    source.id,
                    source.source_name,
                    source.university,
                    source.rsshub_path,
                    source.needs_classification,
                    config.rsshub_base_url,
                )
            )
    return fetchers


def _build_pushers(config: AppConfig) -> list[BasePusher]:
    lark_cfg = config.channels.get(ChannelId.LARK)
    serverchan_cfg = config.channels.get(ChannelId.SERVERCHAN)
    return [
        LarkPusher(config.lark_webhook_url, enabled=bool(lark_cfg and lark_cfg.enabled)),
        ServerchanPusher(config.serverchan_sendkey, enabled=bool(serverchan_cfg and serverchan_cfg.enabled)),
    ]


def main() -> None:
    setup_logging()
    cfg = load_config()
    report = run(cfg)
    report_path = Path("data") / "last_run.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.to_json() + "\n", encoding="utf-8")
    sys.stderr.write(f"Run report written to {report_path.as_posix()}\n")
    if report.push_results and not any(result.success for result in report.push_results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
