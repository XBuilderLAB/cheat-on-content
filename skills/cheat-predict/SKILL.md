---
name: cheat-predict
description: 给最终稿写一份 immutable 盲预测日志。这是 cheat-on-content 整个校准循环的核心动作——预测段一旦写完不可改，由 hook 强制。**自动检测**：如目标文件已有 `## 预测` / `## 预测 v1` 段（被 cheat-shoot 调用走 v2 模式），改成 append `## 预测 v2` 而非覆盖。**打分通过 Task tool 委派给 `cheat-score-blind` sub-agent**（context-isolated channel B），主 Claude review 后落盘。触发词："启动预测"/"start prediction"/"给这稿子打分并预测"/"写预测日志"。
argument-hint: <script-path> [— mode: v1|v2] [— prediction-file: <path>] [— skip-blind]
allowed-tools: Bash(*), Read, Write, Edit, Glob, Task
---

# /cheat-predict — AI 主导的盲预测 + 用户 review

**这个工具是"作弊器"——AI 帮你做判断**。所以 cheat-predict 的核心是：
- **Claude 自己**读稿子 + 打 7 维分 + 给 bucket + 概率分布 + 反事实场景
- 用户 **review** 后回 "ok" 接受，或指出哪个维度 / 哪个判断不对
- 默认走快路径：用户直接 ok → 落盘
- 慢路径：用户挑刺某个维度 → Claude 改 → 再 review → 直至确认

不是用户从 7 维分到概率分布全部自己写，那 Claude 只剩"格式化器"——失去工具的核心价值。

**严格遵守 [shared-references/blind-prediction-protocol.md](../../shared-references/blind-prediction-protocol.md)**——见过任何后续数据就不能写预测，只能记 reconstructed。
完整组件清单见 [shared-references/prediction-anatomy.md](../../shared-references/prediction-anatomy.md)。
Confidence 派生表见 [shared-references/state-management.md](../../shared-references/state-management.md)。

## Overview

```
[用户：启动预测 scripts/<id>.md]
  ↓
[Phase 0: blind check 自检]                    ← 触犯就拒绝
  ↓
[Phase 0.7: 模式判定 — v1 (新建) 还是 v2 (append)]
  ↓
[Phase 1: 读 script + rubric + state + 派生 confidence]
  ↓
[Phase 2: **委派 cheat-score-blind sub-agent**（Task tool）拿 9 维盲打 + per-dim confidence]
  ↓
[Phase 2.5: 主 Claude 对 blind 输出做 review — 若任意维度 |delta| ≥ 2 vs 主估，弹给用户裁定]
  ↓
[Phase 3: **Claude 自己**找锚点对比]
  ↓
[Phase 4: **Claude 自己**给 bucket + 概率分布 + 中枢]   ← confidence 低时分布更平
  ↓
[Phase 5: **Claude 自己**写反事实场景 + 关键校准假设]
  ↓
[Phase 5.5: **用户 review**——展示完整草拟版，等用户 "ok" 或挑刺]
  ↓
   ├─ "ok" → Phase 6 落盘
   └─ "X 维度应该 Y 不是 Z" → Claude 改 → 再 review → 循环
  ↓
[Phase 6: 落盘 — v1 写新文件 / v2 append 到现有文件 ## 复盘 之前]
  ↓
[Phase 7: 更新 state.in_progress_session]
```

## Constants

- **SCRIPTS_DIR = scripts/** — 草稿源目录
- **PREDICTION_DIR = predictions/** — 落盘目录
- **BLIND_CHECK = strict** — strict（默认）/ lenient（仅警告，不推荐）—— 跟 [blind-prediction-protocol.md](../../shared-references/blind-prediction-protocol.md) "见过数据"边界相关
- **BLIND_SCORING = on**（默认）/ off —— 是否走 [cheat-score-blind](../cheat-score-blind/SKILL.md) sub-agent。off 等价于 `--skip-blind` flag，标 `last_prediction_self_scored: true` 给 cheat-status 警告
- **DISAGREEMENT_THRESHOLD = 2** —— blind 与主 Claude 自评的单维度差异 |Δ| ≥ 此值 → Phase 2.5 弹用户裁定
- **BUCKET_PRESET = auto** — 自动派生：有 baseline_plays → 按 baseline × {0.3 / 1 / 3 / 10 / 30}；无 baseline → 平台通用默认
- **MIN_ANCHORS = 2** — 锚点对比期望 2 个；不够时显式标"锚点 N/A"段（不删段，不省略）

> 💡 调用时覆盖：`/cheat-predict scripts/<id>.md — BLIND_CHECK: lenient` / `--skip-blind`（都不推荐）

## Inputs

| 必填 | 来源 |
|---|---|
| `<video-folder-path>` 或 `<script-path>` | 用户参数；缺失则询问 |
| `rubric_notes.md` | 用户项目根 |
| `.cheat-state.json` | 状态文件 |
| `predictions/*.md`（可选） | 历史预测，作为锚点 |

### 入参解析（Phase 0.5，在 blind check 之前）

用户给的路径**应该是** `scripts/<date>_<id>_<short>.md`。如不在 scripts/ 下：

| 形态 | 处理 |
|---|---|
| `scripts/<date>_<id>_<short>.md` | 标准路径，直接用 |
| `<id>` 或 `<short>` 简写 | glob `scripts/*_<id>_*.md` 或 `scripts/*<short>*.md` 找匹配 |
| 任意外部 .md 文件（如 `~/Desktop/my-draft.md`） | **警告 + 询问**："建议把稿子放到 scripts/<date>_<id>_<short>.md 让 cheat-on-content 管理。要我帮你 cp 过去并算 id 吗？"用户同意 → 建标准路径再继续 |
| `videos/<id>/` 路径（user 误以为视频文件夹存稿子）| 提示"video folder 是拍后才建的——pre-shoot 草稿在 scripts/。你要 predict 哪份稿子？" |

如 scripts/<id>.md 不存在 → 报错并询问"你想 predict 的稿子在哪？"

## Workflow

### Phase 0: Blind check 自检（**最关键**，触犯立即终止）

按 [blind-prediction-protocol.md](../../shared-references/blind-prediction-protocol.md) 的"子 skill 必须做的检查清单"执行：

1. 询问用户该作品当前发布状态：
   - 未发 → 通过
   - 已发 < `RETRO_WINDOW_DAYS` 天 → 询问"你看过任何后续数据吗（播放/点赞/评论）？"
     - 用户回答"没看过" → 通过，标记 `published_before_prediction: true` + `blind_status: confirmed_no_data_seen`
     - 用户回答含糊 → 视为"已看"，按下一项处理
   - 已发 ≥ `RETRO_WINDOW_DAYS` 天 → **立即拒绝写"预测"**，建议改用 `_redo.md` 路径记 reconstructed retrospective

2. 自检对话历史里是否含播放/阅读/点赞/评论/转发等字眼的实际数字 → 命中则视为已见数据，按上面 strict 模式处理

3. `BLIND_CHECK=lenient` 模式：仅警告 + 强制在文件头标注 `**Reconstructed retrospective — NOT a blind prediction**`，但仍允许继续

通过 → 进入 Phase 0.7。

### Phase 0.7: 模式判定（v1 vs v2）

判定本次是新建预测（v1）还是对既有预测的 v2 追加（拍后改稿场景）。

**显式参数优先**：用户/调用方传 `— mode: v2` + `— prediction-file: <path>` → 直接 v2 模式。

**自动检测**（无显式参数）：
1. 推断目标 prediction 路径：`predictions/<同 scripts/<id> 命名>.md`
2. 读该路径：
   - 不存在 → **v1 模式**，进入 Phase 1
   - 存在但只有空 `## 复盘`（无任何 `## 预测...` 段）→ **v1 模式**（异常状态，覆盖警告 + 进 Phase 1）
   - 存在且含 `## 预测` 或 `## 预测 v1` 段 → **v2 模式**

**v2 模式额外动作**：
- 比较输入 script（最终拍摄稿）与 `## 预测` 段引用的原 `Script Hash`
- 如完全一致（hash 同）→ 警告"稿子没改，是否真要写 v2？"——用户确认才继续；不确认则退出
- 如不同 → 算 diff 概要（行数 / 字数 / 结构变化）→ Phase 5.5 review 时展示给用户
- 标记 `prediction_basis = "post_shoot_pre_publish"`（v1 默认 `pre_shoot`）

### Phase 1: 读最终稿 + rubric + state + 派生 confidence

1. 按 Phase 0.5 解析后的路径，读 `scripts/<id>.md` 全文
2. 计算 `script_hash` = sha256(script 内容)[:12] → header 用
3. 读 `rubric_notes.md`，识别当前公式 + 维度（同 cheat-score Phase 2）
4. 读 `.cheat-state.json` 拿 `rubric_version`、`content_form`、`calibration_samples`、`typical_duration_seconds`、`baseline_plays`
5. **从 `calibration_samples` 派生 confidence 等级**（按 [state-management.md confidence 表](../../shared-references/state-management.md)）→ 后续写入 prediction header
6. 询问用户："这是你打算实际拍摄发布的最终稿吗？还是会再改？"——必须是最终稿
7. 如果稿子字数与 `typical_duration_seconds` 派生范围严重不符（差 >50%）→ 提示用户："这条稿子 N 字，按你设的典型时长（X 分钟）应该是 M-K 字。是临时改了时长，还是稿子需要砍/补？"

### Phase 2: 委派 cheat-score-blind sub-agent 拿盲打分

**BLIND_SCORING=on**（默认）—— 主 Claude 不再 inline 打分。通过 Task tool spawn `cheat-score-blind`，让一个 context-isolated 的 sub-agent 只看 script + rubric_notes.md 给出 N 维分。

详见 [cheat-score-blind/SKILL.md](../cheat-score-blind/SKILL.md) 的"主 Claude 调用契约"段。**Task prompt 必须精简**：

```
Spawn cheat-score-blind sub-agent.

Input:
  script_path: <Phase 0.5 解析出的 scripts/<id>.md>
  rubric_notes_path: rubric_notes.md

Task: 按 rubric_notes 当前公式给上面 script 打分。返回严格 JSON（见 cheat-score-blind SKILL.md Phase 2 schema）。
不要读 state file / predictions/ / videos/ 任何其他文件。
不要询问用户 —— 你没有用户。
```

**调用前自检**：把 Task prompt 串过 `grep -Ei '播放|阅读|点赞|评论数|实际|retro|复盘|实绩|w$|万$'`——命中 → 改 prompt 重发。

**主 Claude 自己也内心估一份**（不发 sub-agent）——纯为 Phase 2.5 disagreement 检测，**不落盘**、**不替代 sub-agent 输出**。这个估值代表"如果我没用 sub-agent，我会打多少"，是 contamination 的客观指标。

**沙盒 escape**：`BLIND_SCORING=off` 或 `--skip-blind` —— 主 Claude 自己打 7 维。state 立刻标 `last_prediction_self_scored: true` + `last_self_scored_at: <ISO>`，cheat-status 持续提示警告。仅用于：
- Task tool 不可用（开发环境 / 离线）
- 用户主动 audit 主 Claude 的 inline 判分能力（极少数）

按当前公式算 composite——**用 sub-agent 回传的 dim 分**，不用主 Claude 自估。

### Phase 2.5: Blind 输出 review + disagreement detection

拿到 sub-agent JSON 后，主 Claude 必做的事：

1. **JSON validity check**：`python3 -c "import json; json.loads(...)"` 应能解析；不能解析 → 主 Claude 重发 Task（最多 3 次重试），仍败 → abort，向用户报告
2. **Contamination check**：`self_check.any_contamination_signal == true` → 警告用户"sub-agent 自报疑似 contamination"，但仍接受打分（confidence 降一档）
3. **Refusal check**：`refusal != null` → 按 [cheat-score-blind/SKILL.md](../cheat-score-blind/SKILL.md) Phase 2 的处理表对应路径
4. **Disagreement detection**（核心）：
   - 主 Claude 内心估一份 N 维分（Phase 2 末尾的"自估"）
   - 对每个维度算 `delta = |主估 - blind|`
   - 任何维度 `delta >= DISAGREEMENT_THRESHOLD`（默认 2） → **弹给用户裁定**

弹裁定 UX：

```
⚠️  blind sub-agent 跟主 Claude 在某些维度差异较大：

| 维度 | blind (sub) | 主 Claude 自估 | delta | sub-agent 理由 |
|---|---|---|---|---|
| ER | 5 | 3 | 2 | "PPT加油猫猫开头—具象画面强" |
| AB | 2 | 4 | 2 | "一人公司视角，受众窄" |

谁更准？
  a) 信 sub-agent（隔离打分，但同 Claude 模型）
  b) 信主 Claude 自估（有更多对话上下文，可能是 contamination）
  c) 我自己定（你直接给分）

回 a / b / c <你的分数>
```

用户选：
- a → 用 sub-agent 全套分进 Phase 3
- b → 用主 Claude 自估全套分（视为有意接受 contamination）→ 强制标 `last_prediction_self_scored: true`
- c → 用户给的分覆盖该维度，其他维度仍走 sub-agent → 记到 `User Override`

**所有 delta** —— 即使全 < THRESHOLD —— 都记录到 prediction header 的 `BlindScore Disagreement` 字段（详见 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md) 组件 1）。delta=0 也要记录。

### Phase 3: 锚点对比

**所有阶段都跑此 phase**——锚点不够时显式标 N/A，不删段。

1. Glob `predictions/*.md`，读每个文件 header（提取 composite、实绩 bucket、duration_seconds）。**注意排除 reconstructed predictions**（标记 "Reconstructed" 的不算锚点）
2. **优先**找同时长样本（`Target Duration (s)` 与本次差 ±20% 内）
3. 在同时长（或全部）池里，找 2-4 个 composite 与本次预测 ±0.5 范围内的样本
4. **如果池子太小**（同时长 < 2 个 + 全部 < 2 个）→ 输出"锚点对比 N/A 段"（参考 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md) 组件 5）—— 仍写这段，告诉读者锚点为何缺
5. 列对照表；如跨时长，每行额外列"时长 vs 本次"列
6. **关键诊断**：如果某个锚点的 composite 几乎相同但实绩差异 ≥3x → 说明 rubric 没捕获关键维度。**在文件里明确标注**作为新观察的种子

> 为什么按时长筛锚点：4 分钟视频 5w 播放 vs 1 分钟视频 5w 播放完全不是一回事——长视频每秒扛了更多注意力损失。跨时长锚点容易得出虚假结论。

### Phase 4: Bucket + 概率分布 + 中枢

**所有阶段都写**——confidence 低时分布**更平**，不是省略。

1. 从 `starter-rubrics/<content_form>.md` 读默认 bucket 边界（除非用户在 rubric_notes.md 自定义了）
2. 选择最可能的 bucket（headline call）
3. **必须**给出所有 bucket 的概率分布——加起来 100%
4. **必须**给出该 bucket 内的"中枢"点估计

**反诚实陷阱**：如果你给一个 bucket 95% 概率，下次预测错了你没法说"我其实不太确定"。**真实的概率分布通常在 headline bucket 是 40-65%**，剩下 ≥35% 散布在邻近 buckets。

### Phase 5: 反事实场景 + 关键校准假设

**所有阶段都写**——校准池小时关键校准假设可能没有合适对照样本，那就写"无可对照样本——仍写下我对这次的核心赌注"+ 1-2 条这次想测的事。

**反事实场景**（4 段，每段对应一个可能的 bucket，写"如果落在这里，意味着什么 rubric 假设被验证 / 推翻"）：参考 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md) 组件 6。

**关键校准假设**（强烈推荐）：
- 找一个对照样本（最好是上一篇预测）
- 明确写"我押本篇 vs 对照 = X 倍"
- 写"如果反过来 / 差距 < N → 哪个 rubric 假设被推翻"

如 `REQUIRE_HYPOTHESIS=required` → 缺失则不允许落盘。

### Phase 5.5: 用户 review（**核心 — 决定写什么进文件**）

Phase 2-5 全部在内存里做完后，**一次性展示完整草拟版**给用户：

```
我的预测草稿（写文件前 review）：

📊 7 维分（v0 / v2 / 等当前 rubric）：
| 维度 | 分 | 理由 |
|---|---|---|
| ER | 5 | "PPT 加油猫猫 + 老板看到 + 大脑空白"——情感重 |
| HP | 5 | 开头"PPT 第七页大屏中央 一只加油猫猫"具体反差强 |
| QL | 5 | "加油猫猫救了我一命"双金句 |
| NA | 4 | 单一时间线 + 反思，清晰但不复杂 |
| AB | 4 | 一人公司题但 AI 焦虑普适 |
| SR | 3 | AI 焦虑是议题但不是热点对峙 |
| SAT | 2 | 共情调性，几乎无讽刺 |
→ composite ≈ 8.00

🎯 押 bucket：30-100w，中枢 ~60w
   概率分布: <5w 5% / 5-30w 22% / **30-100w 50%** / 100-150w 18% / >150w 5%
   confidence: 🟢 中（基于 8 个校准样本，中枢 ±25%）

🔍 锚点对比：
| 对照 | composite | 实绩 | 异同 |
|---|---|---|---|
| ... | ... | ... | ... |

🤔 反事实：
   如果 >100w → 验证 ER 主导假设强化
   如果 30-100w → 基准线 ok
   如果 <30w → 推翻 "AI 焦虑普适"，AB 偏乐观

🎲 关键校准假设：本篇 vs [对照] 押 1.5x

——————————————————————————————

回 "ok" 我直接落盘，
或指出哪些维度 / 判断不对（如 "AB 给 3，太乐观" / "中枢应该 30w 不是 60w"）。
```

用户三种回应：

1. **"ok"** / "可以" / "继续" → 直接 Phase 6 落盘，header 标 `Scored By: claude`
2. **"X 不对，应该 Y"** → Claude 改对应字段（不光改值，要更新 composite + 概率分布等连锁影响），重新展示 → 循环回 Phase 5.5
3. **"全部重做"** → Phase 2-5 重跑（罕见，通常是 Claude 严重误判稿子调性）

**用户挑刺的字段**记录到 prediction header 的 `User Override` 段（Phase 6 写入）：
- 哪个维度 / 哪个数字被覆盖
- AI 原值 vs 用户改后的值

复盘时这个字段帮诊断：
- 用户每次都 ok（claude 一致）→ 没有用户偏见污染
- 用户经常覆盖某维度 → Claude 在该维度系统性偏离用户实际感觉
- 覆盖维度被实绩验证 → 用户直觉准 → rubric 可能漏了什么

**用户挑刺的纪律**：
- 用户**只能改字段值**，不能在 review 阶段塞新理由让 Claude 重写整段——那是把 Claude 当代笔
- 改完 composite / 概率分布 / 锚点不一致 → Claude 自动连锁更新（不是用户算）

### Phase 6: 落盘

#### Phase 6a: v1 模式（新建预测文件）

文件名约定（[blind-prediction-protocol.md](../../shared-references/blind-prediction-protocol.md) 的"文件名约定"段）：
```
predictions/YYYY-MM-DD_<id>_<short-title>.md
```
- `YYYY-MM-DD`：今天日期（预测写下的日期）
- `<id>`：12 位 hash，对稿子全文做 sha256 取前 12 位（稳定 ID，重写不变）
- `<short-title>`：3-8 字，去标点

**第一段标题写 `## 预测 v1`**（不再写裸 `## 预测`——为将来可能的 v2 留 schema 一致性。老用户的 legacy `## 预测` 文件不动，hook 都识别）。

**header 必填字段**：
- `Article ID`（与 scripts/<id>.md 同 id）
- `Script Path`（指向 scripts/<id>.md）
- `Script Hash`（Phase 1 算出的）
- `Calibration Samples` + `Confidence`（从 state 派生）
- `Prediction Basis`：`pre_shoot`（v1 默认）
- `Scored By`：`claude` / `claude+user_override`
- **`BlindScored By`**：`subagent-v1`（Phase 2 默认）/ `main-claude-self`（`--skip-blind` 时） / `mixed`（Phase 2.5 用户裁定 b/c）
- **`BlindScore Disagreement`**：JSON 字段列表，每维度 `{dim, blind, self, delta, decided_as}`，**所有维度必记**（即使 delta=0）
- `User Override`（如有覆盖）：列出哪些字段被用户改了
- 其他见 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md) 组件 1

留一个空的 `## 复盘` 段：
```markdown
## 复盘

（待填——T+RETRO_WINDOW_DAYS 天后跑 /cheat-retro <对应 video folder>）
```

#### Phase 6b: v2 模式（append 到既有文件）

**绝不**用 Write 覆盖文件——会被 immutability hook 拦。用 **Edit** 在 `## 复盘` 之前插入 `## 预测 v2` 段：

```python
# 伪代码
edit_old = "## 复盘\n"   # 单独一行，确保 hook awk 识别为 v1 段的边界
edit_new = """## 预测 v2 (replaces v1; basis=post_shoot_pre_publish)

**Diff vs v1**: 改了 N 行（X→Y%），主要变化：[摘要]
**重判触发**: cheat-shoot 检测稿子改动 ≥30%
**Script Hash (v2)**: <新稿子 hash>

[7 组件 — 与 v1 同 anatomy]

---

## 复盘
"""
```

v1 段**不动**。v2 段头部明确写"replaces v1"——读者一眼知道哪段是有效预测。

cheat-retro 复盘时按"读最后一个 `## 预测 vN`"逻辑，自然取到 v2 算偏差。

#### 共用规则

**所有阶段都用统一完整版格式**（参考 [prediction-anatomy.md](../../shared-references/prediction-anatomy.md) "完整结构总览"）。confidence 低不缩格式，只让 header 标 confidence 等级 + 锚点对比段写"N/A 解释" + 概率分布更平。

写文件**前**自检 7 个组件齐全（缺锚点 / 关键校准假设 → 写"N/A 解释段"，不删段）。

### Phase 7: 更新 state file

更新 `.cheat-state.json`：
```json
{
  "in_progress_session": {
    "type": "prediction",
    "file": "predictions/YYYY-MM-DD_<id>_<short>.md",
    "video_folder": "videos/YYYY-MM-DD_<id>_<short>/",
    "started_at": "<ISO timestamp>",
    "rubric_version": "<v0/v2/...>"
  },
  "last_prediction_self_scored": <true 仅当 --skip-blind / Phase 2.5 选 b>,
  "last_self_scored_at": <ISO 当 last_prediction_self_scored=true 时>
}
```

`video_folder` 为 null 表示用户跑的是裸 .md 文件，没建 video folder。

`in_progress_session` 在 `cheat-publish` 触发时清除。如果用户预测后从未 publish（弃稿），下次 `/cheat-init` 或 `/cheat-status` 检测到陈旧 in_progress 会询问是否清理。

`last_prediction_self_scored`：
- `true` 仅当本次预测走了 `--skip-blind` 或 Phase 2.5 用户选了 b（信主 Claude 自估）
- 一旦 `true` → cheat-status 持续 nag："上次预测没走 blind sub-agent，已 N 天"——直到下次 normal `cheat-predict`（走 sub-agent）触发后才清回 `false`
- `last_self_scored_at` 跟随更新；下次 `cheat-predict` 走 sub-agent → 这两个字段一起被重置

### Phase 8: 控制台总结

**Cold-start-simple 模式**：

```
✅ 预测落盘（cold-start 简化版）：predictions/2026-05-04_a3f2c1d4e5b6_停止期待.md

7 维打分：ER5 / HP5 / QL4 / NA3 / AB5 / SR2 / SAT4
方向押注：比上一篇明显好（ER+HP 双 5）
对比对象：N/A（这是第 1 篇）

⚠️  ## 预测段已 immutable（hook 锁定）。
⚠️  这是 cold-start 期简化版——没有 bucket 数字。前 5 篇都这样。
   第 5 篇复盘后会自动解锁完整预测（bucket / 概率 / 锚点 / 反事实）。

进度：第 N 篇 / 共 5 篇 cold-start 期

下一步：
- 发布后 → "已发布 https://..."
- T+3 天 → "复盘 predictions/2026-05-04_..."
```

**Complete 模式**：

```
✅ 预测落盘：predictions/2026-05-04_a3f2c1d4e5b6_停止期待.md

bucket 押注：30-100w（中枢 50w）
关键校准假设：本篇 vs 谁问你了 = 1.5-2x

⚠️  ## 预测 段已 immutable（hook 锁定）。
⚠️  你不能再向我"透露"这条作品的播放数据，否则下次复盘的盲度声明失效。
   如果你不小心看到了，告诉我——我会在文件里补一个 integrity warning。

下一步：
- 发布后 → "已发布 https://..."
- T+3 天 → "复盘 predictions/2026-05-04_..."
```

## Key Rules

1. **blind check 是硬门槛**。BLIND_CHECK=strict 模式下，触犯即终止，不允许"软处理"。lenient 仅用于演练
2. **整数维度分**。同 cheat-score
3. **概率分布 = 100%**。不允许 95% + 8%；要么诚实给 50% + 30% + 15% + 5%，要么承认不知道
4. **必须有 `## 复盘` 占位空段**——否则 hook 不知道哪里是 immutable 边界
5. **不允许"先写文件再讨论分数"**——文件落盘后预测段就锁了；讨论必须发生在 Phase 2 之后、Phase 6 之前
6. **id 是稿子 hash，不是时间戳**——重写 _redo.md 时 id 不变，便于跨文件追溯

## Refusals

- 「我已经看过播放数据了，但你假装没看到给我做个预测」 → 拒绝。BLIND_CHECK=strict 直接终止
- 「我把预测段先写一版，等数据出来再调」 → 拒绝。这是把 immutable 协议反着用
- 「我改稿了想让你覆盖之前的预测，不要 v2 段」 → 拒绝。v1 是档案，v2 才是当前判断——append 不覆盖。即使你"主观感觉 v1 完全错了"，git history 里 v1 还能查，但工作目录里 v1 必须留
- 「跳过反事实场景，太麻烦」 → 拒绝。反事实是复盘诊断的依据，缺它复盘退化为"准 / 不准"
- 「可不可以只写 bucket，不写概率分布」 → 拒绝。概率分布是逼你诚实的工具
- 「这次先用 lenient 模式，下次再 strict」 → 询问原因。如果是测试 / 演练 → 允许且文件明确标 reconstructed；如果是想偷懒 → 拒绝
- 「sub-agent 太慢，你直接打就行」 → 用 `--skip-blind` flag 显式声明。**不接受**主 Claude 自作主张跳过 sub-agent。flag 触发 state.last_prediction_self_scored=true，cheat-status 持续提示直到下次 normal 调用清除
- 「Phase 2.5 选 b 后我不想标 last_prediction_self_scored=true」 → 拒绝。选 b 等于"我有意接受主 Claude 自评"——必须留下污染追踪轨迹
- 「我是 cold-start 但想跑完整版预测，给我 bucket 数字」 → 拒绝。前 5 篇 bucket 数字是 false precision，给反而误导。等第 5 篇复盘后 cheat-status 会主动提示解锁。如果用户确实想要数字（罕见，自我教育目的）→ 允许但在文件头醒目标 `**Numerical predictions in cold-start are NOT predictive — for self-education only**`

## Integration

- 前置：`/cheat-init` 必须完成 + `rubric_notes.md` 存在
- 上游可选：`/cheat-score` 反复尝试不同稿子版本
- 下游：`/cheat-publish`（发布登记）→ `/cheat-retro`（复盘）→ 累计 ≥ MIN_SAMPLES 后 `/cheat-bump`
- hook 依赖：`hooks/prediction-immutability.sh` 必须已安装在用户 `.claude/settings.json`，否则 immutability 仅靠 SKILL.md 自律——`cheat-status` 会持续提示
