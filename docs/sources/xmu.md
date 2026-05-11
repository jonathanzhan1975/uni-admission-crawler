# 厦门大学（xmu）

## RSSHub
- namespace: xmu
- rsshub_status: ok
- routes available: kydt
- 选用: kydt
- 实拉 10 条样本（2026-05-11）：
  1. "经济学科吴吉林教授合作论文在Econometric Theory正式发表" → 非招生
  2. "钟齐先副教授两篇论文分别发表于JBES和JASA" → 非招生
  3. "王璐航副教授合作论文在Journal of Development Economics正式发表" → 非招生
  4. "吴吉林教授合作论文在Journal of Econometrics正式发表" → 非招生
  5. "博士生张心宇和刘婧媛教授等合作论文在JASA在线发表" → 非招生
  6. "青年教师柳楠合作论文在JoE发表" → 非招生
  7. "梁若冰教授合作论文在《经济研究》发表" → 非招生
  8. "厦大经济学科博士生张齐圣、王雅琳合作论文在《经济研究》发表" → 非招生
  9. "郑挺国教授合作论文在《经济研究》正式发表" → 非招生
  10. "青年教师王晨笛合作成果在《美国科学院院刊》（PNAS）刊发" → 非招生
- 招生覆盖度: C（0% 含招生）

## 本科招办官网（backup）
- URL: https://zs.xmu.edu.cn/
- 渲染: static
- 实测 selector 命中: ✅
- 真实抓取样本（2026-05-11，前 5 条）：
  1. "学校概况学校简介院系设置奖助贷就业国际交流"

## 实施决策
- 优先级: P0
- 实施方案: 优先自写 Fetcher
- CMS 类型: static
- 实施波次: Wave 3

## 实施警告
⚠️ **known_degraded**：厦门大学招生网由 Vue 渲染，无静态 HTML 列表。
- 决策：POC 阶段降级跳过。
