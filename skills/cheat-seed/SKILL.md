---
name: cheat-seed
description: 跟用户对话讨论选题——**默认一次一个**，用户主动给主题或经历，AI 围绕用户的输入深挖、提炼角度、写一份 draft。不是 AI 拿三个开放问题追用户，也不是一次给 5 个候选。触发词："找选题"/"我想做一条 X"/"最近有个想法"/"seed"/"启动种子"。可选 batch 模式：`/cheat-seed --batch 5` 走旧的 brainstorm 5 候选 + 写 5 draft 流程。
argument-hint: [— batch: N] [— sources: <comma-separated>]
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheat-seed — 选题对话（默认）/ 批量 brainstorm（可选）

cheat-seed 的核心是**跟用户讨论选题**，不是机械地 brainstorm。好内容来自用户的真实经历 + 观察 + 情绪——这些是 AI 不可能凭空 brainstorm 出来的。AI 的角色是**听用户讲 → 帮提炼角度 → 写一份 draft**，不是 dump 15 候选让用户挑。

**默认模式**：对话式一次一个。
**Batch 模式**（`--batch N`）：保留旧的 brainstorm N 候选 + 写 N 份 draft 流程，给"完全没想法 + 想批量初始化"的用户。

## 三种 Mode（自动识别）

```
Mode A — 用户主动给主题（**最常见**）：
  用户："/cheat-seed" + 直接说"我想做一条关于 X 的"
       或："/cheat-seed 我最近开会被领导..."
  ↓
  AI 围绕 X / 这件事**深挖**——什么瞬间触发？最让你 [情绪 / 不爽 / 觉得有意思] 的是哪点？
  ↓
  收敛到一个具体角度 → 提议 → 用户认可 → 写 1 份 draft → 完成
  ↓
  问"下一篇？" 或用户说"今天就这样"

Mode B — 用户给方向但不具体：
  用户："最近想做点关于 [职场 / 婚恋 / AI / ...] 的"
  ↓
  AI："[范围] 太广。最近你接触到的具体哪件事让你想做这个方向？"
  ↓
  收敛到 Mode A 的具体经历

Mode C — 用户完全没想法（少见）：
  用户："我不知道做什么" / "帮我想个题"
  ↓
  AI："好，进 brainstorm 模式——先抓热点 + 你之前的兴趣方向，给你 1 个建议"
  ↓
  跑 trend-sources 抓热点 + 读 candidates.md / predictions/ 看用户历史
  ↓
  提议 1 个角度（不是 5 个） → 用户认可 → 写 draft

Batch Mode — 用户显式要批量（`/cheat-seed --batch 5`）：
  按旧版 brainstorm 流程：3 问题 → 15 候选 → 用户挑 → 写 5 draft。
  给"今天想一次性把未来 2 周的选题搞定"的用户。
```

**关键纠正**（与旧版的区别）：
- AI **不主动开放问**——等用户给输入再深挖
- 一次一个选题，不是 5 个
- 默认对话式 + 一次一个，batch 是 escape hatch

## Constants

- **DEFAULT_TREND_SOURCES = ["manual-paste"]** — 仅 Mode C / Mode A 灰色场景 / Batch 用到。用户可在 state 里加 aihot / trendradar-mcp
- **TREND_TOOL_ROUTING** — 按 `content_form` 路由数据源，详见 [shared-references/data-source-routing.md](../../shared-references/data-source-routing.md)
- **MODE_B_MAX_REPROBE_TURNS = 2** — Mode B "为什么" 反问最多 2 轮；超过则转 Mode C
- **MAX_DEEP_DIVE_TURNS = 4** — Mode A 收敛阶段最多 4 轮反问，避免 AI 过度盘问
- **WITH_DRAFT = yes** — 默认确认角度后立刻写 draft；用户可说 "等下，我自己写" 跳过
- **DRAFT_LENGTH** — 派生自 `state.typical_duration_seconds`：30s→100-200字 / 90s→250-500字 / 240s→600-1000字 / 450s→1100-2000字 / 900s→2200+字
- **HUMANIZE_DRAFT = on**（默认）/ off —— 写完 draft 后用 `humanizer` skill 过一遍，去掉 AI 写作 tells（em-dash 滥用 / rule of three / inflated 词汇 / 空泛归因等）。off 时直接出原始 AI draft。**只 humanize 正文，不动 header 的"必须改写"警告**

## Inputs

| 必填 | 来源 |
|---|---|
| `.cheat-state.json` | 读 calibration_samples / typical_duration / cadence |
| `rubric_notes.md` | 读当前 rubric（粗打分用） |
| `script_patterns.md` | 读已有 pattern（写 draft 时按 cheat sheet 选结构） |
| `predictions/*.md`（如有） | 已发历史，brainstorm 时作为 context |

## Workflow

### Phase 0: 前置检查 + 加载所有 context（**核心：3 个 context 来源**）

1. 读 `.cheat-state.json` → 不存在则提示先跑 `/cheat-init`
2. 读 `rubric_notes.md` 拿当前公式（粗打分用）
3. 读 `script_patterns.md`——写 draft 时按 cheat sheet 选结构
4. **读已有 prediction 文件**（含 init 时 import 的 reconstructed）作为 **context 来源 A**（用户自己历史）：
   - 0 个 → A 为空
   - ≥1 个 → A 有内容，提取 (title / 7 维 / 实绩)
5. **读 `benchmark.md`**（如存在）作为 **context 来源 B**（对标账号）：
   - `state.benchmark_status = imported` → B 有内容，提取对标账号的样本主题分布、调性、Pattern
   - `state.benchmark_status = none / pending` → B 为空
6. 检查用户的入参——是否含具体 topic / 经历，决定走 Mode A/B/C/Batch

**brainstorm 时的 context 优先级**（**Claude 判断**——下面是参考默认）：

- **A 主导**（用户自己数据）：当 Claude 判断用户数据已能驱动方向时（参考默认：`calibration_samples ≥ 10`，但 Claude 可以更早——如 N=5 但出现 ≥3 个与 benchmark 明显不一致的强样本）
- **B 主导**（benchmark）：用户数据少 + benchmark 有内容时
- **B 缺席**（benchmark 为空）+ 用户数据少：纯靠用户 input + 抓热点；明确告诉用户"没 benchmark 也没足够自己数据，建议跑 /cheat-learn-from 后再回来 brainstorm"

判断依据**不是死磕样本数**，而是看：
- 用户最近 N 个样本的实绩**是否与 benchmark 的高表现样本类型一致**——一致说明 benchmark 仍有借鉴价值；不一致说明用户已经走自己的路
- 用户的样本**多样性**——3 篇都是同类内容不算成熟；3 篇覆盖不同类目反而比 10 篇同类更可信

### Phase 1: Mode 分流

读用户输入，识别：

**含具体名词 + 情绪 / 经历词**（"我昨天开会..." / "我看到 X 让我..." / "我对 Y 觉得..."）→ **Mode A**（深挖；如话题是时事，Phase 2A.5 询问要不要拉外部数据）

**含方向词但无具体内容**（"想做职场" / "AI 方向" / "婚恋"）→ **Mode B**（单问"为什么想做这个"——用户内省窗口，**不调任何热点工具**）

**显式说没想法**（"不知道做什么" / "帮我想" / "随便给个"）→ **Mode C**（按 [data-source-routing.md](../../shared-references/data-source-routing.md) 调热点工具 + 用户挑 + 回到内省；都不行则走"聊经历"三选项兜底）

**显式 `--batch N`**（用户主动批量）→ **Batch Mode**

**纯 `/cheat-seed` 无附加内容** → **询问入口问题**：

```
你今天想干嘛？

- 有想做的主题 / 经历 → 直接告诉我（"我想做一条 X" / "我最近 X..."）
- 知道大致方向 → 告诉我（"想做职场" / "AI 方向"）→ 我会单问你为啥想做
- 完全没想法 → 说"帮我想"→ 我用 [aihot / trendradar] 拉今天的热点给你看
- 批量搞定 → 说 "batch <N>"

(我不会拿一堆开放问题追你——你给一句话我就开始)
```

注意这是**唯一的开放式问题**——只在用户**纯触发** `/cheat-seed` 时问。如果用户已经在触发词里给了内容（"/cheat-seed 我想做..." 或 "找选题 我最近开会..."），直接进 Mode A/B/C 不再问这一句。

### Phase 2A: Mode A 深挖（用户给了具体 topic / 经历）

**核心原则**：围绕用户给的内容**深挖**，**不要切到别的话题**。

**反问类型（按场景挑）**：

- 触发瞬间："你说 X 这件事，最初是哪个具体瞬间触发你想做的？" / "是什么让你觉得这值得讲一条视频？"
- 情绪锚点："这里面最让你 [生气 / 觉得荒唐 / 觉得有意思] 的是哪个细节？"
- 角度选择："你想说的是 [角度 a：现象批判] 还是 [角度 b：自我反思] 还是 [角度 c：泛化到普遍]？"
- 受众想象："你心里想着是说给哪种人听？她/他听完会怎么想 / 怎么转发？"
- 反对意见探测："如果有人反驳说 [反方观点 X]，你会怎么回？"——逼用户先想清楚立场

**反问纪律**：
- 一次只问 **1 个**问题（不要塞 3 个连珠炮）
- 最多 `MAX_DEEP_DIVE_TURNS` 轮（默认 4）——超过就主动收敛："OK 我感觉够了，帮你提议一个角度试试"
- 用户的回答如果含 emoji / 简短 / 不耐烦 → 立刻收敛，不要逼

**收敛输出**：

```
我感觉这个角度能做：

[一句话立意：50 字以内]

走法：
- 用 [Pattern X 结构]（来自 script_patterns.md）
- 钩子：[具体场景 / 句子]
- 主体：[3 个观察是什么]
- 收尾：[MVP 句方向]

粗打分（v0 等权 7 维）：ER=X HP=X QL=X NA=X AB=X SR=X SAT=X → composite ≈ X.X
Confidence: 🔴 极低 (你才校准 0/N 篇)

要不要让我先写一份 draft？(yes / 换角度 / 我自己写)
```

用户回 yes → Phase 4 写 draft。
用户说"换角度" → 回 Phase 2A 深挖更多。
用户说"我自己写" → 把 candidate 加进 candidates.md 标 tier1，结束。

### Phase 2B: Mode B — 单问"为什么"，触发用户内省

用户给了方向但不具体（"想做职场" / "AI 方向" / "婚恋"）。**这阶段不调任何热点工具**——是用户内省的窗口，外部信息会污染。

只问一个问题，**单刀直入**：

```
为什么想做这个主题？
```

不要问"a/b/c 三种例子"——那是 dump 选项让用户挑，破坏内省。让用户自己组织语言。

**根据用户回答分流**：

| 用户答 | 分类 | 行为 |
|---|---|---|
| 含具体经历 / 个人卡点（"我自己经常加班" / "我看到 X 让我..."） | **真动机** | 转 Mode A 深挖（Phase 2A） |
| 抽象热度归因（"这话题最近热" / "别人都在做" / "听说能涨粉"） | **空动机** | 反问"那你自己对这个话题最有感觉的角度是啥？"——逼出个人 stake；继续空 → 转 Mode C |
| "我也不知道" / "朋友说赚钱" / 模糊推搡 | **真没想法** | 直接转 Mode C |

**反问纪律**：最多 2 轮。第 2 轮还问不出真动机 → 直接转 Mode C，**不要无限挖**。

> 设计意图：Mode B 是"过滤器"，不是"工厂"。用户来这里要么暴露真实动机（→ 进 Mode A）要么暴露自己其实没想法（→ 进 Mode C）。两条都比硬要在 Mode B 里产出选题更好。

### Phase 2C: Mode C — 外部素材 + 用户挑 + 回到内省

用户完全没想法（直接显式说 / 从 Mode B 转过来）。**这是唯一默认调热点工具的入口**。

按 [shared-references/data-source-routing.md](../../shared-references/data-source-routing.md) 的路由规则：

1. **拉外部素材**（按 `content_form` 选 trend source）：
   - `tutorial-builder` / AI 类 → 调 aihot skill
   - `opinion-video` / `long-essay` / `podcast` / `other` → 调 trendradar-mcp（如启用）
   - `mixed` → 两个都调
   - 都不可用 → 走 manual-paste（询问用户："今天看到啥可以拍的？粘几条 URL/标题"）

2. **聊经历兜底**（用户拒绝看外部素材 / 外部素材都不感兴趣）：

   ```
   外部素材你都没感觉，那回到你自己。三个开口，挑一个开始讲：

   a) 你最近真实接触到的某件具体事？（"上周我看到我同事 X..."）
   b) 你最近读到 / 看到的某条让你想吐槽的内容？（"知乎上有个回答..."）
   c) 你长期琢磨的某个 unsolved 困惑？（"我一直没想明白为啥 X..."）

   随便挑一个开始讲。
   ```

3. **拉到外部素材后**，用 rubric 粗筛 + 按 content_form 过滤，留 5 条最契合的：

   ```
   今天这 5 个跟你形态契合：
   1. [标题 A]（来源: trendradar / 微博热搜 / hot_score: 8.5）
   2. [标题 B]（来源: aihot / 模型类 / 精选）
   3. ...

   你哪个最有感觉？没感觉就回 '都没'，我换方向问。
   ```

4. **用户挑了一条 → 回到内省**：

   ```
   OK [标题 X]。你为啥对这条最有感觉？
   是 [angle1] 还是 [angle2] 还是别的？
   ```

   → 用户答 → 转 Mode A 深挖。

5. **用户回 "都没"** → 转回 Mode C 第 2 步的"聊经历兜底"。

**关键**：热点不是"塞 5 候选让用户挑"，是"给材料 + 强制问用户的个人 stake"——AI 不替用户决定哪条最值得做。

### Phase 2A.5: Mode A 灰色场景 — 用户讲了时事话题

Mode A 默认深挖用户经历。但如果**用户讲的本身是时事话题**（产品名 + 时间词 / 人名 + 事件词），按 [data-source-routing.md](../../shared-references/data-source-routing.md) 的"时事判定"规则，**询问**用户要不要拉外部数据作参考：

```
💡 [话题] 是时事——我可以拉一下今天的舆论风向（各平台情绪 + 主要 angles）作参考。

要看吗？回 '看' 我调；回 '不用' 我直接跟你深挖你的角度。
```

用户回 "看" → 调对应 trend source → 把数据 inline 到深挖 context；
用户回 "不用" → 标准 Mode A 深挖，不动外部数据。

**永远不主动调**——用户的 angle 优先于外部数据，避免外部信息**带偏**用户视角。

### Phase 2D: Batch Mode（用户显式 `--batch N`）

**保留旧 brainstorm 流程**：

1. 问 3 个清单问题（兴趣 / 调性 / 红线）—— Batch 模式才问这些
2. 抓热点 + Claude brainstorm 15 候选
3. 用户挑 N
4. 写 N 份 draft 到 scripts/

详见 commit history（旧 cheat-seed 的 Phase 1-3）。这是 escape hatch，不是默认。

### Phase 3: 计算 candidate ID + 落候选池

不管 Mode A/B/C 哪条路径，确认角度后：

1. 算 candidate id：`sha256("seed-" + 立意 + 触发时间)[:12]`
2. 写一行 entry 到 `candidates.md`（按 [candidate-schema.md](../../shared-references/candidate-schema.md) 格式）
3. 标 `tier=tier1` + `read_status=deep_read`（已经讨论过，不是 skim）

### Phase 4: 写 draft

`WITH_DRAFT=yes` → 顺次写到 `scripts/<YYYY-MM-DD>_<id>_<short-title>.md`：

**写 draft 前必读** `script_patterns.md` —— 按"结构选型 cheat sheet"对应用户的 topic 选合适结构。如果文件还在抽象骨架阶段（用户没填几个 pattern），就用 starter rubric 对应的通用框架。

**字数**：按 `DRAFT_LENGTH` 派生（基于 `typical_duration_seconds`）。

**段落版**：每段 100-300 字，**不要写一行一行的字幕格式**——那是剪映拍后自动断的。

格式：

```markdown
# [立意标题]

> ⚠️ **Draft by Claude — 你必须改写后再拍**
>
> 这是脚手架，不是成品。你的语气 / 节奏 / 个人经历无法 AI 生成。
> 改写流程：
> 1. **直接在本文件改写**（同 path：scripts/<...>.md）
>    - 加你的语气、个人经历、真实金句
>    - 砍铺垫、砍模型缩写、砍学术包装
> 2. 改完后跑 `/cheat-predict scripts/<本文件>.md`
> 3. 拍完跑 `/cheat-shoot scripts/<本文件>.md`

**Article ID**: <12 位 hash>
**调性**: [基于讨论得出的，不是清单 Q]
**目标时长**: <state.typical_duration_seconds 转换> 分钟
**目标字数**: <按时长派生>
**结构选型**: [按 script_patterns.md 的 cheat sheet 显式标，如 "metaphor 优先" / "数据反转开场"]
**用到的 patterns**: [编号 + 简短说明]
**讨论种子**: [一句话回顾 deep dive 出来的核心]

---

[draft 正文，段落版]
```

`WITH_DRAFT=no`（用户说"我自己写"）→ 跳过 Phase 4 + Phase 4.5。

### Phase 4.5: humanizer 自检 pass（去 AI 味）

`HUMANIZE_DRAFT=on`（默认）—— draft 写完落盘后，**在展示给用户前**用 `humanizer` skill 过一遍。Claude 自己写的初稿天然带 AI tells（em-dash 滥用 / rule of three / "inflated" 词汇 / 空泛归因 / -ing 浅层分析），这一步把它们清掉，让 draft 是个更干净的起点。

**为什么安全**（不污染校准）：cheat-seed 的 draft 不是被预测/发布的东西——用户改写后、cheat-predict 打分的是**用户最终稿**。humanize 初稿只是给用户更好的起点。

步骤：

1. 检查 `humanizer` skill 是否可用（`~/.claude/skills/humanizer/` 存在）：
   - 不可用 → 跳过 Phase 4.5，在 Phase 5 输出里加一行"（humanizer 未装，draft 是原始 AI 版——`git clone https://github.com/blader/humanizer` 到 ~/.claude/skills/ 可启用自动去 AI 味）"
2. 可用 → 通过 Skill tool 调 `humanizer`，**只传 draft 正文**（`---` 分隔线之后的部分），**绝不传 header**：
   - header 的 `⚠️ Draft by Claude — 你必须改写后再拍` 警告是**有意的脚手架标记**，不是要 humanize 的散文
   - **voice calibration**：如果用户有历史脚本（`videos/*/script.md`）或填过 `script_patterns.md`，把最近 1-2 份作为 humanizer 的 voice 参考样本一起传——让它往"**这个用户的声音**"靠，而不是"通用人声"
3. humanizer 返回去 AI 味的正文 → 用 Edit 替换 draft 文件的正文段（header 不动）
4. 记录 humanizer 报告的"修了哪些 tell"（如 `em-dash 滥用 ×3 / rule of three ×2 / inflated 词汇: "深刻" "本质上"`），Phase 5 输出里展示

**纪律**：
- humanizer 是**去 AI 味**，不是**替用户改写**。它让 draft 不那么像机器写的，但**仍不是用户的声音**——header 的"必须改写"警告依然成立，Phase 5 输出要重申
- 如果 humanizer 把某句改得偏离了 `结构选型` / 用到的 pattern → 以 pattern 为准，那句回滚（pattern 是和用户讨论定的，humanizer 不该推翻）

### Phase 5: 输出"下一步" + 询问继续

```
✅ Draft 写完：scripts/2026-05-04_<id>_<short>.md
🧹 humanizer 过了一遍：修了 em-dash 滥用 ×3 / rule of three ×2 / inflated 词汇 2 处
   （draft 现在不那么"机器味"了——但这仍是脚手架，不是你的声音）

接下来你可以：
- 改写这份 draft（直接在原文件改）—— 加你的语气、经历、真实金句
- 改完跑 "打分这篇 scripts/<...>.md" 看 7 维评分
- 决定要拍 → "启动预测 scripts/<...>.md"

下一篇你想做什么？
（直接告诉我具体经历 / topic，或者说"今天就这样"结束）
```

> humanizer 那行只在 `HUMANIZE_DRAFT=on` 且 skill 可用时出现。未装时换成一行提示如何启用。

用户说"今天就这样" → 结束 cheat-seed。
用户给新 topic → 回 Phase 1 重新分流。

## Key Rules

1. **AI 不主动开放问**——只在用户纯触发 `/cheat-seed` 时问一次入口问题，其他时候**等用户给输入再深挖**
2. **一次一个选题**——默认 Mode A/B/C 都给 1 个建议；用户主动要批量才走 Batch
3. **反问纪律**：一次问 1 个，最多 4 轮，用户不耐烦立刻收敛
4. **深挖围绕用户给的话题**，不要切到别的——你说"开会被领导骂"，AI 不该问"那你最近有没有觉得 AI 让大家..."这种平行话题
5. **写 draft 必须读 script_patterns.md**——按用户已有 pattern 选结构
6. **draft 是脚手架**——header 加醒目警告"必须改写"
7. **humanizer 只去 AI 味，不替用户改写**——Phase 4.5 让 draft 不那么机器味，但它仍不是用户的声音；"必须改写"的警告不因为过了 humanizer 就失效

## Refusals

- 「跳过深挖，直接写 draft」 → 询问"你想直接给主题让我写吗？OK 但 draft 质量可能差——我不知道你的角度。给我一句话立意我就写"
- 「AI 替我决定 topic」 → 拒绝。Mode A/B/C 路径里 AI 永远只**呈现外部素材** + **问用户角度**，不替用户拍板"做哪条"
- 「Mode B 我懒得回答为什么，直接给我 5 个候选吧」 → 拒绝。Mode B 的"为什么"是过滤器——你答不出来就不该用 Mode B 的方向。要么进 Mode A 给具体经历，要么进 Mode C 我帮你找素材
- 「Mode A 时直接帮我拉热点，不问我同意」 → 拒绝。Mode A 用户已经有 angle，未经允许拉外部数据会污染他的视角。详见 [data-source-routing.md](../../shared-references/data-source-routing.md)
- 「一次写 5 个 draft」 → 不在默认流程。用户必须显式 `--batch 5`
- 「我懒得改写，直接拍 AI draft」 → 警告"AI 直接生成的稿子拍出来 ER 偏低，会污染你的校准数据"，但用户坚持也允许（标 `unmodified_ai_draft: true`）

## Integration

- 上游：`/cheat-init` Phase 5 末尾在 `pool_status=none + calibration_samples=0` 时主动询问"现在跑 /cheat-seed？"
- 上游：`/cheat-recommend` 在 candidates 空时引导文案中提及 `/cheat-seed`
- 上游：`/cheat-status` 在 `pool_status=none + 距 init >24h` 时提示"还没拍——跑 /cheat-seed？"
- 下游：用户的 candidate → candidates.md（tier1，已 deep_read）
- 下游：（默认）draft → Phase 4.5 humanizer 去 AI 味 → scripts/<id>.md → 用户改写 → /cheat-predict
- 可选依赖：[`humanizer`](https://github.com/blader/humanizer) skill（MIT，外部项目）。装在 `~/.claude/skills/humanizer/` 时 Phase 4.5 自动启用；未装则优雅跳过。**不打包进 cheat-on-content**——用户自己 clone
- 与 `/cheat-trends` 区别：cheat-seed 是**讨论 + 写 draft**（重 conversation）；cheat-trends 是**多 adapter 抓 + 粗打分**（重 fetch）。两者目的不同，不互相替代。
