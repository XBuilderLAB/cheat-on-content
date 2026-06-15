# Adapter: weibo-hot（微博热搜）

被以下 skill 调用：`cheat-seed` Phase 2a、`cheat-trends`。

> **当前状态**：schema only。实际 fetch 实现归 batch 3。/cheat-seed 在 stub 期由 Claude 通过 `WebFetch` 直接抓取 + 解析（见下方"过渡期实现"）。

---

## 适用场景

- **`cheat-seed` 默认 source 之一**——cold-start 用户的第一次选题种子
- **`cheat-trends` 可选 source**——日常补充候选池

最贴合：时事评论、社会议题、热点解读类观点视频。

## 依赖

- 公开端点，**无需 cookie**
- 端点：`https://s.weibo.com/top/summary?cate=realtimehot`（HTML 页面）
- 备选：`https://weibo.com/ajax/side/hotSearch`（JSON，部分时段返回 401，不稳定）

## Fetch 接口

```
fetch(limit: int = 50) -> List[Candidate]
```

返回符合 [shared-references/candidate-schema.md](../../shared-references/candidate-schema.md) 的 items 列表。

字段映射：
- `id`：`sha256("weibo-hot|" + normalized_title + "|" + url_path)[:12]`
- `title`：热搜词
- `source`：`"trend:weibo-hot"`
- `snapshot_text`：热搜词 + （如有）官方标签 + 简短摘要（自动从热搜详情页抓 1-2 句）
- `snapshot_at`：抓取时间 ISO 8601
- `url`：`https://s.weibo.com/weibo?q=<encoded_keyword>`
- 其他字段：null（抓取阶段不打分；由调用方 cheat-score 处理）

## 失败模式

| 症状 | 处理 |
|---|---|
| HTML 结构变化导致解析失败 | 返回空列表 + stderr 写明 "weibo HTML 结构变化，参考 adapters/trend-sources/weibo-hot.md 自行修补" |
| 端点 503 / 限流 | 返回空列表 + 报告 |
| 网络不可达 | 返回空列表 + 报告 |

**优雅降级**：单次失败不抛异常——调用方（cheat-seed / cheat-trends）会用其他 sources 兜底。

## 稳定性等级

★★★ — 公开端点，但微博偶尔调整页面结构 + 有反爬（同一 IP 短时间高频抓取会被限流）。

建议节流：`/cheat-seed` 默认每用户每天 ≤ 3 次抓取——cold-start 阶段不需要更高频。

## 过渡期实现（stub）

在 batch 3 写专用 adapter 实现前，`/cheat-seed` 在调用本 source 时直接由 Claude 通过 `WebFetch` 工具抓 `https://s.weibo.com/top/summary?cate=realtimehot`，从 HTML 中提取 top 50 热搜标题。具体由 cheat-seed 的 Phase 2a 处理：

```
WebFetch("https://s.weibo.com/top/summary?cate=realtimehot",
         "提取 top 50 热搜的标题文本，每行一个，按热度降序")
```

如果 WebFetch 返回的内容能识别出 ≥10 条热搜 → 视为成功；否则视为失败，跳过本 source。

## 风险提示

- 微博热搜内容**经常含政治敏感 / 娱乐八卦**议题——/cheat-seed Phase 1 Q3 的"红线"过滤至关重要
- 部分热搜词太短（5-10 字）缺少上下文——Claude brainstorm 时需要展开
- 热搜的"热度"分数与"适合做观点视频的程度"**不正相关**——粗打分时不要直接把热度当 composite 输入

## 相关 adapter

- [zhihu-hot.md](zhihu-hot.md) — 议题深度更高，论说类更匹配
- bilibili-popular.md（待）— 偏年轻议题
- thirdparty-paid.md（待）— 新榜 / 飞瓜，付费但稳定
