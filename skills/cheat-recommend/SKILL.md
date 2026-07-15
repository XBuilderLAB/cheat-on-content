---
name: cheat-recommend
description: 从 candidates.md 里按当前 rubric 排序推荐 top N 选题，每条带 composite + 一句 rationale + 锚点对比。**candidates 不存在时给引导而非报错**。触发词："推荐选题"/"next topic"/"下一篇做什么"/"recommend topics"/"挑一个选题"。
argument-hint: "[— top: N] [— filter: tier1|all|safe|risky]"
allowed-tools: Read, Glob, Grep
---

# /cheat-recommend — 候选池排序推荐

读 candidates.md → 按 composite 排序 → 输出 top N 推荐，每条带评分细节 + 锚点对比 + 推荐理由。

## Overview

```
[用户：推荐选题]
  ↓
[Phase 0: 检查 candidates.md 存在性]   ← 不存在则引导，不报错
  ↓
[Phase 1: 解析 candidates 列表]
  ↓
[Phase 2: 过滤（tier / 安全性 / 已发过）]
  ↓
[Phase 3: 排序 by composite + 找锚点]
  ↓
[Phase 4: 输出 top N + 每条的 rationale + 锚点对比]
```

## Constants

- **TOP_N = 5** — 默认推荐 top 5
- **STRATEGY = stable+experimental** — 推 ≥2 时按 [cadence-protocol.md](../../shared-references/cadence-protocol.md) 的"1 稳分 + 1 实验性"策略；推 1 时只推 top 稳分
- **POOL_PATH = candidates.md** — 候选池路径
- **EXCLUDE_PUBLISHED = true** — 排除已发布的（与 `predictions/*.md` 去重）
- **EXCLUDE_REJECTED = true** — 排除用户主动跳过的（`tier=skip`）
- **REQUIRE_SCORED = true** — 只推荐已打分的——避免推没读过的素材
- **DUPLICATE_CATEGORY_LOOKBACK** — 派生自 `state.target_publish_cadence_days`：max(3, cadence_days × 3) 天内已发同类目候选不推（避免审美疲劳）

> 💡 调用时覆盖：`/cheat-recommend — top: 3 — filter: safe`

## Inputs

| 必填 | 来源 |
|---|---|
| `candidates.md` | 用户项目根 |
| `predictions/*.md` | 用于去重 |
| `.cheat-state.json` | 当前 rubric_version |

## Workflow

### Phase 0: 候选池存在性检查

读 `candidates.md`：

| 状态 | 处理 |
|---|---|
| 文件不存在 | **不报错**。输出引导：见下方"无候选池引导" |
| 文件存在但空（< 1 个 entry） | 同上 |
| 文件存在且非空 | 进入 Phase 1 |

**无候选池引导**（核心：不让用户第一次遇到 cheat-recommend 时被劝退）：

```
你目前没有候选池（candidates.md 不存在或为空）。

绝大部分人没有候选池——这很正常。四个建立方式，挑一个：

1. 🌱 [推荐] 跑 /cheat-seed
   一次性的种子动作：3 个问题（兴趣 / 调性 / 红线）→ 拉公开热点 + Claude brainstorm
   → 输出 15 候选让你挑 5 → 默认顺带写 5 个 draft。5 分钟搞定。
   
   - 没发过历史的：纯 brainstorm（兴趣 × 热点）
   - 发过历史的（init 时已 import）：brainstorm 会基于"你过去做过什么"给推荐
   
   说："找选题" 或 "seed"

2. 🔥 [日常补充] 用 /cheat-trends 抓 20 条带打分的候选
   说："抓热点" — 从 weibo-hot / zhihu-hot / b站热门 / HN / 你配的源各拉 N 条
   适合已经跑过 /cheat-seed、想日常补充候选池的用户

3. ✍️  手动建：把候选标题贴进 candidates.md，每行一条
   我会自动给每条粗打分

4. 📋 从 Notion / RSS 导入：跑 /cheat-init --mode add-pool 配置 adapter

你也可以跳过候选池，直接给我具体稿子说"启动预测"。

> /cheat-seed vs /cheat-trends 的区别：
> - seed 是种子动作（含 brainstorm + 可选 draft），适合"我从零开始没选题"
> - trends 是日常多 adapter 抓取（不 brainstorm 不写 draft），适合"日常补充候选池"
```

完成引导 → 退出，不继续后续 phase。

### Phase 1: 解析 candidates

按 [candidate-schema.md](../../shared-references/candidate-schema.md) 的"Markdown 表示"格式解析每个 H3 entry：

```markdown
### [tier1] 标题
- **id**: a3f2c1d4e5b6
- **composite (v2)**: 8.47 — ER=4 HP=4 QL=5 NA=3 AB=5 SR=3 SAT=3
- **predicted bucket**: 5-30w
...
```

提取每条的 `id` / `title` / `tier` / `composite` / `dimension_scores` / `note`。

容错：`candidates.md` 格式被用户手改过 → 询问用户 schema，**不要静默忽略不识别的 entry**。

### Phase 2: 过滤

```
1. EXCLUDE_PUBLISHED=true → 扫 predictions/*.md 的 header，提取所有 id；从候选池过滤掉
2. EXCLUDE_REJECTED=true → 过滤 tier=skip
3. REQUIRE_SCORED=true → 过滤 composite=null（未打分的不推荐）
4. filter 参数：
   - tier1: 只保留 tier=tier1
   - all: 不过滤（tier1+2+3）
   - safe: 排除 tier=risky
   - risky: 仅显示 tier=risky（用于"我今天就想发风险议题"）
```

### Phase 2.5: Buffer 颜色覆盖（**最高优先级**）

读 `state.shoots` + `state.target_publish_cadence_days` 算 buffer 颜色（[cadence-protocol.md](../../shared-references/cadence-protocol.md)）：

| Buffer 颜色 | 推荐策略覆盖 |
|---|---|
| 🔴 红 | **只推 top 1 稳分**——不推实验性。回："buffer 已 0/1 篇，下个发布日断更风险高，今天必须拍 ≥1 条稳分。下面是 top 1 稳分（不推实验性）" |
| 🟠 橙 | 标准 1 稳 + 1 实验，但提示"建议优先拍稳分" |
| 🟢 绿 | 标准 1+1（默认） |
| 🔵 蓝 | **拒绝推荐**。回："你 buffer 已 N 条，cadence-protocol 规定积压时暂停拍摄。先发存货 + 复盘。手动覆盖请说 '我就要拍'" |
| 灵活模式 (`target_publish_cadence_days=null`) | 不应用 buffer 覆盖，标准策略 |

### Phase 3: 排序 + 选 1 稳 + 1 实验（按 STRATEGY）

#### 第 1 条（稳分）

1. 按 `composite` 降序排
2. 过滤掉 `tier=risky`（稳分要安全议题）
3. 过滤掉 `category` 与最近 `DUPLICATE_CATEGORY_LOOKBACK` 天已发/已推过的重复（避免审美疲劳）
4. 取 top 1

#### 第 2 条（实验性）

1. 在 candidates.md 中找：
   - 维度组合与最近已发样本**差异最大**（增加校准信息量），或
   - 含明确的 pattern/dimension hypothesis（如 "MS=5 的 A/B 对照"），或
   - tier=risky 但用户主动愿意试（用 `--filter risky` 覆盖）
2. composite 不一定 top——但有"信息价值"
3. 如 candidates 池里没有合适的实验性候选 → 回："候选池里没有明显的实验性样本，给你 2 条稳分"

#### 剩余 (TOP_N - 2) 条

按 composite 降序补满，标 "（备选）"。

#### 锚点

对每条找 1-2 个 composite 接近的**已发布**作品作为锚点（从 `predictions/*.md` 读）。优先**同时长**锚点（按 `state.typical_duration_seconds` ±20%）。

### Phase 4: 输出

```
🎯 候选池推荐（rubric: v2 / buffer: 🟢 绿 / cadence: 隔日更）

📌 第 1 条 — **稳分**（推荐立即拍）：
  **[tier1] [👍 9.18] "为你好"高密体系**
   - 维度：ER=5 HP=5 QL=4 NA=4 AB=5 SR=5 SAT=4
   - 粗预测桶：30-100w（中枢 ~60w）
   - rationale：ER+SR 双 5 顶配，"高密度家庭议题"普适且分享安全
   - 锚点：仓鼠 (composite 9.41, 实绩 124w) — 同走"理论框架+具象样本"路线
   - 风险：议题厚重，不适合连续 2 篇都打这种

🧪 第 2 条 — **实验性**（验证特定假设）：
  **[tier1] [👍 8.71] 哈哈长度**
   - 维度：ER=3 HP=5 QL=5 NA=4 AB=5 SR=4 SAT=5
   - 粗预测桶：30-100w（中枢 ~55w）
   - **测试目标**：v2.1 候选维度 MS+TS 双 5 vs 谁问你了同 ER/HP/QL/SR 但 MS+TS 低 3
   - 信息价值：拍这条能强证据/弱推翻 v2.1 升正
   - 锚点：谁问你了 (composite 8.24, 实绩 11.7w)

（备选 top 3）：
  3. ……
  4. ……
  5. ……

下一步：
- 选稳分 + 实验性各拍 1 条 → 改写 script → "启动预测"
- 只拍 1 条 → 选稳分（buffer 颜色越红，越应该选稳分）
- 想抓更多候选 → 说"抓热点"
- 都不满意 → 说"过滤改 all"看其他 tier 或 "regen"
```

如 buffer 颜色为 🔴：
```
🔴 buffer 警戒：你 buffer 已 0/1 篇，**下个发布日可能断更**。
   按节奏协议，只推 top 1 稳分（不推实验性）：

  **[tier1] [👍 9.18] "为你好"高密体系**
   - ...（同上稳分格式）

今天必须拍这条。挑 5 条候选 → "抓热点"。
```

如 buffer 颜色为 🔵：
```
🔵 buffer 积压：你 buffer 已 N 条，**暂停推荐**。
   按节奏协议，先发存货 + 复盘。
   - 已拍未发：N 条（最早一条 X 天前拍的）
   - 待复盘：N 条
   说 "已发布 ..." 出队，或 "复盘" 处理待复盘项。
   如果你坚持要拍新的，回 "我就要拍"，我会推 top 1 稳分。
```

每条必有：维度评分（让用户能挑战打分）+ 锚点（让用户校准 composite 的可信度）+ rationale（让用户理解推荐逻辑）。**不允许只输出 composite 排序而无解释**——那是黑箱。

## Key Rules

1. **不报错，给引导**。candidates 缺失是默认状态，不是错误
2. **不推未打分的**。REQUIRE_SCORED=true 是诚实门槛——推未读过的素材是占星
3. **必带锚点**。composite 8.47 在不同账号意味不同，锚点把抽象数字 ground 到真实样本
4. **必带 rationale**。一句话——为什么这条比第二条强？
5. **去重 published**。已发过的不推（用户可显式覆盖）

## Refusals

- 「直接给我 composite 最高的，不用解释理由」 → 拒绝。展示评分 + 锚点是发现"打错"的唯一机会
- 「把 candidates.md 里所有 entry 都重新打分一遍」 → 路由到 `/cheat-score` 单条做；批量重打分是 `/cheat-bump` 的一部分，不在 recommend 范围
- 「按预测桶排，不要按 composite」 → 询问理由。bucket 是 composite 的离散化，按 composite 排即按 bucket 排，差异在桶内序——如果用户真想按"押注期望值"排，需要乘以平均播放，那是另一个独立 scoring 维度

## Integration

- 上游：`/cheat-trends` 把外部热点拉进 candidates.md → recommend 自动看到
- 下游：用户挑一条后写稿 → `/cheat-predict`（candidate 的粗 composite 不进入 prediction，prediction 重新打）
- 与 `/cheat-status` 协调：status 显示 "candidates 池有 N 条 tier1 未发"，recommend 提供具体推荐
