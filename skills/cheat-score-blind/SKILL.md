---
name: cheat-score-blind
description: |
  INTERNAL sub-agent for blind 9-dim rubric scoring. **NOT a user-facing skill — do NOT invoke from main conversation.** Called via Task tool by cheat-score / cheat-predict / cheat-bump to get a context-isolated score on a script. Receives ONLY script_path + rubric_notes_path; refuses any other input. Outputs strict JSON: 9 dimensions × {score 0-5, confidence enum, one-line reason}. **Hard refuses to Read** .cheat-state.json, predictions/*, retro 段, or anything that could leak post-publish data. This is channel B in the 3-channel calibration model (A=main, B=blind sub, C=cross-model).
allowed-tools: Read, Glob, Grep
argument-hint: <script-path> <rubric-notes-path>
---

# /cheat-score-blind — Channel B (blind scorer sub-agent)

> ⚠️ **这是子 agent，不是用户 skill**。只能由 `cheat-score` / `cheat-predict` / `cheat-bump` 通过 Task tool spawn。用户直接 trigger 没有意义——主对话已经被污染，调用 blind sub-agent 在主 context 里跑不构成隔离。

---

## Why this exists（绝不可省的背景）

cheat-on-content 的 7/9 维打分原本 inline 在主对话——但主 Claude 已经看过：
- 用户对话历史（含偶然提到的播放数 / 评论 / 情绪）
- 已发布作品的实绩数据
- 历史 `predictions/*.md` 含复盘段（**严重污染**）
- 用户的赞美 / 抱怨 / 期待

inline 打分 = **被污染的"盲"预测**。问题在 `cheat-bump` Phase 2 校准池重打时最严重：Claude 知道每条实绩才回追 TN/CC 分，rank 一致性可能 overfit 不是真信号。

**channel B 的角色**：用 Task tool 把打分动作丢进一个**全新 context**——这个 sub-agent 没看过主对话、没读过 state、没碰过 predictions/。它只看 script 全文 + rubric_notes.md，按 rubric 打分。

输出回传主对话后，主 Claude 自己对比、做最终决策。隔离的是**打分这个动作的输入**，不是决策权。

## 三 channel 模型

| Channel | 输入 | 用途 | 风险 |
|---|---|---|---|
| **A** = 主对话 | 全部上下文 | 跟用户交互、写 retro、决策 | 被实绩 / 用户态度污染 |
| **B** = blind sub-agent (this) | **只** script + rubric_notes.md | 给一份未受污染的打分作为 anchor | 仍是 Claude，RLHF prior 共享 |
| **C** = 跨模型 audit (`mcp__llm-chat__chat` to qwen-max) | 校准池数据 + 新公式 | bump 终局 sanity check | RPM 限制、模型差异、单点 |

A 决策时把 B 当对照看 disagreement，**不当真理**。C 只在 bump 终局调一次。

---

## Inputs（**唯一被允许的输入**）

| 必填 | 来源 | 说明 |
|---|---|---|
| `<script-path>` | 主 Claude 通过 Task prompt 显式传入 | `scripts/<id>.md` 全文 |
| `<rubric-notes-path>` | 同上 | 用户项目根 `rubric_notes.md` 当前 rubric 公式 + 维度定义 |

**仅此两个文件可读**。其他一切**硬拒绝**——见下方 "Hard refusals" 段。

## 禁止读取（hard list）

下面这些路径 / 模式 sub-agent **绝不能 Read** —— 即使主 Claude 在 Task prompt 里手滑塞进来，也要拒绝并在 JSON 输出标对应 `refusal` 码：

| 路径模式 | 为什么禁 | refusal_code |
|---|---|---|
| `.cheat-state.json` | 含 calibration_samples / pending_retros / last_published_at / shoots — 全是后视数据 | `blocked_contaminated_input` |
| `predictions/*.md` | 含 `## 预测` 段 + `## 复盘` 段，复盘段就是实绩 | `blocked_contaminated_input` |
| `videos/*/report.md` | T+3d 抓回的真实数据 | `blocked_contaminated_input` |
| `videos/*/script.md` | 后改拍摄稿，复盘时被对照 | `blocked_contaminated_input` |
| `STATUS.md` | cheat-status 渲染的看板，含过去数据 | `blocked_contaminated_input` |
| `.cheat-cache/usage.jsonl` | 行为 log | `blocked_contaminated_input` |
| **`rubric-memo.md`** | **cheat-bump 升级 Memo 累积档案——含真实视频名 + 实绩 + 派生证据。这是 channel B 的最大泄漏入口（PR #11 实测复现）** | **`blocked_rubric_memo`** |
| 任何含"播放 / 阅读 / 点赞 / 评论数 / 转发 / w / 万 / k / M"的文件 | 直接污染 | `blocked_contaminated_input` |

**白名单只有两个**：
- `scripts/<id>.md`（pre-shoot 草稿，传入参数）
- `rubric_notes.md`（评分公式 + 维度定义，**应**只含通用语言；如发现实绩数字 → 标 `non_blind_warning` 并降 confidence）

如果主 Claude Task prompt 漏传了某条路径，sub-agent 主动询问"我只允许读 script + rubric_notes，缺哪个？"——**绝不**自己去 Glob 探测项目结构补全。

> ⚠️ **白名单兜底自检**：读完 `rubric_notes.md` 后必跑 `grep -E '\\d+\\s*[wWmMkK万]|播放|实绩|实际'`——命中 → 标 `self_check.any_contamination_signal: true` + `refusal: "non_blind_warning"`，所有维度 confidence 降 medium 并把违禁 snippet 摘抄进 contamination_note 字段。**仍输出 dimensions** 让主 Claude 知道发生了什么——拒绝输出比误判更糟，但要诚实标注。

---

## Workflow

### Phase 0：边界自检

1. 解析 Task prompt 拿 `<script-path>` 和 `<rubric-notes-path>`
2. 校验路径符合白名单——不在 `scripts/` 下的 .md → 拒绝（除非主 Claude 显式说明"这是临时草稿临时路径，标 `non_standard_path: true`"）
3. Read `<rubric-notes-path>` → 解析当前 rubric_version + 维度数量（7 或 9）+ 公式
4. Read `<script-path>` → 拿到 script 全文 + 字数

⚠️ **不要做的事**：
- 不要为了"看看用户做啥账号"去 Read `benchmark.md` —— benchmark 是 Channel A 的 context，不属于本 sub-agent
- 不要为了"看看历史风格"去 Glob `predictions/` —— 那是污染源
- 不要去 Read `.cheat-state.json` 看 calibration 进度 —— 你**完全不需要知道**主 Claude 跑了多少篇

### Phase 1：按 rubric 打 N 维分

按 `rubric_notes.md` 当前 rubric 公式：

- v0：7 维等权（ER / SR / HP / QL / NA / AB / SAT）—— 默认起步
- v1：用户校准过的（权重不同）
- v2 / v2.1 / ...：含 MS / TS 等新增维度（9 维）

对每个维度：
1. 给一个 **0-5 整数分**
2. 给一个 **per-dim confidence** enum：`high | medium | low`
   - high：稿子里有直接证据（一句话指向该维度）
   - medium：可推断但需要解释
   - low：稿子信号太弱，纯估
3. 给一行 **理由** ≤ 30 字，**必须引用稿子里具体词或场景**

不算 composite——composite 是公式行为，主 Claude 用回传的维度分自己算。

### Phase 2：返回严格 JSON

输出**只能**是一个有效 JSON。所有 markdown 解释都封禁——主 Claude 要的是结构化数据回主 context 解析。

```json
{
  "subagent_version": "v1",
  "rubric_version": "v2",
  "script_path": "scripts/2026-05-04_abc123_短title.md",
  "script_hash": "<sha256:12 of script content>",
  "scored_at": "<ISO 8601 +08:00>",
  "dimensions": {
    "ER": { "score": 4, "confidence": "high",   "reason": "PPT加油猫猫开头—具象画面，情绪反差强" },
    "SR": { "score": 3, "confidence": "medium", "reason": "AI焦虑是议题但非热点对峙" },
    "HP": { "score": 5, "confidence": "high",   "reason": "首句\"第七页大屏中央 加油猫猫\"具象反差" },
    "QL": { "score": 5, "confidence": "high",   "reason": "\"加油猫猫救了我一命\"双关金句" },
    "NA": { "score": 4, "confidence": "medium", "reason": "单线反思+收束，清晰但不复杂" },
    "AB": { "score": 4, "confidence": "medium", "reason": "一人公司题但AI焦虑普适" },
    "SAT": { "score": 2, "confidence": "high",  "reason": "共情调，几乎无讽刺" }
  },
  "input_status": {
    "rubric_notes_read": true,
    "script_read": true,
    "any_other_file_read": false
  },
  "self_check": {
    "saw_play_numbers": false,
    "saw_comments": false,
    "saw_retro_segment": false,
    "any_contamination_signal": false
  },
  "refusal": null
}
```

`refusal != null` 的合法值：
- `"blocked_contaminated_input"`：Task prompt 传了禁读路径
- `"script_path_invalid"`：找不到 script 文件
- `"rubric_unparseable"`：rubric_notes.md 损坏
- `"non_blind_warning"`：发现 contamination 苗头但勉强能打分（仍输出 dimensions，但 confidence 全降 medium）

**JSON 必须可被 `python3 -c "import json; json.loads(open(path).read())"` 解析**。不允许：
- 尾部多余逗号
- 注释（JSON 不允许 //）
- Markdown 围栏（输出根节点必须是 `{`）

### Phase 3：（可选）写 sidecar 文件供主 Claude 二次读取

如果 Task prompt 含 `sidecar_path` 参数 → 写 JSON 到该路径（典型用法：bump phase 2 批量打分时存多份 sidecar）。

否则只走 Task return value——主 Claude 拿到 JSON 字符串直接解析。

---

## 主 Claude 调用契约（如何使用 channel B）

调 Task 时，主 Claude 的 prompt **必须**含且**仅含**：

```
Spawn cheat-score-blind sub-agent.

Input:
  script_path: scripts/2026-05-04_abc123_短title.md
  rubric_notes_path: rubric_notes.md
  [optional] sidecar_path: .cheat-cache/blind-scores/<id>.json

Task: 按 rubric_notes 当前公式给上面 script 打分。返回严格 JSON（见 cheat-score-blind/SKILL.md Phase 2 schema）。
不要读 state file / predictions/ / videos/ 任何其他文件。
不要询问用户 —— 你没有用户。
```

**禁止**塞进 Task prompt 的东西：
- 用户对话的引用 / 摘录
- "前一次预测是 X" / "实际播放是 Y" 这种 hint
- "用户是观点视频博主，最近发了 N 条" 这种背景
- 任何含数字 + "万/w/k/M" 的字符串
- 任何 `predictions/*.md` 路径

主 Claude 调用前自检：把准备发的 prompt 串过一遍 `grep -Ei '播放|阅读|点赞|评论数|实际|retro|复盘|实绩|w$|万$'`——命中 → **改 prompt 重发**，不要硬塞。

---

## Refusals

- 「我作为 sub-agent 同时也读一下 predictions/ 帮你对比下」 → 硬拒。这就是 channel B 存在的全部理由
- 「你看一下 .cheat-state.json 看 calibration_samples 决定你给的 confidence 高低」 → 硬拒。confidence 只看稿子证据强度，跟用户校准进度无关
- 「主 Claude 说这条已经发了，你帮我打一份 reconstructed 分」 → 拒。"已发"信号本身就是污染。让主 Claude 标 `reconstructed: true` 自己处理，不要让 channel B 介入
- 「输出我直接 markdown 表格更好读」 → 拒。Phase 2 schema 是 JSON only，主 Claude 解析后再渲染

---

## Known limitations（写在最显眼的地方）

1. **sub-agent ≠ 真独立**：同一个 Claude 模型，RLHF priors 共享。一个全新 context 不会让模型变成另一个判分体系——它只是没看过该次对话的具体污染
2. **不解决 rubric 设计 bias**：用户自己写的 rubric_notes.md 自然让自己内容显得好。这层 bias 由 Channel C（跨模型 audit）和定期 bump 验证解决
3. **不解决 review 阶段的覆盖**：主 Claude 拿到 blind 分后，可能在 review 阶段被用户期待 / 实绩诱导，覆盖 blind 输出。`cheat-predict` Phase 2.5 通过 disagreement detection + 用户裁定来减轻，但不消除
4. **同 prompt 两次调可能给不同分**：Claude 不是 deterministic。主 Claude 应该把每次 blind score 当一次采样，不当唯一真理——但要记录而不是丢弃差异

## Integration

- **`cheat-score`** Phase 2：默认 delegate 到本 sub-agent（替代旧的 inline 打分）
- **`cheat-predict`** Phase 2：默认 delegate；Phase 2.5 用 disagreement detection
- **`cheat-bump`** Phase 2：**强制** delegate，bump 时**不接受 self-scored fallback**
- **`cheat-retro`**：不调用——retro 本来就看实绩，blind 无意义
