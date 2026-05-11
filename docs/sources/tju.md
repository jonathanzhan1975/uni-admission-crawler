# 天津大学（tju）

## RSSHub
- namespace: tju
- rsshub_status: partial_503
- routes available: cic, news, oaa, yzb
- 选用: news
- 实拉 1 条样本（2026-05-11）：
  1. "提示信息" → 非招生
- 招生覆盖度: C（0% 含招生）

## 本科招办官网（backup）
- URL: https://zs.tju.edu.cn/
- 渲染: static
- 实测 selector 命中: ✅
- 真实抓取样本（2026-05-11，前 5 条）：
  1. "走进天大学校概况国之栋梁天之骄子校园风景媒体视角云游天大校史博物馆"

## 实施决策
- 优先级: P0
- 实施方案: 优先自写 Fetcher
- CMS 类型: static
- 实施波次: Wave 3
