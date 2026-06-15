---
name: cheat-status
description: cheat-on-content 的状态看板。显示当前模式 / rubric 版本 / 校准进度 / 待复盘 / pool 状态 / 是否该升级 SQLite / 是否该 bump rubric。**任何时候都可调，无副作用**。触发词："状态"/"看板"/"status"/"我现在该做什么"/"进度怎么样"。
allowed-tools: Bash(*), Read, Glob, Grep
---

# /cheat-status — 状态看板

读 state file + 扫描用户项目 → 汇总当前进度 → 输出"今天该做什么"清单。

## Overview

```
[用户：状态]
  ↓
[Phase 1: 读 .cheat-state.json + 扫文件系统]
  ↓
[Phase 2: 计算派生指标]
  ↓
[Phase 3: 检测建议触发器（升级 / bump / 清算）]
  ↓
[Phase 4: 输出看板]
```

## Constants

- **SQLITE_UPGRADE_THRESHOLD = 30** — calibration_samples 达到 N 时建议升 SQLite
- **CLEANUP_LINE_THRESHOLD = 600** — rubric_notes.md 行数超 N 时建议清算
- **STALE_PREDICTION_DAYS = 30** — in_progress prediction 超 N 天未发布提示清理

## Inputs

| 来源 | 用途 |
|---|---|
| `.cheat-state.json` | 主要状态 |
| `predictions/*.md` | 校准样本数 / pending retros |
| `candidates.md` | 候选池规模 |
| `rubric_notes.md` | 行数 / 当前版本 |
| `.cheat-cache/usage.jsonl`（如有） | meta-logging 数据，用于"距上次 bump 多少次预测" |

## Workflow

### Phase 1: 读状态

```python
state = read_json('.cheat-state.json')
if not state:
    return "你还没初始化。请先跑 /cheat-init。"

predictions = glob('predictions/*.md')
candidates_count = parse_candidates_md_entries()
rubric_lines = wc -l rubric_notes.md
```

### Phase 2: 派生指标

| 指标 | 算法 |
|---|---|
| **Buffer 数** | `len(state.shoots)` |
| **Buffer 颜色** | 按 [cadence-protocol.md](../../shared-references/cadence-protocol.md) 派生：`buffer_days = buffer_count × target_publish_cadence_days`，`<1 红 / 1-2 橙 / 3-5 绿 / >5 蓝`。如 `target_publish_cadence_days=null` → 颜色禁用 |
| **Confidence 等级** | 按 [state-management.md confidence 表](../../shared-references/state-management.md) 派生：从 `calibration_samples` 整数派生 emoji + 标签 |
| **最早一拍至今天数** | `now - state.shoots[0].shot_at`，用于警告"拍了 N 天没发" |
| 校准样本数 | predictions 中含完整复盘段（实绩数据非空）的文件数 |
| 待复盘 | state.pending_retros 中已过 RETRO_WINDOW_DAYS 的 |
| 池大小 | candidates.md 中 tier!=skip 的 entry 数 |
| 上次 bump 至今几次预测 | predictions 中 published_at > state.last_bump_at 的数量 |
| 同向偏差队列 | state.consecutive_directional_errors |
| in_progress 陈旧度 | now - state.in_progress_session.started_at（如有） |

### Phase 3: 检测建议触发器

按优先级（高→低）逐项检查：

1. **Buffer 颜色 = 🔴 红** → 第一行高优先级警戒："buffer 已 0/1 篇，下个发布日可能断更——今天必须拍 ≥1 条。说'推荐选题'我只推 top 1 稳分（不推实验性）"
2. **Buffer 颜色 = 🔵 蓝** → 高优先级提示："buffer 已 N 篇积压。**暂停拍摄**，先发存货 + 复盘。说'已发布 ...'我帮你出队"
3. **state.shoots 中最早一项 shot_at > 14 天** → "你有视频拍了 N 天还没发——议题时效流失风险，建议尽快发或弃稿"
4. **in_progress 陈旧** (>= STALE_PREDICTION_DAYS) → 高优先级提示"清理或 publish"
5. **待复盘 ≥ 1** → 高优先级"今天该复盘 X 篇"
6. **`pool_status=none` + `calibration_samples=0` + 距 init >24h** → "🌱 你 init 完已经 N 天但还没拍——是因为没选题吗？跑 /cheat-seed 5 分钟拿 5 个候选 + 5 个 draft" 高优先级
7. **Claude 判断系统性偏差信号**（**不是死磕 ≥3 同向**） → 提示"建议跑 /cheat-bump"
   - **默认参考**：连续 ≥3 次同向偏差
   - **但 Claude 可以更早**：1 次极端偏差（≥10x）或 2 次同向 + 评论区强反向证据
   - **也可以更晚**：3 次同向但每次幅度都 <25%（可能只是噪声）
   - 提示时显式标注："本次是 [default-aligned] / [judgment-driven]"
8. **calibration_samples 跨入新 confidence 等级**（0→1, 2→3, 5→6, 10→11, 20→21）→ 提示"🎉 confidence 升级：<旧等级> → <新等级>。bucket 中枢精度从 ±X% 提到 ±Y%"。**仅作通知，无任何用户必须确认的操作**——所有 skill 都已经按 calibration_samples 自动调整
9. **calibration_samples 跨过 5** → "你的 rubric 形态可以第一次正式 bump 了。回顾 rubric_notes.md 看观察记录段是否有 ≥3 样本支持的 pattern → 跑 /cheat-bump"
10. **calibration_samples 跨过 10** → "可以跑 /cheat-bump --bucket-only --scheme percentile 让 bucket 边界改用 percentile（永远自洽）"
11. **calibration_samples 跨过 SQLITE_UPGRADE_THRESHOLD** 且 data_layer=markdown → "建议跑 tools/md-to-sqlite.py"（planned — batch 3, not yet available）
12. **rubric_notes.md 行数 > CLEANUP_LINE_THRESHOLD** → "建议清算观察段（手动或下次 bump 触发）"
13. **calibration_samples ≥ 5 + pool_status=none** → "可以开始建立选题池了"
14. **calibration_samples ≥ 15 + pool_status=none** → "强烈建议建池：/cheat-trends 或手动建 candidates.md"
15. **state.hooks_installed=false** → "你的 immutability 是君子协定，建议跑 /cheat-init 装 hook"
16. **state.last_bump_self_audited=true** → "上次 bump 是自审。建议配置 mcp__llm-chat__chat 后下次 bump 走外部审"
17. **state.rubric_form_mismatch=true** → "你的 content_form 不是 opinion-video，用了内置观点 rubric。前几篇预测会更不准，下次 bump 时建议自行调整权重适配你的形态"
18. **state.benchmark_status=pending** → "🎯 你 init 时答应等下找对标账号但还没找。跑 /cheat-learn-from 导入 ≥3 条对标视频，工具就有 anchor 了"
19. **state.benchmark_status=imported + Claude 判断用户数据信号已超过 benchmark** → "📊 你的真实数据已经成为主信号，benchmark 影响淡出"
   - **默认参考**：calibration_samples ≥ 10
   - **但 Claude 可以更早**：N=5 但用户的 (打分, 实绩) 配对里出现 ≥3 条与 benchmark pattern 不一致的——说明你的账号已经走出对标的路径
   - **也可以更晚**：N=15 但用户的样本都很相似，没足够多样性 → benchmark 仍有信号价值
   - 提示是**通知不是 gate**——benchmark.md 永远保留作 sanity check，cheat-seed 仍可读

### Phase 4: 输出看板

```
🎛️ cheat-on-content 状态（更新于 2026-05-04 15:00）

内容形态：opinion-video / 时长 3-5min / cadence: 隔日更
当前 rubric：v2 (上次 bump: 2026-04-22)
校准样本：18 篇
Confidence: 🟢 较高 (中枢 ±15%，rubric 形态稳定)
Baseline: 4.2w 中位数

📦 Buffer：3 篇（🟢 绿色）
   按你的 cadence (隔日更)= 6 天 buffer，节奏稳定

📊 进度条
  [█████████████░░░░░] 18 / 30 → SQLite 升级建议门槛
  [██████████░░░░░░░░] 18 / 10 → percentile 桶可用（已超过门槛）

🎬 待办（按紧急度）
  🚨 复盘 1 篇（已过 T+3d）
     - predictions/2026-05-01_db063817_你已不在关系里.md（T+3d 到了）
  ⚠️  同向偏差 3 次（high, high, high）→ 建议 /cheat-bump
  💤 in-progress prediction 已陈旧 35 天
     - predictions/2026-04-01_xxx.md → 是已发了忘登记？还是弃稿？

🔥 候选池
  - candidates.md: 27 条（tier1: 12, tier2: 9, tier3: 6）
  - 距上次抓热点: 4 天 — 可以再跑 /cheat-trends

📈 健康度
  - rubric_notes.md: 412 行（健康，<600 警戒线）
  - hooks_installed: ✅
  - external audit configured: ❌ → 建议配 mcp__llm-chat__chat

下一步建议（按推荐优先级）：
1. /cheat-retro predictions/2026-05-01_db063817_你已不在关系里.md  ← 最紧急
2. /cheat-bump  ← 同向偏差 3 次的处理
3. 处理陈旧 in-progress（手动或回 "清理 in-progress"）

完整的命令清单见主 SKILL.md。
```

输出风格：**直白、具体、可点击**。每个建议附确切的命令——用户应能 copy-paste 直接执行。

## Key Rules

1. **无副作用**。读多写零。任何状态修改是其他 skill 的事
2. **不假装数据可用**。state file 字段缺失 → 显式标"未知"，不猜
3. **建议带优先级**。10 个建议同时显示用户会麻木——按紧急度排
4. **每个建议附命令**。不能只说"该 bump 了"——要给 `/cheat-bump --propose "..."` 的精确入口

## Refusals

- 「顺便帮我自动跑一下 retro」 → 拒绝。status 是只读，retro 是另一个动作（避免一次操作做两件事）
- 「我不想看 rubric_notes 行数，太琐碎」 → 输出仍包含但折叠到底部"健康度"区——状态信息的存在让用户在出问题前可见

## Integration

- 上游：所有其他 skill 完成时更新 .cheat-state.json，status 是这些更新的可视化
- 下游：每个建议都路由到具体子 skill
- meta-logging hook（如启用） → 写 usage.jsonl，status 用它算"距上次 X 多少次"
