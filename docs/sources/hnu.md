# 湖南大学（hnu）

## RSSHub
- namespace: hnu
- rsshub_status: ok
- routes available: careers
- 选用: careers
- 实拉 10 条样本（2026-05-11）：
  1. "麒盛科技股份有限公司" → 非招生
  2. "中建铁路投资建设集团有限公司" → 非招生
  3. "海军工程大学" → 非招生
  4. "中海油田服务股份有限公司" → 非招生
  5. "江苏润阳新能源科技股份有限公司" → 非招生
  6. "贵州路桥集团有限公司" → 非招生
  7. "就业办2019" → 非招生
  8. "卧龙控股集团有限公司" → 非招生
  9. "就业办2019" → 非招生
  10. "湖南启宇原生物科技有限公司" → 非招生
- 招生覆盖度: C（0% 含招生）

## 本科招办官网（backup）
- URL: https://admi.hnu.edu.cn/
- 渲染: static
- 实测 selector 命中: No items found with common selectors
- 真实抓取样本（2026-05-11，前 5 条）：
  (未能自动获取样本)

## 实施决策
- 优先级: P0
- 实施方案: 优先自写 Fetcher
- CMS 类型: static
- 实施波次: Wave 3

## 实施警告
⚠️ **known_degraded**：湖南大学招生网采用 VSB 渲染，但列表项在 HTML 源码中缺失。
- 决策：POC 阶段降级跳过。
