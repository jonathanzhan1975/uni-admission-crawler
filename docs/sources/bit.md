# 北京理工大学（bit）

## RSSHub
- namespace: bit
- rsshub_status: partial_503
- routes available: cs, jwc, rszhaopin, yjs
- 选用: rszhaopin
- 实拉 3 条样本（2026-05-11）：
  1. "聚英才 建高地 I 北京理工大学“特立青年学者”全球招聘开启" → 非招生
  2. "博士后 待遇厚 I 北京理工大学博士后招聘公告" → 非招生
  3. "聚天下英贤 建一流大学｜北京理工大学诚邀全球优秀人才加盟" → 非招生
- 招生覆盖度: C（0% 含招生）

## 本科招办官网（backup）
- URL: https://admission.bit.edu.cn/
- 渲染: static
- 实测 selector 命中: ✅
- 真实抓取样本（2026-05-11，前 5 条）：
  1. "走进北理学校概况名家纵览重点实验室人才培养重点学科校园学习校园环境北理风采北理在线北理等你宣传片下载大中衔接先修课"

## 实施决策
- 优先级: P0
- 实施方案: 优先自写 Fetcher
- CMS 类型: static
- 实施波次: Wave 3
