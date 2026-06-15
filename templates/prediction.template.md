# [作品标题] — 预测日志

> **本模板由 `/cheat-predict` 自动填充**。
> 所有预测都用统一格式（7 个组件 + 复盘段）——前 5 篇和成熟期都一样，区别仅是 header 里的 confidence 等级。
>
> 完整规范见 [shared-references/prediction-anatomy.md](../cheat-on-content/shared-references/prediction-anatomy.md)。
>
> 模板里的示例数据来自 视频分析 项目「停止期待」（[predictions/2026-04-24_ab61ed09_停止期待.md]）。

---

**Article ID**: `<12 位 hash>`  ← e.g. ab61ed09f0a1（对 `scripts/<id>.md` 首次落盘内容做 sha256，取前 12）
**Title**: `<完整标题>`
**Rubric Version**: **`<v0/v1/v2/...>`**
**预测时间**: `<YYYY-MM-DD>`（基于最终稿）
**Script Path**: `scripts/<YYYY-MM-DD>_<id>_<short>.md`
**Script Hash**: `sha256:<12 位>` (predict 时 hash script 内容；cheat-shoot 时再 hash，不一致则复盘段加 integrity warning)
**Target Duration (s)**: `<state.typical_duration_seconds>`  ← e.g. 240 (3-5min)
**Actual Script Length**: `<script.md 实际字数>`  ← e.g. 980 字
**Calibration Samples (at predict time)**: `<state.calibration_samples>`  ← e.g. 3
**Confidence**: `<emoji + 标签>`  ← e.g. 🟡 偏低 (中枢 ±40%，可作为参考之一)。从 calibration_samples 派生，见 state-management.md
**Scored By**: `claude` | `claude+user_override`  ← Claude 自打分；如用户在 review 阶段挑刺改了字段，标 `+user_override`
**User Override**: `<如有覆盖，列出哪些字段被改了+原值与新值>` | `none`
  ← 例：`AB: claude=4 → user=3 (用户认为 '一人公司题没那么普适')` `中枢: claude=60w → user=40w`
  ← 复盘时这个字段帮诊断：用户哪个维度直觉跟 Claude 系统性偏离，被实绩验证 → rubric 可能漏了什么
**预测时数据状态**: **blind**（未看任何 `<平台>` 实际播放数据）
**Prediction Basis**: `pre_shoot`  ← 或 `post_shoot_pre_publish`（v2 段）
**BlindScored By**: `subagent-v1`  ← 或 `main-claude-self` / `mixed`
**BlindScore Disagreement**: `<inline JSON — 每维度一条，见 prediction-anatomy.md>`

---

## 输入快照

**分数 (vN)**: `<dim1=X / dim2=X / ...>` → composite=**`<X.XX>`**

> 示例：ER5 / HP5 / QL5 / NA3 / AB5 / SR2 / SAT4 → composite=**8.24**

**用户改写要点 vs Claude 草稿**（如有）:
- **开头**：[user 砍掉了什么 / 加了什么]
- **砍掉**：[具体段落 / 概念名 / 铺垫]
- **保留**：[关键的金句 / 致谢段 / 主体结构]
- **节奏**：比草稿 [紧 / 松] 约 N%

> 如用户从零写没用 cheat-seed，写"用户原创稿，无 Claude 草稿对照"。

---

## 预测 v1

> ⚠️ **本段是 immutable**——`hooks/prediction-immutability.sh` 会拦截对本段的 Edit。
> 写完不可改。如要重做请创建 `<本文件名>_redo.md`，原文件保留。

**Bucket**: `<X-Yw>`  ← e.g. `30-100w`

**内心概率分布**:
- `<5w` → X%
- `5-30w` → X%
- **`<headline bucket>` → X%**（中枢 ~Xw）
- `>100w` → X%
- `>150w` → X%

> 加起来必须 100%。
> Confidence 低（calibration_samples 少）时**应该更平**（如 30/30/20/15/5），不是更尖（如 5/40/45/8/2）——诚实地反映不确定。

**一句话 reason**:
> [核心驱动因素 + 最强反例约束 + 中枢预测]

---

## 推理因素

| 因素 | 方向 | 置信度 | 说明 |
|---|---|---|---|
| `<dim or feature>` | 强 + / 中 + / 弱 ? / 强 - | 高 / 中 / 低 | [≤30 字理由] |

> 置信度三档：高（强证据 + 多锚点支持）、中（有理由但样本少）、低（凭直觉）。复盘时如果"低置信度"因素被验证 → 直觉强；"高置信度"因素被推翻 → rubric 有 bug。

---

## 锚点对比

| 对照样本 | composite | 实绩 | 异同 |
|---|---|---|---|
| `<样本名>` | `<X.XX>` | `<Yw>` | [关键差异维度] |

> **校准池不够时**（< 2 个 composite ±0.5 邻近样本）：
> 写"校准池只有 N 个样本，无 composite 邻近样本。**锚点对比 N/A**——注意本次预测 confidence 是 🟡 偏低 / 🔴 极低，bucket 中枢仅供参考。"
> **不要直接删这段**——告诉读者锚点为何缺，比静默跳过诚实。

---

## 反事实场景（复盘用）

**如果爆 `>X w`**（X% 预期）:
- [验证什么假设]
- [推翻什么假设]
- [可能新增什么 rubric 维度]

**如果落在 `headline bucket`**（X% 预期）:
- [基准线验证什么]

**如果跌到 `<X w`**（X% 预期）:
- [推翻什么核心判断]

**如果 `<<X w`**（X% 预期）:
- [极端场景的可能解释]

> 实际落在哪个 bucket → 告诉你 rubric 的哪个假设被测试。**不可省略**。

---

## 关键校准假设

[把这次预测当成一次实验，明确写下"如果 X 发生，证明 Y"]

[找一个对照样本（最好是上一篇预测）]

两篇 [同 composite / 邻近 composite]，差异：
- 本篇：[关键维度对比]
- 对照：[关键维度对比]

**我押**：[本篇 vs 对照 = X 倍 / 高 N w]

如果反过来 → [推翻什么 rubric 假设]
如果差距 < N → [rubric 基本 OK / 噪声范围]

> **校准池只有 0-1 篇时**：写"无可对照样本——但仍写下我对这次的核心赌注（即使没有锚点）："然后写 1-2 条这次想测的事。

---

## 复盘

> ⚠️ **以下段落由 `/cheat-retro` 在 T+`RETRO_WINDOW_DAYS` 天后追加**。
> hook 允许追加本段；不允许改预测段任何字符。

（待填——T+RETRO_WINDOW_DAYS 天后跑 `/cheat-retro <对应 video folder>`）
