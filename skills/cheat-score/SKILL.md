---
name: cheat-score
description: 给单篇稿子打 rubric 分。**只在控制台输出，不写文件，不预测**。触发词："打分这篇 [path]"/"score this [path]"/"给这稿子打分"/"先打分看看"。是 cheat-predict 之前的轻量探索动作。
argument-hint: <draft-path> [— mode: single|team]
allowed-tools: Read, Glob, Grep, Bash(*)
---

# /cheat-score — 单稿打分

打分但**不预测**。用户用它快速看稿子的 composite，决定是否值得进入正式预测流程。支持单 Agent 快速打分与 Agent Teams 多智能体协作评估。

## Overview

```
[用户：打分这篇 draft.md — mode: team]
  ↓
[读 draft.md + rubric_notes.md]
  ↓
[模式判定: single 模式还是 team 模式?]
  ↓
  ├─ single  →  [Claude 单体快速逐维度打分]
  └─ team    →  [Claude 脑内模拟 HS/LS/AM/Manager 专家会商与共识博弈]
  ↓
[计算并渲染 composite 分数矩阵表]
  ↓
[结束 — 不写任何文件]
```

## Constants

- **RUBRIC_PATH = rubric_notes.md** — 当前 rubric 来源
- **OUTPUT_DETAIL = full** — full: 含每维度理由及专家博弈分；compact: 仅分数表
- **DEFAULT_MODE = team** — 默认启用多智能体团队打分

> 💡 调用时覆盖：`/cheat-score draft.md — mode: single`

## Inputs

| 必填 | 来源 |
|---|---|
| `<draft-path>` | 用户作为参数传入；如缺失则在对话里询问 |
| `rubric_notes.md` | 用户项目根 |
| `.cheat-state.json` | 用户项目根（用于读当前 `rubric_version` 与 mode） |

## Workflow

### Step 1：前置检查

1. 读 `.cheat-state.json` → 不存在则提示用户先跑 `/cheat-init`，停止
2. 读 `<draft-path>` → 不存在或无内容 → 报错并停止
3. 读 `rubric_notes.md` 找到当前生效的公式段（一般在"当前评分维度"或"综合分公式"位置）

### Step 2：识别公式与维度

从 `rubric_notes.md` 解析出：
- 当前 rubric_version
- 维度列表与权重
- 归一化常数
- 每个维度的 0-5 含义

如果 `rubric_notes.md` 格式与预期不符 → 询问用户当前公式是哪一行。

### Step 3：打分流程 (单 Agent / Agent Teams)

根据参数 `— mode` 决定打分模式（默认 `team`）：

#### 选项 A：single 模式（单体快速打分）
由 **Claude 单体** 快速打分。对每个维度：
1. 读维度定义 + 0-5 含义，在脑里 anchor 到 0/3/5 样本对照。
2. 给出首个直觉 **整数**，并写一行理由（≤30 字，引用稿件具体文案）。

#### 选项 B：team 模式（Agent Teams 协作打分）

直接由 Claude（我们）在当前会话中扮演 Manager 并分流出三个虚拟子 Agent 进行**合意共识打分**（遵循 `shared-references/agent-teams-protocol.md`），无须配置任何外部 API 密钥：
- **HS-Agent** (Hook & Emotion) 评估 `HP` / `ER`。
- **LS-Agent** (Logic & Structure) 评估 `QL` / `NA` / `SAT` / `LE`。
- **AM-Agent** (Audience & Market) 评估 `AB` / `SR` / `TS`。
每个维度由主审和备审专家独立打分。若两人估分差值 ≥ 2，在 CoT 脑内进行两轮自辩讨论（陈述事实 -> 交叉驳斥与让步），最终由 Manager 裁决。输出中明确呈现每维度的“主审分/备审分”以及冲突辩论过程，最后归一计算。


打分速度纪律（限 single 模式）：
- 每个维度 ≤ 30 秒思考时间。相信第一个整数，不提前查实绩锚点。

输出后用户可以挑刺，Claude 连锁修改并重新展示。

### Step 4：算 composite + 输出

按当前公式算综合分。控制台输出（OUTPUT_DETAIL=full）：

```
📊 [draft.md 短标题] — 打分（rubric: v2）

| 维度 | 分 | 理由 |
|---|---|---|
| ER (情感共鸣)        | 5 | "半夜三点翻聊天记录" 极端具象 |
| HP (钩子强度)        | 5 | IS 句一句锁定受众 |
| QL (金句密度)        | 5 | MVP 句"间歇性希望"独立可传 |
| NA (叙事性)          | 3 | 平铺直叙，弱弧线 |
| AB (受众广度)        | 5 | 暗恋/前任普适 |
| SR (社会议题共振)    | 2 | 纯个人情感，无社会托底 |
| SAT (讽刺深度)       | 4 | 致谢段自指反讽 |

公式：(ER×1.5 + SR×1.5 + HP×1.5 + QL + NA + AB + SAT) / 8.5 × 2.0
composite = (5×1.5 + 2×1.5 + 5×1.5 + 5 + 3 + 5 + 4) / 8.5 × 2.0 = **8.24**

📍 落在 30-100w 桶（基于 starter-rubrics 的 bucket 边界）

下一步建议：
- 如果你已写定最终稿、准备发布 → 说 "启动预测"
- 如果想再改稿子 → 改完再打一次（多次打分不留痕迹）
- 如果想看历史相近 composite 的样本 → 说 "找 composite 8.0-8.5 的锚点"
```

OUTPUT_DETAIL=compact 时仅输出分数表 + composite，不附理由列。

### Step 5：**绝不**做的事

- ❌ 写任何文件（包括 predictions/、rubric_notes.md、candidates.md）
- ❌ 给 bucket 概率分布（那是 cheat-predict 的活）
- ❌ 触发"已发布"或"复盘"逻辑
- ❌ 提议 rubric 升级（即使打分时发现明显异常也只在控制台提示，不动 rubric）

## Key Rules

1. **整数分**。不允许 4.5、3.7。如果犹豫 → 选低值 + 备注
2. **盲打优先**。打分前不读 anchors（当前样本附近 composite 的旧作品的实绩），避免被实绩锚定
3. **理由是诊断工具**。每个维度的 1-30 字理由不是装饰——复盘时用来找出哪个维度判断错了
4. **不写文件**。这是 score 与 predict 的核心区别。score 是探索，predict 是承诺
5. **不算 candidate composite**。candidates.md 里的 composite 字段在 cheat-trends/cheat-recommend 里写——score 只服务"已写好的具体稿子"

## Refusals

- 「打分顺便预测一下」 → 拒绝。请改用 `/cheat-predict`。原因：predict 必须走 blind check + 写 immutable 日志，score 跳过这些
- 「打完分把分数写进 rubric_notes.md 的观察段」 → 拒绝。observation lifecycle 规定观察必须有"实绩 vs 预测"对比，光有打分不构成观察
- 「能不能直接告诉我会不会爆」 → 拒绝。给具体 composite + bucket 的判定要求走 predict 流程；score 只输出当前 rubric 下的机械计算

## Integration

- 是 `cheat-predict` 的前置探索：用户可以反复 score 不同稿子版本，确定一份再 predict
- score 不更新 `.cheat-state.json`——这是无副作用操作
- 如果用户连续 score 同一稿子 ≥3 次 → 控制台温和提示"反复打分会引入决策疲劳，差不多可以决定了"
