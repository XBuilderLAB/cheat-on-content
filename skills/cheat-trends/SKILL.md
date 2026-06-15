---
name: cheat-trends
description: 从配置的热点源（HN / Reddit / YouTube trending / B 站热门 / 等）抓今天的热门话题，去重 + 粗打分 + 写入 candidates.md。**绝大部分人没有候选池——这是让"我没素材"问题在 onboarding 第二步就消失的钥匙**。触发词："抓热点"/"fetch trends"/"今天有什么可做的"/"trending now"/"找选题"。
argument-hint: [— sources: <comma-separated>] [— max-per: 20]
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheat-trends — 热点抓取

多 adapter 模式：读各 `trend-sources` adapter 的输出 → 去重 → 粗打分 → 写入 `candidates.md`。

## Overview

```
[用户：抓热点]
  ↓
[Phase 0: 读 .cheat-state.json 拿 enabled adapters]
  ↓
[Phase 1: 对每个 adapter 调 fetch]
  ↓
[Phase 2: normalize 到 candidate-schema]
  ↓
[Phase 3: 去重（vs candidates / predictions / trends-history）]
  ↓
[Phase 4: 对每个新 item 粗打分（调 cheat-score 内联逻辑）]
  ↓
[Phase 5: 排序 + 询问用户哪些加入 candidates.md]
  ↓
[Phase 6: 写入 + 更新 trends-history.jsonl 缓存]
```

## Constants

- **TREND_SOURCES = ["manual-paste"]** — 启用的 adapter 列表（默认仅 manual-paste，最稳）
- **LOOKBACK_HOURS = 24** — 抓最近 N 小时的热点
- **MAX_PER_SOURCE = 20** — 每个 adapter 最多 N 条
- **DEDUPE = true** — 去重开关
- **AUTO_SCORE = true** — 抓回来后自动调 cheat-score 粗打分
- **MIN_COMPOSITE_TO_SUGGEST = 6.0** — 低于此分的不推荐用户加入候选池（仍写入 trends-history 避免下次重复推）

> 💡 调用时覆盖：`/cheat-trends — sources: manual-paste,aihot,weibo-hot — max-per: 10`

## Inputs

| 必填 | 来源 |
|---|---|
| `.cheat-state.json` | 默认 sources |
| `adapters/trend-sources/<name>.md` | 各 adapter 的实现描述 |
| `candidates.md` | 去重对照 |
| `predictions/*.md` | 去重对照（已发的不再推） |
| `.cheat-cache/trends-history.jsonl` | 历史抓取去重缓存 |

## Workflow

### Phase 0: 读启用的 adapters

```python
# 伪代码
state = read('.cheat-state.json')
enabled_adapters = args.sources or state.get('enabled_trend_sources', ['manual-paste'])
```

如 enabled_adapters 为空 → 输出引导：

```
你目前没有启用任何热点源。

最快配法：
- 临时跑：/cheat-trends — sources: manual-paste,aihot
- 永久启用：编辑 .cheat-state.json 的 enabled_trend_sources 数组

可用 adapter（详见 adapters/trend-sources/）：
- manual-paste（默认，永远能用）
- aihot（AI 热点聚合，无需 key）
- weibo-hot（微博热搜，无需 key）
- zhihu-hot（知乎热榜，无需 key）
- trendradar-mcp（TrendRadar MCP 服务，需配置）
```

### Phase 1-2: 对每个 adapter 调 fetch + normalize

对每个 adapter，读其 `adapters/trend-sources/<name>.md` 中描述的 fetch 接口（实际是 Bash 调底层 Python / shell / WebFetch）：

| Adapter | 实现机制 |
|---|---|
| `manual-paste` | 询问用户："粘贴你今天的候选 URL/标题列表（每行一条）" → 解析每行，对 URL 做 WebFetch 拓展 snippet |
| `aihot` | 读 adapters/trend-sources/aihot.md 描述的 fetch 接口 |
| `weibo-hot` | 读 adapters/trend-sources/weibo-hot.md 描述的 fetch 接口 |
| `zhihu-hot` | 读 adapters/trend-sources/zhihu-hot.md 描述的 fetch 接口 |
| `trendradar-mcp` | 读 adapters/trend-sources/trendradar-mcp.md 描述的 fetch 接口 |

每个 adapter 输出符合 [candidate-schema.md](../../shared-references/candidate-schema.md) 的 items。

**优雅降级**：单 adapter 失败（API key 缺失 / 端点 503 / cookie 失效）→ skip 该 adapter，**不抛异常**，在汇总里说明：
```
✅ aihot: 拉到 18 条
✅ weibo-hot: 拉到 15 条
✅ zhihu-hot: 拉到 12 条
⚠️  trendradar-mcp: 跳过（MCP 服务未配置——配置见 adapters/trend-sources/trendradar-mcp.md）
```

### Phase 3: 去重

按 [candidate-schema.md](../../shared-references/candidate-schema.md) 的"去重协议"：

1. 对每个 item 算 id（`sha256(source_type + normalized_title + url_path)[:12]`）
2. 检查 `candidates.md` 已含此 id → 跳过
3. 检查 `predictions/*.md` 已含此 id → 跳过
4. 检查 `.cheat-cache/trends-history.jsonl` 已含此 id 且 `rejected_at != null` → 跳过

去重统计写到汇总报告里。

### Phase 4: 粗打分

`AUTO_SCORE=true` 时，对每条新 item：
1. 用 item 的 `snapshot_text` 作为输入
2. 按当前 rubric 给 7 维打分（**不**调 `/cheat-score` 子 skill 走 IO；inline 复用打分逻辑）
3. 算 composite
4. 给一句 rationale

**注意**：粗打分 ≠ 正式预测。预测必须基于最终稿（用户改过的），这里的打分只是"是否值得展开写"的粗筛。

`AUTO_SCORE=false` 时，items 写入 candidates.md 时 composite=null，需要后续手动 `/cheat-score`。

### Phase 5: 排序 + 询问

按 composite 降序，过滤掉 composite < `MIN_COMPOSITE_TO_SUGGEST` 的：

```
🔥 抓热点完成。各源拉取统计：
- manual-paste: 5 条（用户输入）
- aihot: 18 条
- weibo-hot: 15 条
跳过 trendradar-mcp（MCP 服务未配置）

去重后剩 27 条新 item。
粗打分后 12 条 composite ≥ 6.0：

| # | 标题 | source | composite | bucket | rationale |
|---|---|---|---|---|---|
| 1 | 为什么我们都讨厌主动联系朋友 | aihot | 8.4 | 30-100w | ER+QL 双 5，AB 普适 |
| 2 | "她不一样"的一千种变体 | weibo-hot | 8.1 | 30-100w | MS 候选维度高 |
| 3 | ...... |

哪些加入 candidates.md？
- 全部加 → 回 "all"
- 选几个 → 回 "1, 3, 5"
- 都不要 → 回 "none"（这些会被记到 trends-history 避免下次重复推）
```

### Phase 6: 落盘

用户响应后：
1. 选中的 items → 按 [candidate-schema.md](../../shared-references/candidate-schema.md) 的"Markdown 表示"格式追加到 `candidates.md`
2. 所有抓回来的 items（不管选中与否）→ append 到 `.cheat-cache/trends-history.jsonl`：
   ```jsonl
   {"id": "...", "title": "...", "source": "...", "snapshot_at": "...", "rejected_at": null|"<ISO>", "fetched_at": "<ISO>"}
   ```

### Phase 7: 状态更新

```json
{
  "last_trends_run_at": "<ISO>",
  "last_trends_added_count": 5
}
```

## Key Rules

1. **不抛异常**。单 adapter 失败 → skip + 报告。多 adapter 全失败 → 报错"所有源都失败"，附排查指引
2. **manual-paste 永远在**。即使其他所有 adapter 都坏了，manual-paste 模式必须能跑——它是兜底
3. **去重是硬约束**。同 id 不重复推；用户拒绝过的 6 个月内不再推
4. **粗打分要诚实标注**。在 candidates.md 的 entry 里标 `composite (rough, snapshot-based)`，避免与 prediction 的精打分混淆
5. **不直接进 predictions/**。trends 只产 candidates，predict 是另一个动作

## Refusals

- 「直接抓抖音热门 feed，不用 cookie」 → 拒绝。抖音反爬极严，无 cookie 必失败；引导到 douyin-session adapter 配置文档
- 「跳过去重，把所有抓到的都写进去」 → 拒绝。会污染候选池，下次 recommend 时排序失效
- 「跳过粗打分，直接写 raw 标题」 → 允许（`AUTO_SCORE=false`），但提示用户后续需要 `/cheat-score` 才能进 recommend 池

## Integration

- 上游：用户配置 `.cheat-state.json` 的 `enabled_trend_sources` 数组
- 下游：`/cheat-recommend` 直接读 `candidates.md` 排序——trends 写完，recommend 立刻看到
- 与 `/cheat-init`：onboarding Q4 选"没有候选池"的用户被引导到这里
- 与 `/cheat-status`：status 看板显示"上次抓热点：X 天前 / 待清理候选池：Y 条"

## Adapter 实现注意事项

每个 `adapters/trend-sources/<name>.md` 必须文档化以下：
1. **依赖**：API key / cookie / package
2. **fetch 接口**：调用方式（python script path / shell command / API endpoint）
3. **输出 schema**：必须符合 candidate-schema.md
4. **失败模式**：常见错误 + 优雅降级行为
5. **稳定性等级**：★ 1-5 颗星

详见 [adapters/HOWTO.md](../../adapters/HOWTO.md)（待批次 3 实现）。
