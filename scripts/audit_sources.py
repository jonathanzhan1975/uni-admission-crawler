from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup
import feedparser
import httpx

from crawler.pipeline.classifier import EXCLUDED_KEYWORDS, KEYWORDS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "docs" / "06-源审计报告.md"
RAW_PATH = PROJECT_ROOT / "docs" / "06-源审计原始数据.json"
RSSHUB_BASE_URL = "https://rsshub-uni-admission.vercel.app"
USER_AGENT = "uni-admission-crawler/0.1 (audit; +https://github.com/jonathanzhan1975/uni-admission-crawler)"
TODAY = datetime.now().date().isoformat()


@dataclass(frozen=True)
class University:
    name: str
    namespace: str | None = None
    suggested_domain: str | None = None


@dataclass
class RouteSample:
    route: str
    url: str
    status: str  # ok, unavailable, failed
    rating: str
    score_ratio: float | None
    numerator: int
    denominator: int
    titles: list[str]
    error: str | None = None


@dataclass
class AuditResult:
    university: str
    namespace: str | None
    rsshub_status: str  # ok, partial_503, unavailable, no_namespace
    routes_available: list[str]
    selected_route: str | None
    selected_rating: str
    score_ratio: float | None
    priority: str
    admission_url: str | None
    cms_type: str
    notes: str
    samples: list[RouteSample]


RSSHUB_UNIVERSITIES: list[University] = [
    University("北京大学", "pku", "https://admission.pku.edu.cn/"),
    University("清华大学", "tsinghua", "https://join-tsinghua.edu.cn/"),
    University("中国人民大学", "ruc", "https://rdzs.ruc.edu.cn/"),
    University("北京航空航天大学", "buaa", "https://zs.buaa.edu.cn/"),
    University("北京理工大学", "bit", "https://admission.bit.edu.cn/"),
    University("中国农业大学", "cau", "https://jwzs.cau.edu.cn/"),
    University("北京师范大学", "bnu", "https://admission.bnu.edu.cn/"),
    University("天津大学", "tju", "https://zs.tju.edu.cn/"),
    University("大连理工大学", "dut", "https://zs.dlut.edu.cn/"),
    University("吉林大学", "jlu", "https://zsb.jlu.edu.cn/"),
    University("哈尔滨工业大学", "hit", "https://bkzs.hit.edu.cn/"),
    University("同济大学", "tongji", "https://bkzs.tongji.edu.cn/"),
    University("上海交通大学", "sjtu", "https://admissions.sjtu.edu.cn/"),
    University("华东师范大学", "ecnu", "https://zsb.ecnu.edu.cn/"),
    University("南京大学", "nju", "https://bkzs.nju.edu.cn/"),
    University("东南大学", "seu", "https://zsb.seu.edu.cn/"),
    University("浙江大学", "zju", "https://zdzsc.zju.edu.cn/"),
    University("中国科学技术大学", "ustc", "https://zsb.ustc.edu.cn/"),
    University("厦门大学", "xmu", "https://zs.xmu.edu.cn/"),
    University("武汉大学", "whu", "https://aoff.whu.edu.cn/"),
    University("华中科技大学", "hust", "https://zsb.hust.edu.cn/"),
    University("湖南大学", "hnu", "https://admi.hnu.edu.cn/"),
    University("中南大学", "csu", "https://zhaosheng.csu.edu.cn/"),
    University("国防科技大学", "nudt", "https://www.nudt.edu.cn/bkzs/"),
    University("中山大学", "sysu", "https://admission.sysu.edu.cn/"),
    University("重庆大学", "cqu", "https://zhaosheng.cqu.edu.cn/"),
    University("西安交通大学", "xjtu", "https://zs.xjtu.edu.cn/"),
    University("西北农林科技大学", "nwafu", "https://zhshw.nwafu.edu.cn/"),
]

SELF_WRITE_UNIVERSITIES: list[University] = [
    University("中央民族大学", suggested_domain="https://www.muc.edu.cn/zsjy/zs/bykzs.htm"),
    University("南开大学", suggested_domain="https://zsb.nankai.edu.cn/"),
    University("东北大学", suggested_domain="http://zs.neu.edu.cn/"),
    University("复旦大学", suggested_domain="https://ao.fudan.edu.cn/"),
    University("山东大学", suggested_domain="https://www.bkzs.sdu.edu.cn/"),
    University("中国海洋大学", suggested_domain="https://bkzs.ouc.edu.cn/"),
    University("华南理工大学", suggested_domain="https://admission.scut.edu.cn/"),
    University("四川大学", suggested_domain="https://zs.scu.edu.cn/"),
    University("电子科技大学", suggested_domain="https://zs.uestc.edu.cn/"),
    University("西北工业大学", suggested_domain="https://zsb.nwpu.edu.cn/"),
    University("兰州大学", suggested_domain="https://zsb.lzu.edu.cn/"),
]

ALL_UNIVERSITIES = RSSHUB_UNIVERSITIES + SELF_WRITE_UNIVERSITIES

ROUTE_PRIORITY_MARKERS = (
    "bkzs",
    "admission",
    "admissions",
    "zsb",
    "zs",
    "news",
    "jwc",
    "yzb",
    "gs",
)


def print_safety_statement():
    print("[audit] 安全声明：本脚本属于公开网页可用性审计")
    print("[audit] 仅访问已公开 GET/POST 端点；不做安全测试")
    print("[audit] 默认间隔 8 秒/请求；预计总耗时 30-60 分钟")
    print("[audit] 遇 4xx/5xx 一律标记后跳过，不尝试任何绕过")


class Auditor:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.last_domain = ""
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=15.0,
            follow_redirects=True,
            verify=False
        )

    def delay(self, url: str):
        if self.args.dry_run:
            return
        time.sleep(self.args.rate_seconds)
        domain = urlparse(url).netloc
        if domain == self.last_domain:
            time.sleep(5.0)
        self.last_domain = domain

    def run(self):
        print_safety_statement()
        universities = ALL_UNIVERSITIES[: self.args.max_schools] if self.args.max_schools else ALL_UNIVERSITIES
        
        if self.args.dry_run:
            print("[dry-run] 计划审计目标：")
            for uni in universities:
                print(f"- {uni.name} (ns: {uni.namespace}, domain: {uni.suggested_domain})")
            return

        results = []
        for uni in universities:
            print(f"Auditing {uni.name}...")
            results.append(self.audit_university(uni))

        REPORT_PATH.write_text(self.render_report(results), encoding="utf-8")
        RAW_PATH.write_text(
            json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"wrote {REPORT_PATH}")
        print(f"wrote {RAW_PATH}")

    def audit_university(self, uni: University) -> AuditResult:
        routes_available: list[str] = []
        samples: list[RouteSample] = []
        selected: RouteSample | None = None
        notes: list[str] = []
        rsshub_status = "no_namespace"

        if uni.namespace and not self.args.only_bkzs:
            routes_available = self.list_routes(uni.namespace)
            candidate_routes = self.prioritize_routes(routes_available)[:5]
            
            if not candidate_routes:
                rsshub_status = "unavailable"
            else:
                for route in candidate_routes:
                    sample = self.fetch_rsshub_route(uni.namespace, route)
                    samples.append(sample)
                
                # Check status
                statuses = [s.status for s in samples]
                if all(s == "unavailable" for s in statuses):
                    rsshub_status = "unavailable"
                elif "unavailable" in statuses:
                    rsshub_status = "partial_503"
                else:
                    rsshub_status = "ok"
                
                # Filter out unavailable for rating
                valid_samples = [s for s in samples if s.status == "ok"]
                selected = max(valid_samples, key=self.route_rank, default=None)
        
        selected_rating = selected.rating if selected else ("?" if rsshub_status == "unavailable" else "N/A")
        score_ratio = selected.score_ratio if selected else None
        
        # Priority calculation
        if selected is None:
            priority = "P0" if self.has_admission_hint(uni) else "BLOCKED"
        elif selected.rating == "C":
            priority = "P0"
        elif selected.rating == "B":
            priority = "P1"
        else:
            priority = "P2"

        admission_url = uni.suggested_domain
        cms_type = "not_probed"

        if not self.args.only_rsshub and priority in {"P0", "P1", "BLOCKED"}:
            valid_url, remark = self.find_and_validate_admission_url(uni)
            if valid_url:
                admission_url = valid_url
                cms_type = self.detect_cms(admission_url)
                if remark:
                    notes.append(remark)
            else:
                cms_type = "manual_needed"
                notes.append("admission_url_not_found_or_dead")

        return AuditResult(
            university=uni.name,
            namespace=uni.namespace,
            rsshub_status=rsshub_status,
            routes_available=routes_available,
            selected_route=selected.route if selected else None,
            selected_rating=selected_rating,
            score_ratio=score_ratio,
            priority=priority,
            admission_url=admission_url,
            cms_type=cms_type,
            notes="; ".join(notes),
            samples=samples,
        )

    def list_routes(self, namespace: str) -> list[str]:
        url = f"https://api.github.com/repos/DIYgod/RSSHub/contents/lib/routes/{namespace}"
        try:
            # Note: Github API usually doesn't need high delay, but let's be safe
            response = self.client.get(url, headers={"Accept": "application/vnd.github+json"})
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list): return []
            routes = []
            for entry in payload:
                name = entry.get("name", "")
                if name.endswith(".ts") and name not in {"namespace.ts", "maintainer.ts", "radar.ts"}:
                    routes.append(name.removesuffix(".ts"))
                elif entry.get("type") == "dir":
                    routes.append(name)
            return sorted(set(routes))
        except Exception:
            return []

    def prioritize_routes(self, routes: list[str]) -> list[str]:
        def score(route: str) -> tuple[int, str]:
            lowered = route.lower()
            for index, marker in enumerate(ROUTE_PRIORITY_MARKERS):
                if marker in lowered:
                    return (index, route)
            return (len(ROUTE_PRIORITY_MARKERS), route)
        return sorted(routes, key=score)

    def fetch_rsshub_route(self, namespace: str, route: str) -> RouteSample:
        url = f"{RSSHUB_BASE_URL}/{namespace}/{route}"
        self.delay(url)
        try:
            response = self.client.get(url)
            if response.status_code >= 500:
                return RouteSample(route, url, "unavailable", "?", None, 0, 0, [])
            
            feed = feedparser.parse(response.content)
            entries = list(feed.entries[:10])
            items = []
            for entry in entries:
                t = self.clean(entry.get("title", ""))
                s = self.clean(entry.get("summary", ""))
                items.append((t, s))
            
            numerator = sum(1 for t, s in items if self.is_admission_item(t, s))
            denominator = len(items)
            ratio = numerator / denominator if denominator else 0.0
            rating = self.coverage_rating(ratio)
            return RouteSample(route, url, "ok", rating, ratio, numerator, denominator, [t for t, _ in items])
        except Exception as e:
            return RouteSample(route, url, "failed", "C", 0.0, 0, 0, [], error=str(e))

    def is_admission_item(self, title: str, summary: str) -> bool:
        text = f"{title}\n{summary}"
        if any(keyword in text for keyword in EXCLUDED_KEYWORDS):
            return False
        return any(keyword in text for keyword in KEYWORDS)

    def coverage_rating(self, ratio: float) -> str:
        if ratio > 0.5: return "A"
        if ratio >= 0.1: return "B"
        return "C"

    def route_rank(self, sample: RouteSample) -> tuple[int, float]:
        rating_rank = {"A": 3, "B": 2, "C": 1, "N/A": 0, "?": -1}
        return (rating_rank.get(sample.rating, 0), sample.score_ratio or 0.0)

    def find_and_validate_admission_url(self, uni: University) -> tuple[str | None, str | None]:
        candidates = []
        
        # 1. Custom overrides for problematic ones
        overrides = {
            "中央民族大学": ["https://zsb.muc.edu.cn/", "https://www.muc.edu.cn/zsjy/zs/bykzs.htm"],
            "哈尔滨工业大学": ["https://bkzs.hit.edu.cn/", "https://join.hit.edu.cn/", "https://admission.hit.edu.cn/"],
            "东北大学": ["http://zs.neu.edu.cn/"]
        }
        
        if uni.name in overrides:
            candidates.extend(overrides[uni.name])
        
        # 2. Suggested domain
        if uni.suggested_domain and uni.suggested_domain not in candidates:
            candidates.append(uni.suggested_domain)
        
        # 3. Pattern based
        ns = uni.namespace or self.infer_ns(uni.name)
        if ns:
            patterns = [
                f"https://admission.{ns}.edu.cn/",
                f"https://bkzs.{ns}.edu.cn/",
                f"https://zsb.{ns}.edu.cn/",
                f"https://zhaosheng.{ns}.edu.cn/",
            ]
            # Special case: don't use zs.hit.edu.cn as it's internal
            if ns != "hit":
                patterns.append(f"https://zs.{ns}.edu.cn/")
            
            for p in patterns:
                if p not in candidates:
                    candidates.append(p)
        
        # Validate candidates
        for url in candidates:
            status, remark = self.validate_url(url)
            if status == "ok":
                return url, remark
            if status == "waf":
                return url, "waf_blocked"
        
        # 4. Search as last resort
        if not self.args.no_search:
            print(f"Searching for {uni.name} admission site...")
            searched = self.search_bing(f"{uni.name} 本科招生网")
            for url in searched:
                if ".edu.cn" in url and url not in candidates:
                    status, remark = self.validate_url(url)
                    if status == "ok":
                        return url, remark
                    if status == "waf":
                        return url, "waf_blocked"
        
        return None, "bkzs_url_not_found"

    def validate_url(self, url: str) -> tuple[str, str | None]:
        """Returns (status, remark) where status in ['ok', 'waf', 'failed']"""
        self.delay(url)
        try:
            # Use Browser-like UA for probe as requested
            resp = self.client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8.0)
            if resp.status_code in {412, 403}:
                return "waf", "waf_blocked"
            
            if resp.status_code in {200, 301, 302}:
                # CONTENT VALIDATION
                content = resp.text
                keywords = ["招生", "录取", "本科", "报考", "高考", "强基", "综评"]
                if any(k in content for k in keywords):
                    return "ok", None
                else:
                    return "failed", "content_mismatch_possibly_homepage"
            
            return "failed", f"http_{resp.status_code}"
        except Exception as e:
            return "failed", "unreachable"

    def search_bing(self, query: str) -> list[str]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}"
        self.delay(url)
        try:
            response = self.client.get(url)
            response.raise_for_status()
            return list(dict.fromkeys(re.findall(r"https?://[^\"'<> ]+?\.edu\.cn[^\"'<> ]*", response.text)))[:5]
        except Exception:
            return []

    def infer_ns(self, name: str) -> str | None:
        # Simple heuristic for common ns
        return None

    def detect_cms(self, url: str) -> str:
        try:
            self.delay(url)
            resp = self.client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            html = resp.text.lower()
            if "wp_article_list" in html or "/_upload/tpl/" in html or "webplus" in html:
                return "webplus"
            if "data-n-head" in html or "_nuxt/" in html or "window.__nuxt__" in html:
                return "nuxt-spa"
            if "__next_data__" in html or ("react" in html and "_next/" in html):
                return "next-spa"
            soup = BeautifulSoup(resp.text, "lxml")
            if soup.select("ul li a[href]") or soup.select("table a[href]"):
                return "static"
            return "unknown"
        except Exception:
            return "unknown"

    def has_admission_hint(self, uni: University) -> bool:
        return bool(uni.suggested_domain)

    def clean(self, value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def render_report(self, results: list[AuditResult]) -> str:
        lines = [
            "# 方案 B Phase 1 源审计报告 v2",
            "",
            f"- 重测日期：{TODAY}",
            "- 修复说明：区分了 503 不可用状态；优化了代表路由优先级；增加了招办 URL 主动探测与 WAF 识别",
            f"- RSSHub 实例：{RSSHUB_BASE_URL}",
            "- 口径：仅本科招生；研究生/推免/复试/调剂/考研/博士/硕士/MBA/MPA 不计入招生覆盖分子",
            "- 安全边界：本报告是公开网页可用性审计，仅访问公开 GET/POST 页面/API；不做漏洞探测、目录爆破、登录尝试或绕过行为",
            "- 评级：A=>50% RSS item 命中本科招生；B=10-50%；C=<10%；?=>服务不可用",
            "",
            "| # | 大学 | RSSHub ns | rsshub_status | 路由数 | 代表路由 | 评级 | 覆盖度 | 优先级 | 招办 URL | CMS | 备注 |",
            "|---|---|---|---|---:|---|---|---:|---|---|---|---|",
        ]
        for index, r in enumerate(results, start=1):
            ratio_str = f"{r.score_ratio:.0%}" if r.score_ratio is not None else "N/A"
            lines.append(
                "| {index} | {university} | {namespace} | {rsshub_status} | {route_count} | {selected_route} | {rating} | {ratio} | "
                "{priority} | {admission_url} | {cms_type} | {notes} |".format(
                    index=index,
                    university=r.university,
                    namespace=r.namespace or "",
                    rsshub_status=r.rsshub_status,
                    route_count=len(r.routes_available),
                    selected_route=r.selected_route or "",
                    rating=r.selected_rating,
                    ratio=ratio_str,
                    priority=r.priority,
                    admission_url=r.admission_url or "",
                    cms_type=r.cms_type,
                    notes=r.notes,
                )
            )
        
        # Summaries
        lines.extend(["", "## 优先级汇总", "", "| 优先级 | 数量 | 学校 |", "|---|---:|---|"])
        for p in ("P0", "P1", "P2", "BLOCKED"):
            names = [r.university for r in results if r.priority == p]
            lines.append(f"| {p} | {len(names)} | {'、'.join(names)} |")

        return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-schools", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-search", action="store_true")
    parser.add_argument("--rate-seconds", type=float, default=8.0)
    parser.add_argument("--only-rsshub", action="store_true")
    parser.add_argument("--only-bkzs", action="store_true")
    args = parser.parse_args()

    if args.rate_seconds < 5.0:
        args.rate_seconds = 5.0
        print("[audit] Warning: rate-seconds capped at 5.0s minimum.")

    auditor = Auditor(args)
    auditor.run()


if __name__ == "__main__":
    main()
