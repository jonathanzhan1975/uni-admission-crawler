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
