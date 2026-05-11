# Rubric Memo — Bump 升级档案

> ⚠️ **本文件是 Channel A 内部参考。Channel B（cheat-score-blind sub-agent）**永远不读**本文件**——blind sub-agent 的 hard refusal list 显式包含本文件路径。
>
> 这里累积每次 rubric bump 的完整 Memo：触发观察、证据数据表（含真实样本名 + 实绩）、诊断、跨模型审核结论、已知局限。

---

## 这文件是干嘛的

cheat-bump Phase 5 落地时把升级 Memo 写**这里**，**不写**进 `rubric_notes.md`。

历史上 cheat-bump 把 Memo 全文（含视频名 + 实绩 + 派生证据）写到 `rubric_notes.md`。但 `rubric_notes.md` 是 blind sub-agent 的白名单文件——sub-agent 通过它泄漏实绩数据，本应隔离的盲打分变成"看过实绩的事后解释"。

修复方案：

| 文件 | 内容 | blind 白名单 |
|---|---|---|
| `rubric_notes.md` | 公式 / 维度定义（**通用语言**，不含视频名 / 实绩）/ Bucket 段 / 顶部 metadata | ✅ YES |
| `rubric-memo.md`（本文件） | 升级 Memo 全文（**含**真实视频名 + 真实播放数 + 派生证据） | ❌ NO（硬禁读） |

---

## 写入规则（cheat-bump Phase 5）

- **追加模式**：新 bump 的 Memo **append 到文件末尾**，旧 Memo 不动。按时间倒序倒着读可看 rubric 演化全程
- **每段 Memo 必含 6 个组件**（按 [bump-validation-protocol.md](../shared-references/bump-validation-protocol.md) Step 5 模板）：
  1. 触发观察（哪些观察累积到 ≥3 同向偏差）
  2. 证据数据（校准池重打表 + 排序对照——**含真实视频名 + 实绩**）
  3. 诊断（rubric 哪条假设被推翻）
  4. 新公式（变化的权重 / 维度）
  5. 跨模型审核结论引用（channel C verdict + 理由摘录）
  6. 已知局限（这次 bump 没解决什么）

- **派生证据段**也写**这里**：「派生证据：「视频 X」CC=1 → 实绩 13.7w」这种 named anchor 在 `rubric_notes.md` 里**绝对不允许**，全部沉淀进本文件

---

## 谁读本文件

| Skill | 读？ | 干啥 |
|---|---|---|
| `cheat-bump` Phase 5 | ✅ 写 | append 新 Memo |
| `cheat-retro` | ✅ 读 | 复盘时回看历史 Memo 找 rubric 演化轨迹 |
| `cheat-status` | ✅ 读 | 看板上显示"上次 bump 用了什么证据" |
| **`cheat-score-blind`** | ❌ **硬禁** | refusal_code: `blocked_rubric_memo` |
| `cheat-score` / `cheat-predict` 主 Claude 自估那部分 | 不主动读 | 主对话本身已被污染，再读一遍 Memo 也只是冗余 |

---

## Memo 段格式（cheat-bump 用此格式写）

每次 bump append 一段，格式：

```markdown
---

## v<N> → v<N+1> Memo （bumped at <ISO 8601>）

### 触发观察
（列累积到本次 bump 的 ≥3 同向偏差观察 ID + 一句话总结。引用 rubric_notes.md 的观察 ID）

### 证据数据
**校准池重打表**：

| 样本 | composite (vN) | composite (vN+1) | rank (vN+1) | 实绩 | rank (actual) | delta |
|---|---|---|---|---|---|---|
| 「真实视频名 1」 | 9.41 | 9.55 | 1 | 124.8w | 1 | 0 |
| 「真实视频名 2」 | 8.24 | 9.11 | 2 | 71.1w | 2 | 0 |
| ... | ... | ... | ... | ... | ... | ... |

**派生证据**（如有）：
- 「视频名 X」CC=1 → 实绩 Y w 验证「高抽象密度 → 低 reach」假设
- ...

### 诊断
（rubric vN 的哪条假设被数据推翻；为什么 vN+1 的公式能解释偏差）

### 新公式
旧：`(ER×1.5 + SR×1.5 + HP×1.5 + QL + NA + AB + SAT) / 8.5 × 2.0`
新：`(ER×2.0 + HP×1.5 + MS×1.5 + QL + SR + TS + SAT) / 9.0 × 2.0`

变化：删 NA / AB；加 MS / TS；ER 权重 1.5 → 2.0

### 跨模型审核（channel C）
- 审核模型：qwen-max-2025-XX
- 判定：PASS
- 理由摘录：「...」
- 关键风险：「...」

### 已知局限
（这次 bump 没解决的事；下次 bump 时仍待观察的方向）

```

---

## 例：v0 → v1（首次 bump）

（cheat-init 创建时本文件为空，首次 bump 时在此追加第一段 Memo）

<!-- 后续 bump 在此 append -->
