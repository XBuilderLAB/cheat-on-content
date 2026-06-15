# Adapter: zhihu-hot（知乎热榜）

被以下 skill 调用：`cheat-seed` Phase 2a、`cheat-trends`。

> **当前状态**：schema only。实际 fetch 实现归 batch 3。/cheat-seed 在 stub 期由 Claude 通过 `WebFetch` 直接抓取（见下方"过渡期实现"）。

---

## 适用场景

- **`cheat-seed` 默认 source 之一**——cold-start 用户的第一次选题种子
- **`cheat-trends` 可选 source**——日常补充候选池

最贴合：论说 / 议题讨论 / 知识科普类观点视频。知乎话题平均比微博更"可讨论"——一个标题就含问题与立场，省了 brainstorm 一半工。

## 依赖

- 公开端点，**无需登录**
- 端点：`https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true`（JSON）
- 备选：`https://www.zhihu.com/billboard`（HTML，可作为兜底）

## Fetch 接口

```
fetch(limit: int = 50) -> List[Candidate]
```

返回符合 [shared-references/candidate-schema.md](../../shared-references/candidate-schema.md) 的 items 列表。

字段映射：
- `id`：`sha256("zhihu-hot|" + normalized_title + "|" + url_path)[:12]`
- `title`：知乎问题标题
- `source`：`"trend:zhihu-hot"`
- `snapshot_text`：问题标题 + 高赞答案前 200 字摘要（可选——抓不到就只用标题）
- `snapshot_at`：抓取时间 ISO 8601
- `url`：知乎问题 URL（如 `https://www.zhihu.com/question/<id>`）
- 其他字段：null

## 失败模式

| 症状 | 处理 |
|---|---|
| API 端点变更 | 切换到 `/billboard` HTML 兜底 |
| API 返回需要登录（403） | 返回空列表 + 报告 |
| 网络不可达 | 返回空列表 + 报告 |

**优雅降级**：失败不抛异常——调用方有其他 sources 兜底。

## 稳定性等级

★★★★ — 知乎 API 比微博稳定；JSON 端点改动频率低于微博 HTML。

建议节流：`/cheat-seed` 默认每用户每天 ≤ 3 次抓取。

## 过渡期实现（stub）

在 batch 3 写专用 adapter 前，`/cheat-seed` 通过 `WebFetch`：

```
WebFetch("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50&desktop=true",
         "解析 JSON 中 data 数组的每个 item，提取 target.title_area.text 和 target.url，最多 50 条")
```

如果返回结构识别失败 → 切换到 `/billboard` HTML 抓取兜底。

## 内容特点（影响 brainstorm 质量）

知乎热榜的标题结构通常是 **完整的疑问句**（"如何看待 X"、"为什么 Y"、"X 的本质是什么"），比微博热搜的关键词更适合直接转化为观点视频选题。

但要注意：
- 一些标题太具体（"X 公司裁员事件"）→ Claude brainstorm 时要做"个案 → 普遍"的抽象提升
- 一些标题太"知乎腔"（学术化、长难句）→ Claude brainstorm 时要做"知乎话术 → 短视频钩子"的转译

## 风险提示

- 知乎热榜偶现政治敏感议题——/cheat-seed Phase 1 Q3 的"红线"过滤必要
- 部分热榜话题已被知乎大 V 高密度覆盖，做视频时差异化不易——粗打分时建议提示用户"该话题已饱和，需要差异化角度"

## 相关 adapter

- [weibo-hot.md](weibo-hot.md) — 议题更广但更碎片化，时事评论类更匹配
- bilibili-popular.md（待）— 视频内容直接对照参考
- thirdparty-paid.md（待）— 付费稳定数据源
