# 方案 B — 28 所 RSSHub 已覆盖大学的聚合方案

> 前置条件：方案 A POC 通过验收。
> 复用方案 A 的 dedup / render / push 模块，仅扩展 fetcher。

---

## 1. 关键决策点

每所 RSSHub 高校通常有 3-8 条路由（新闻/教务/研院/各院系）。**全订会噪音爆炸**，必须先做"路由筛选"。

> ⚠️ RSSHub 大多覆盖"主新闻网/教务/研招办"，本科招生办专用路由几乎没有。如只要本科招生口径，需自写补充。

## 2. 推荐架构

```
config/sources.yaml          # 单一事实源，每条手工 review
  └── 28 所 × 1-3 条路由
      │
      ▼
RSSHub 实例（自部署 vs 公共）—— 二选一
      │
      ▼
统一 fetcher（一份 RSS 解析逻辑通吃 28 所）
      │
      ▼
关键词预筛（必需）+ LLM 分类（覆盖关键词漏召）
      │
      ▼
[与方案 A 共用 dedup / render / push]
```

## 3. sources.yaml 选路原则

每所大学只订 1-3 条最相关路由，按优先级：

1. **首选**：`/<uni>/zsb` `/admission` `/yzb`（如有）
2. **次选**：`/<uni>/news`（主新闻，必须配分类）
3. **避开**：院系新闻（28 × 多院系 = 数百条/天，噪音淹没信号）

样例配置：

```yaml
universities:
  - name: 北京大学
    routes:
      - path: /pku/news
        needs_classification: true
  - name: 上海交通大学
    routes:
      - path: /sjtu/jwc
        needs_classification: false   # 教务处天然窄
      - path: /sjtu/yzb
        needs_classification: false
  - name: 清华大学
    routes:
      - path: /tsinghua/news
        needs_classification: true
```

每条路由需人工 review 一次（**这是方案 B 的主要工作量**：约 28 × 5 分钟 = 2.5 小时）。

## 4. RSSHub 部署：自托管 vs 公共

| 方案 | 优点 | 缺点 | 推荐度 |
|---|---|---|---|
| 公共实例 `rsshub.app` | 0 配置 | 限流、偶尔挂、IP 被高校 ban | POC 阶段可用 |
| **Vercel 部署** | **0 元，稳定** | 部分路由不兼容 | **生产推荐** |
| Cloudflare Workers | 免费 | 部分路由不兼容 | 折中 |
| 阿里云 99/年 ECS | 稳定 | 8 元/月 | 备选 |

## 5. 与方案 A 的协同

方案 A 的 `pipeline/` 完全复用，只增加：
- `fetchers/rsshub_batch.py`：读 sources.yaml，并发拉取所有 RSS
- `pipeline/classifier.py`：扩展为支持批量

**整体最终架构（A+B 合并后）**：

```
fetchers:
  - rsshub_batch.py   ← 28 所（方案 B）
  - fudan.py          ← 11 所自写中的 1 所（方案 A 同款）
  - <other_10>.py     ← 剩余 10 所自写
                ↓
        统一 Item Stream
                ↓
   classifier (按 needs_classification 标志位决定是否调用)
                ↓
       dedup → render → push
```

## 6. 方案 B 测试计划

### T-B1 路由健康度

跑一次全量拉取，记录每条路由：

| 指标 | 阈值 |
|---|---|
| HTTP 成功率（连续 7 天） | ≥ 95% |
| 单路由日均条目数 | 1 ≤ x ≤ 50（>50 说明选错路由，太宽） |
| 标题非乱码率 | 100% |

### T-B2 招生召回回测

人工从各高校官网招生办抽 50 条已发布消息，验证 RSSHub 路由是否覆盖到。

| 指标 | 阈值 |
|---|---|
| 覆盖率 | ≥ 80%（达不到说明路由选漏，需补） |

### T-B3 公共实例 vs 自托管 A/B

并行跑 1 周，对比成功率。决定是否上自托管。

## 7. 工作量估算

| 阶段 | 工作量 |
|---|---|
| sources.yaml 人工筛路由（28 所） | 0.5 天 |
| rsshub_batch fetcher | 0.5 天 |
| 集成现有 pipeline | 0.5 天 |
| T-B1/B2 测试 + 调优 | 1 天 |
| 自托管 RSSHub Docker / Vercel（可选） | 0.5 天 |
| **合计** | **3 天**（在方案 A 完成基础上） |

## 8. 推荐执行顺序

1. **W1** 方案 A POC（3 所，跑通全链路 + 7 天验收）
2. **W2** 方案 B（扩展到 28 所 RSSHub 高校）
3. **W3** 自写剩余 11 所
4. **W4** 优化分类器、上线生产、加监控
