# 高校招生动态聚合推送系统

POC 范围：复旦大学、上海交通大学、清华大学招生相关动态每日抓取、过滤并通过 Server 酱推送。

## 本地运行

```powershell
pip install -r requirements.txt
pip install -e .
$env:SERVERCHAN_SENDKEY="SCT..."
python -m crawler.main
```

源码使用 `src/` 布局，配置在 `config/config.yaml`。飞书渠道已实现但默认关闭，Server 酱默认开启。

## GitHub Actions

`.github/workflows/daily.yml` 每天北京时间 09:00 运行，并在推送成功后提交 `data/state.db` 保持去重状态。

## 2026-11-21 清理说明

保留高校招生每日汇总；移除人大（S-15）、西安交大（S-31）、南开（S-36）三个信息源，现配置 35 个信息源。
AI 信息分类已移除：不再使用 Google/Gemini、不再读取 API Key，不再有分类 API 费用。综合新闻源继续使用本地招生关键词过滤，专门的招办来源直接保留。
历史审计和需求文档保留作为开发记录，其中的 AI 方案不代表当前实现。
