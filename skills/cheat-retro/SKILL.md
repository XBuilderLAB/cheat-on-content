---
name: cheat-retro
description: T+N 天数据回收 + 复盘 + 把新观察写入 rubric_notes.md。这是校准循环的反馈环节——不复盘的预测等于占星。触发词："复盘 [path]"/"retro this"/"T+3d 数据来了"/"抓数据 [path]"/"把这篇复盘了"。
argument-hint: <prediction-file> [— window: 3|5|7] [— source: manual|adapter]
allowed-tools: Bash(*), Read, Edit, Write, Glob, Grep, Skill
---

# /cheat-retro — 数据回收与复盘

抓 T+N 天的实际表现 → 对比预测 → 提炼新观察 → 写入 rubric_notes.md。**只追加 `## 复盘` 段，绝不改预测段**。

## Overview

```
[用户：复盘 predictions/2026-05-04_...]
  ↓
[Phase 0: 校验 immutability + 校验时间窗口]
  ↓
[Phase 1: 抓数据（manual paste 或 adapter）]
  ↓
[Phase 2: 写实绩段 + top 评论关键词]
  ↓
[Phase 3: 验证/推翻预测的各假设]
  ↓
[Phase 4: 提炼新观察]
  ↓
[Phase 5: 落盘（追加到 ## 复盘 段）]
  ↓
[Phase 6: 写入 rubric_notes.md 的"观察记录"段]
  ↓
[Phase 7: 检测是否触发 bump 候选 → 提示用户跑 /cheat-bump]
```

## Constants

- **RETRO_WINDOW_DAYS = 3** — 默认 T+3d。短视频快平台可设 1，长文设 7
- **DATA_SOURCE = manual** — manual: 用户粘数字；adapter: 调对应平台 adapter（需配置）
- **AUTO_PROPOSE_BUMP = true** — Claude 判断是否系统性偏差时自动提议 /cheat-bump
  - **默认参考**：连续 ≥3 次同向偏差（high/low）→ 提议
  - **但 Claude 可以更早提议**：1 次极端偏差（如中枢 50w 实绩 5w 这种 ≥10x），即使没有"连续"也提议
  - **也可以更晚**：3 次同向但每次偏差都很小（<25%），可能只是噪声不是系统性
- **TOP_COMMENTS_N = 20** — 抓 / 粘 top N 高赞评论

> 💡 调用时覆盖：`/cheat-retro <file> — window: 7 — source: adapter`

## Inputs

| 必填 | 来源 |
|---|---|
| `<prediction-file>` 或 `<video-folder>` | 用户参数；缺失则从 `.cheat-state.json` 的 `pending_retros[0]` |
| `rubric_notes.md` | 用户项目根 |
| `.cheat-state.json` | 状态文件 |

### 入参解析（同 cheat-predict 双形态接受）

用户给的可能是：
- **`predictions/2026-05-04_<id>_<short>.md`** → 直接用这个 prediction 文件
- **`videos/2026-05-04_<id>_<short>/`** → 找对应的 prediction 文件（按 id 匹配）+ 把 report.md 写到该 video folder 里
- 缺省 → 从 `pending_retros[0]` 取最早的

## Workflow

### Phase 0: 校验

1. 读 `<prediction-file>`，确认存在
2. **识别有效预测段**：扫所有 `## 预测...` 段（可能含 `## 预测`、`## 预测 v1`、`## 预测 v2` 等）：
   - 取**最后一个**`## 预测 vN` 作为本次校准的依据（v2 存在则用 v2；只有 v1 则用 v1；legacy 单段 `## 预测` 直接用）
   - state.shoots 对应项的 `v2_prediction_written` 应与"是否存在 v2 段"一致——不一致则警告（state 与文件脱节）
3. **校验 immutability**：在内存 cache 住所有 `## 预测...` 段的内容（用于 Phase 5 后核对——**全部段不可改**，不只是有效段）
4. 校验文件 header 有 `Published at` → 没登记的不能复盘，提示用户先 `/cheat-publish`
5. 校验时间窗口：今天 - published_at >= RETRO_WINDOW_DAYS。不够 → 提示"还差 X 天"，询问用户是否仍坚持复盘（标 `early_retro: true`）
6. 校验已有复盘段是否已填——已填则询问"是补充还是修正？"
   - 补充 → 在已有复盘段下追加新子段，标日期
   - 修正预测段（用户错觉）→ 拒绝

### Phase 1: 抓数据

按 `state.data_collection` 字段分两条路径——抓回数据后**写到 video folder 的 `report.md`**（如果 prediction 关联 video folder），同时解析摘要 inline 到 prediction 的复盘段。

#### Path A：`DATA_SOURCE=manual`（候补方案）

- 询问用户："粘贴这条作品的当前数据：播放 / 点赞 / 评论 / 转发 / 收藏（顺序无所谓，能识别就行）"
- 用户粘 → 解析提取数字
- **强制要求 top 评论**：让用户从平台后台或直接打开评论区贴 TOP_COMMENTS_N 条到对话里（每条带赞数）
  - 用户拒绝 / 给少于 5 条 → **拒绝继续**："评论才是真信号——'她不一样'这种模因爆发只能从评论看出。
    没评论的复盘 = 看体温计判断病情。粘 top 20 给我。如果实在拿不到，告诉我原因（比如评论被关了），我帮你标 `comments_unavailable`，但这次复盘价值打折。"
- 把粘的原始数据写到 `videos/<...>/report.md`（如有 video folder）

#### Path B：`DATA_SOURCE=adapter`

按 prediction header 的 `Platform` 字段 + state 的 `enabled_perf_adapters` 决定调哪个：

| Platform | Adapter | 调用方式 |
|---|---|---|
| `douyin` | `adapters/perf-data/douyin-session/` | `bash <adapters-dir>/douyin-session/run.sh <aweme_id> <video_folder>` |
| `xhs` | `adapters/perf-data/xhs-explore/` | `bash <adapters-dir>/xhs-explore/run.sh <note_id> <video_folder>` |
| `youtube` | `adapters/perf-data/youtube-data-api/`（待） | 调 YouTube Data API（需 API key） |
| `bilibili` | `adapters/perf-data/bilibili-stat/`（待） | 调 B 站官方 stat 接口 |
| 其他 | 无 adapter | 优雅降级到 Path A |

> `<adapters-dir>` = 克隆源码处的 `cheat-on-content/adapters/perf-data/`（install.sh **不**复制 adapter 到 ~/.claude/skills，只复制 15 个 skill）。定位：`find ~ -path '*/cheat-on-content/adapters/perf-data' -type d | head -1`。

**douyin-session 的特殊处理**：
- 视频 URL（如 `https://v.douyin.com/abc123`）→ 短链解析 → 提取 aweme_id
- 调用前确认 cookie 文件存在（adapter 会找 `.auth/`）；不存在则提示用户先跑 `python <adapter>/crawler.py login`
- adapter 输出在 `<video_folder>/report.md`（adapter 的 renderer.py 已经按这个格式写）
- cheat-retro 读这个 report.md 解析关键数据 → 摘要写入 prediction 的复盘段

**xhs-explore 的特殊处理**：
- 笔记 URL（`https://www.xiaohongshu.com/explore/<note_id>?xsec_token=...` 或 `https://xhslink.com/xxx`）→ 提取 note_id
- 调用前确认 cookie 存在（adapter 找 `.auth-xhs/`）；不存在则提示先跑 `python <adapter>/crawler.py login`
- 字段已校准（观看 `view_count` 等已写死）；万一接口改版导致某项为 0，看 report.md 末尾 galaxy 原始 JSON，把新 key 加进 `crawler.py` 的 `_normalize_note`
- **评论可能抓不到**（xsec_token 缺失 / 评论关闭）→ report.md 标"未抓到评论" → 此时**降级要求用户 manual 粘 top 20 评论**（评论是真信号，不能省）

**任何 adapter 失败**（cookie 过期 / 接口变化 / 网络）→ **优雅降级到 manual**，提示用户："adapter 调用失败，原因 [X]。改用 manual 模式——粘下面的数据"。**不阻塞流程**。

#### 共同输出

不管 Path A 还是 B，最终：
- `videos/<...>/report.md` 含完整原始数据（数字 + top 评论）
- prediction 文件复盘段含**摘要**（关键比率 + 评论关键词聚类 + 验证/推翻判定）
- report.md 是数据真相，prediction 复盘段是判断真相

### Phase 2: 写实绩段 + top 评论分析

**实绩数据格式**（参考 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md) 的复盘段格式）：

```markdown
### 实绩数据
- 播放：71.1w（落在 `30-100w` 桶内偏高，相对中枢 50w **+42%**）
- 点赞：2.4w（赞播比 3.38%）
- 评论：899（评播比 0.126%）
- 收藏：5251
- 分享：1.8w（分播比 2.53%，强）
```

数据点之间的派生比率（赞播比、评播比、分播比）必须算出来——它们是单纯播放数无法暴露的信号。

**top 评论关键词聚类**：
- 把粘进来的 N 条评论分 3-5 类（高赞模因 / 概念引用 / 离题噪声 / 转发暴露暗示 / @朋友传播 等）
- 每类列代表性评论（带赞数）
- 报告比例（"22% 是模因复用、35% 是概念引用、5% 是离题"）

### Phase 3: 验证/推翻

对 prediction 文件里的每一项（推理因素表、关键校准假设、反事实场景），逐项判定：

```markdown
### 哪些预测被验证 ✅ / 推翻 ❌

**验证 ✅**:
- 关键校准假设完全成立：本篇 71.1w / 谁问你了 11.7w = 6.07x，远超我押的 1.5-2x
- ER=5 主导情感传播力 → H1 强证据
- HP=5 验证：分播比 2.53% 与"金句被高频引用"匹配

**推翻 ❌**:
- 中枢 50w 被超出 +42%
- 反事实推理里"必须搭配强社会议题才能破 30w" 完全错误
- SR 押注（"H2 SR 应上调"）反向被推翻：SR 在情感向场景几乎不贡献
```

**关键纪律**：
- 每条验证 / 推翻必须引用具体数据（"分播比 2.53%"），不许写"基本符合"这种含糊措辞
- 反事实的"如果落在 X bucket 意味着什么"——实际落在的那个 bucket 直接告诉你哪个 rubric 假设被测试了，明确写出来

### Phase 4: 提炼新观察（**两类，分别写入两个文件**）

#### 4a. Rubric 观察（写入 rubric_notes.md）

打分维度 / 公式 / bucket 边界相关的观察：

```markdown
### 需要写进 rubric_notes.md 的新观察

1. **ER 在情感向场景的真实权重应 ≥ ×2.0**：与谁问你了 6x 流量比是 v2 rubric 最强的反事实证据
2. **议题分享冲动 (TS) 是隐藏维度**：joker / "她不一样" / 滤镜重构提供了安全的自嘲身份，转发不暴露处境，TS=5 的样本
3. ……
```

每条观察必须可追溯到具体数据点（不写"情感很重要"——写"ER5/SR2 vs ER3/SR4 同 composite 下流量差 6x"）。

#### 4b. 写作 Pattern 观察（写入 script_patterns.md）

Diff `scripts/<id>.md`（pre-shoot 草稿，可能是 cheat-seed 写或用户写）vs `videos/<id>/script.md`（实际拍摄稿——cheat-shoot 时用户提供的版本），找出**改动且对流量有明显影响**的部分：

| 用户做了什么 | 流量影响 | 是否提议追加 pattern |
|---|---|---|
| 砍掉某段 | 实绩 ≥ 中枢 → "砍掉没伤流量"——验证那段冗余 | 是，加到 script_patterns.md "用户改稿历史观察"表 |
| 加了某句 / 互动钩子 | 实绩超中枢 → 可能是新 pattern | 是，候选 Pattern N，标 ≥1 样本待验证 |
| 改了风格（如开头软化） | 高于同类样本 → 风格改动有效 | 是，候选 Pattern N |
| 没动结构 / 改动与流量无关 | — | 不追加 |

输出格式：

```markdown
### 需要写进 script_patterns.md 的新 pattern 候选

1. **用户改稿模式**: 砍掉 [X 段] / 加了 [Y]
   - 流量影响：实绩 [N] vs 中枢 [M]，[偏差 / 命中]
   - 建议：追加到 script_patterns.md 的"用户改稿历史观察"表

2. **新 pattern 候选 N**：[一句话描述]
   - 单样本支持
   - 触发条件：[何时该用]
   - 建议：追加到 script_patterns.md 末尾的"新发现的 Pattern"段，标 ≥1 样本待验证
```

询问用户："要把这些追加到 script_patterns.md 吗？(yes / no / 选择哪几条)"。**用户确认后才追加**——避免把单点观察直接写成正式 pattern。

> **rubric 进化 ≠ 写作进化**——两者解耦：
> - rubric_notes.md 学的是"哪些维度真的预测流量"
> - script_patterns.md 学的是"什么写法真的能起作用"
> 可能有交叉（如 MS 维度与"互动钩子" pattern），但记录在两个文件里是因为**作用域不同**——rubric 改了影响所有未来打分，pattern 改了影响所有未来 draft。

如果 `videos/<id>/script.md` **缺失**（cheat-shoot 时用户标 `script_lost`） → 跳过 4b，没法 diff。
如果 `script_consistency = "consistent"`（用户拍时没改稿）→ 4b 仍然有意义（diff 也许是空），但可以快速跳过细查。
如果 `script_consistency = "modified"`（用户拍时改了）→ **4b 是核心**，重点学这次改动 → 流量影响。

### Phase 5: 落盘到 ## 复盘 段

用 Edit 工具，**仅追加**到现有 `## 复盘` 段（如有占位 `（待填）` 行先删除）：

```markdown
## 复盘

**复盘时间**: 2026-05-07（发布 T+3d）
**抓取时间**: 2026-05-07 09:30
**数据来源**: manual paste

### 实绩数据
[Phase 2 内容]

### Top 评论关键词
[Phase 2 内容]

### 哪些预测被验证 / 推翻
[Phase 3 内容]

### 需要写进 rubric_notes.md 的新观察
[Phase 4 内容]
```

**写完后再次校验**：读取保存后的文件，对比**所有** `## 预测...` 段（v1 / v2 / legacy）的合并哈希应等于 Phase 0 cache 的合并哈希。**任一段被改 → 报错并回滚**。

### Phase 6: 写入 rubric_notes.md + script_patterns.md

#### 6a. rubric_notes.md（Phase 4a 的输出）

按 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md) 的"观察记录模板"格式，追加到 `rubric_notes.md` 的 `## 观察记录` 段：

```markdown
### YYYY-MM-DD [标题简称] (id) — [一句话定性]
- 预测：composite=X.XX，bucket=Y
- 实绩：播放 / 点赞 / 评论 / 转发（带 T+Nd 标注）
- Top 评论关键词：[简短摘录 + 赞数]
- 判断：哪个维度被验证/推翻？为什么？
- Rubric 调整：[如果有，写明 "下次打 XX 类文章时改 YY"]
- 详见：[predictions/<file>.md]
```

**检测跨样本 pattern**：扫描已有"观察记录"，看新观察是否与某条已有观察形成 ≥2 样本支持。命中则按 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md) 升级到"重大跨视频观察"段。

#### 6b. script_patterns.md（Phase 4b 的输出，**用户确认后才写**）

如 Phase 4b 用户回 "yes" 或选择性确认了某几条：
- "用户改稿模式" → 追加到 script_patterns.md 的"用户改稿历史观察"表
- "新 pattern 候选 N" → 追加到末尾"新发现的 Pattern"段，**显式标 ≥1 样本待验证**

新 pattern 候选的格式（同 [script_patterns.template.md](../../templates/script_patterns.template.md) 的 Pattern 11/12 示例）：

```markdown
### Pattern N（来自 [视频简称]，单样本待验证）

**现象**：[Phase 4b 描述]

**原理**：[为什么有效——基于这一次观察的猜测]

**触发条件**：[何时该用]

**待验证**：需要 ≥2 样本支持才能升正式 pattern。
```

跨样本 pattern 升正式：扫描"新发现的 Pattern"段，看是否有 ≥2 样本支持同一现象 → 升到核心 pattern 库 + 删 "待验证" 标记。

如用户在 Phase 4b 全否（"no"）→ 跳过 6b，rubric_notes.md 仍照写。

### Phase 7: 检测 bump 触发

读 `.cheat-state.json` 的 `consecutive_directional_errors` 字段，按本次复盘判定向更新：
- 本次预测高估（实绩 < 中枢 -25%） → push `["high"]` + 记录 deviation_magnitude（如 0.5x / 0.3x）
- 本次预测低估（实绩 > 中枢 +25%） → push `["low"]` + 记录 deviation_magnitude
- 在 ±25% 内 → 不 push

**Claude 判断是否提议 bump**（不是固定门槛）：

```
判断维度：
1. 连续同向次数（参考默认：≥3）
2. 单次偏差幅度（参考默认：>2x 或 <0.5x 算极端）
3. 偏差是否能解释为单一维度漏判（如 ER 或 SR 一致偏离）
4. 用户是否在复盘里反复提到同一现象

任一足够强 → 提议 bump：
- 3 次连续同向，每次都中等偏差 → 提议
- 1 次极端偏差（如 ≥10x），即使没连续 → 提议（"一次性强信号"）
- 2 次同向 + 评论区出现一致的反向证据 → 提议（"评论 + 数据双信号"）

不提议的情况：
- 3 次同向但每次都很小（<25%）→ 可能只是噪声
- 偏差跨多个维度无清晰方向 → bump 不知道改什么
```

提议时输出：

```
🚨 检测到 [系统性偏差信号] / [极端单点偏差] 。

[简短描述：连续 N 次 / 1 次极端 / 评论双信号 等]

这可能是 rubric 系统性偏差的信号。建议：
- 跑 /cheat-bump 看是否需要升级公式
- 或先看 /cheat-status 详细分析

注：本次提议是 [default-aligned: 满足 ≥3 同向] / [judgment-driven: 1 次 10x 强偏差]
```

更新 state file：
```json
{
  "calibration_samples": <+1>,
  "pending_retros": [<剔除本次>],
  "last_retro_at": "<ISO>",
  "consecutive_directional_errors": [...]
}
```

## Key Rules

1. **预测段 immutable**。Phase 0 cache + Phase 5 校验是双保险。任何 hash 不一致 → 报错回滚
2. **数据来源必须标注**。`数据来源: manual paste` 或 `数据来源: adapter:douyin-session` 写进复盘段
3. **观察可追溯**。每条新观察引用具体数据点
4. **不在复盘里 bump**。Phase 7 只**提议** bump，实际升级走 `/cheat-bump`——避免一次操作做两件事
5. **早复盘标记**。RETRO_WINDOW_DAYS 不到就复盘 → state file 记 `early_retro: true`，bump 时这种样本权重降级

## Refusals

- 「这条数据已经看过了，但你假装没看，按预测时的盲度做复盘」 → 复盘本来就是看完数据再做的；这个表述本身没有违规，但要确认用户没在 prediction 写之前透露过数据
- 「把预测段的概率分布改一下，让复盘看起来更准」 → 拒绝。原则 #1
- 「跳过观察提炼，直接结束」 → 拒绝。新观察是 rubric 进化的唯一燃料；缺它复盘退化为"看一眼"
- 「直接 bump，不要单独走 /cheat-bump」 → 拒绝。bump 流程有完整的跨模型审 + cleanup pass，retro 是触发器不是执行器

## Integration

- 前置：`/cheat-publish` 已登记 + 时间窗口达到
- 下游：累计 `consecutive_directional_errors` 满 3 → 触发 `/cheat-bump` 提议
- 状态字段更新：`calibration_samples` +1（这是 cheat-status 显示进度的关键）
- pending_retros：剔除本条
- 与 [observation-lifecycle.md](../../shared-references/observation-lifecycle.md) 紧耦合：每次复盘是观察新增的入口
