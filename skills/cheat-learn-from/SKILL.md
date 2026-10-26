---
name: cheat-learn-from
description: 从对标账号导入 script + 数据 → 拆 pattern + 派生 base rubric 信号 → 写到 benchmark.md / script_patterns.md / rubric_notes.md。**这是工具最早期信号的来源**——cold-start 用户没自己历史时全靠对标，发过历史的用户也建议至少 1 个对标做 sanity check。触发词："学这个账号"/"拆这几个对标视频"/"learn from"/"导入对标账号"/"找对标"。
argument-hint: "<账号名> [— way: a (default) | b] [— append | --replace]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheat-learn-from — 对标账号导入

工具早期最重要的信号源是**对标账号**——你 init 完没数据，rubric 等权 v0 等于占星。但如果你能找一个你想做成那样的账号，导入 5-10 条它的高/中/低样本，工具就有了 anchor。

后期当你自己 calibration_samples ≥ 10 时，benchmark 影响自然减弱——你的真实数据成为主要信号源。但 benchmark.md **不删**，仍是 cheat-seed brainstorm 的 reference frame。

## Overview

```
[用户：学这个账号 / 启动 cheat-learn-from]
  ↓
[Phase 0: 检查 benchmark 状态]
  ↓
[Phase 1: 选 input 方式（Way a 默认）]
  ↓
[Phase 2: 收集材料]
  Way a: 用户粘 N 条 script 文本 + 数据
  Way b: 用 whisper 转录 samples/ 目录里的视频
  ↓
[Phase 3: 询问每条样本的"印象判断"（高/中/低 + 为啥）]
  ↓
[Phase 4: Claude 拆 pattern + 派生 rubric 信号]
  ↓
[Phase 5: 用户 review → 改 → 落盘]
  ↓
[Phase 6: 写 benchmark.md / script_patterns.md / rubric_notes.md]
  ↓
[Phase 7: 更新 state.benchmark_status]
```

## Constants

- **MIN_SAMPLES = 3** — 最少 3 条样本（少于拆不出 pattern）
- **RECOMMENDED_SAMPLES = 5-10** — 推荐区间，平衡信号量 vs 用户工作量
- **MAX_SAMPLES_PER_RUN = 15** — 单次导入上限——再多 Claude context 不够 + 用户也累
- **DEFAULT_WAY = a** — Way a 简单 + 准确，是 default

## Inputs

| 必填 | 来源 |
|---|---|
| `<账号名>` | 用户参数；缺失则询问 |
| `.cheat-state.json` | 状态文件 |
| Way a: 用户粘的 script 文本 + 数据 | 对话 |
| Way b: `samples/<账号名>/*.mp4` 等视频文件 | 用户提前下载好放进去 |

## Workflow

### Phase 0: 检查 benchmark 状态

读 `.cheat-state.json` 的 `benchmark_status`：

| 状态 | 处理 |
|---|---|
| `none` | 首次导入——继续 Phase 1 |
| `pending` | 用户之前答应等下找——继续 Phase 1 |
| `imported` 已有 benchmark | 询问"你已有 benchmark [当前名]，N 条样本。要做什么？  a) 追加新视频到当前 benchmark  b) 替换为新 benchmark  c) 只看不改" |

参数解析：
- `--append` → 追加到现有 benchmark
- `--replace <new-name>` → 用新 benchmark 替换（旧的归档到 benchmark.archived/）
- 没标志 + 已有 benchmark → 走上面询问

### Phase 1: 选 input 方式（**两个独立维度**）

每条样本 = **script** + **数据**。两者怎么拿是独立的——你可以混搭。

#### Phase 1a: script source（怎么拿稿子）

```
script 怎么拿？

a) **粘文本（最简单，推荐）**
   - 你自己整理过 / 用工具提取过——直接粘进对话
   - 工具推荐（按方便程度排）：
   
     抖音 / 小红书：
     - 微信小程序「轻抖」—— 粘视频链接 → 自动提取文案 + 评论。最快
     - 类似工具："视频解析助手" / "短视频文案提取" 等小程序
     - 通常有免费额度，重度使用收费
     
     B 站 / YouTube：
     - 视频页面有"显示字幕/文字记录"按钮（如果 UP 主开了）
     - 第三方：DownSub / SaveSubs / yt-dlp --write-auto-sub
     
     公众号 / Substack：
     - 直接复制网页文字
   
b) **whisper 转录视频文件**
   - 你下载了视频到 samples/<账号名>/<video>/source.mp4
   - 需要装 whisper-cpp + ffmpeg（见 adapters/script-extraction/whisper/README.md）
   - 转录可能有错别字 / 漏字 / 标点不准——准确度比 a 差

c) **跳过 script，只用元数据 + 印象**
   - 你拿不到稿子也懒得用工具
   - 后果：pattern 拆不深（只能看标题 / 数据 / 你的印象），但 rubric 信号还行
   - 适合"先快速搭起来，将来补"

回 a / b / c。
```

#### Phase 1b: data source（怎么拿播放/点赞/评论）

```
数据（播放 / 点赞 / 评论 / 转发）怎么拿？

a) **手填数字（最简单）**
   - 你查一下账号后台或视频页面，告诉我数字
   - 不需要装任何工具

b) **adapter 自动抓（如已配置）**
   - 你已经装了 perf-data adapter（如 douyin-session）
   - 给我视频 URL，工具自己抓数据 + top 评论
   - 评论数据更全（手填只能告诉我数字，adapter 能拿到具体评论文本）

回 a / b。
```

**最常见的组合**：
- 完全零依赖路径：1a + 1b（粘文本 + 手填）—— 5 分钟搞定
- 评论质量优先：1a + 2b（粘文本 + adapter 抓）—— 装了 adapter 就走这个
- 拿不到稿子兜底：1b + 1b（whisper + 手填）

### Phase 2: 收集材料

按 Phase 1a + 1b 的组合走对应路径。

**通用纪律**：每条样本最少要有 (script 或 transcript 或 N/A标记) + 数据 (4 项基础：播放/点赞/评论/转发)。

#### Path A: 粘文本（Phase 1a=a）

```
好。我们一条一条来。最少 3 条，推荐 5-10 条。

第 1 条 script，把整段粘下面（段落版，不要字幕格式）：
```

收到 script → 算 video_id（sha256(script_content)[:12]）→ 进 Phase 2 数据采集。

#### Path B: whisper 转录（Phase 1a=b）

```
先确认 whisper 装了：

[运行 `command -v whisper-cpp` 或 `command -v whisper` 检测]

如果没装：
  ❌ whisper 没装。三选一：
  - brew install whisper-cpp（推荐——快）
  - pip install openai-whisper（Python 慢些）
  - 切回 Path A 自己粘文本（推荐用轻抖等小程序）

装好后：把视频文件放到 samples/<账号名>/<video-name>/source.mp4
（一个视频一个子目录）

放好后告诉我"放好了 N 条"，我转录。
```

用户放好后：
1. Glob `samples/<账号名>/*/source.*` 找视频文件
2. 对每个视频跑 `bash adapters/script-extraction/whisper/run.sh <video> samples/<账号名>/<id>/`
3. 失败项报告但继续其他
4. 进 Phase 2 数据采集

#### Path C: 跳过 script（Phase 1a=c）

直接进 Phase 2 数据采集——告诉用户"没 script 我能拆的 pattern 仅限标题级别 / 你的印象，rubric 信号正常拆"。

#### Phase 2 数据采集（Phase 1b=a 手填 / b adapter）

**如 Phase 1b=a（手填）**：

```
第 1 条数据：告诉我
- 标题
- 播放量
- 点赞
- 评论数（不是评论内容，是数字）
- 转发 / 分享数

格式随意，能识别就行。例如：
  "标题：怎么停止期待
   播放：71w / 点赞 2.4w / 评论 899 / 转发 1.8w"

如果你能再粘 top 5-10 条评论（带赞数）更好——pattern 拆能挖到模因层。
```

**如 Phase 1b=b（adapter）**：

```
你说装了 adapter（如 douyin-session）。给我每条视频的 URL，
我跑 adapter 自动抓数据 + top 评论。

第 1 条 URL：
```

收到 URL → 调对应 adapter → 写数据 + 评论到 samples/<账号名>/<id>/meta.md。

**通用**：继续问第 2 条 / 第 3 条 / ... 用户说"够了"或达到 MAX_SAMPLES_PER_RUN 时进 Phase 3。

### Phase 3: 询问"印象判断"

对每条样本（不管 Way a 或 b），收完数据后**追加问印象**：

```
你看完 / 听完这条视频的印象，算这个账号的：
  a) 高表现样本（代表作 / 你想做成这样的）
  b) 中表现样本（普通水准 / 不上不下）
  c) 低表现样本（不算这个账号的代表 / 你不想做成这样）

为什么？（一句话——这个判断比数据更能告诉我你想做什么风格）
```

记录 (impression_label, impression_reason) 到内存。

> 注意：印象**可以**和数据冲突——比如某条数据高但用户觉得"不算代表作"。这种冲突本身是有用信号，记录下来。

### Phase 4: Claude 拆 pattern + 派生 rubric 信号

阅读所有 (script, 数据, 印象) → 自己分析：

#### 4a. Script patterns

按 script_patterns.md 的 cheat sheet 框架拆：
- 开头钩子：3 种类型分布（场景代入 / IS 戏仿 / 数据反转）
- 主体结构：几段 / 怎么切
- 句式 / 句长 / 节奏：短句还是长句、有没有标志性句式
- emotional 标记 / 双声道
- 致谢段 / 收尾
- 高频词汇 / 词汇风格

输出 N 个具体 pattern（每个引用具体样本作证据）。

#### 4b. Rubric 信号（**仅定性，不给数值权重**）

对每条样本打 7 维分（用通用维度），然后看：
- 高表现样本（按用户印象）共有哪些维度高？
- 低表现样本共有哪些维度低？
- 哪些维度在高/低样本之间无差异（说明不是关键维度）？

输出**定性方向**（不是数值权重）：
- "ER 看起来重要"（3/3 高样本 ER ≥4）
- "SR 看起来不显著"（高低样本 SR 分布无差异）
- "MS 高的样本评论区有明显模因爆发"

### Phase 5: 用户 review

一次性展示所有结果给用户：

```
我从你给的 N 条对标视频拆出：

📝 N 个 script pattern：
  1. **[Pattern 1 名称]**：[一句话描述] → 证据：[样本 X / Y]
  2. ...
  
🎯 Rubric 定性信号：
  - 看起来重要的维度：ER / QL / MS（每个有 N 条高样本支持）
  - 看起来不显著的维度：SR / NA
  - 给的初始建议：你的对标账号是 [情感+金句驱动型] / [数据驱动型] / [类比讲解型] / ...
  - **不直接给数值权重**——5-10 样本拟合容易过拟合，先用作 tier-2 信号
  
🎨 选题方向感：
  - 主题分布大概：[主题 A 40% / 主题 B 30% / ...]
  - 调性：[一句话]

回 "ok" 我落盘，
或指出哪些 pattern / 信号你不认同（"Pattern X 我觉得不准" / "Rubric 信号 Y 错了"）。
```

用户反馈循环：
- "ok" → Phase 6 落盘
- 用户挑刺 → Claude 改 → 重新展示 → 直至确认

### Phase 6: 落盘

#### 6a. benchmark.md

按 [templates/benchmark.template.md] 格式写到 `<user-channel>/benchmark.md`：
- 账号信息（账号名、URL、调性、粉丝量级——用户提供）
- 导入的样本表
- 基础 rubric 派生（仅定性）
- 选题方向感

如 `--append` → 在现有 benchmark.md 的样本表追加新行 + 重新拆 pattern；不重写整个文件。
如 `--replace` → 把现有 benchmark.md 移到 `benchmark.archived/<旧账号名>_<日期>.md`，写新的。

#### 6b. samples/<账号名>/

为每条样本建子目录：
```
samples/<账号名>/<video-id>/
├── source.mp4 (Way b 才有，Way a 没有)
├── transcript.md (从粘文本写 / whisper 转出来)
└── meta.md (标题 / 数据 / 印象 / 印象理由)
```

#### 6c. script_patterns.md

在 `<user-channel>/script_patterns.md` 加新段：

```markdown
## 对标 [账号名] 借鉴（imported on YYYY-MM-DD，N 条样本）

> 这些 pattern 来自对标账号——**Imported, untested on my channel**。
> 实拍验证后（≥2 次跑出 + 复盘确认有效）再去掉这个标记，升入正式 pattern。

### Pattern A: [一句话名]
**来自**: [样本 X]
**描述**: [详细]

### Pattern B: ...
```

#### 6d. rubric_notes.md

在 `<user-channel>/rubric_notes.md` 加 / 更新"benchmark-derived initial signals"段：

```markdown
## Benchmark-derived initial signals

> 来自 benchmark.md 的对标账号 [账号名]（N=N 样本，import on YYYY-MM-DD）。
> **仅定性方向，不直接采纳为数值权重**——5-10 样本拟合容易过拟合。
> 等你自己 N≥5 校准样本后正式 bump 时**再决定**是否调权重。

- 看起来重要的维度: ER / QL / ...
- 看起来不显著的维度: SR / NA / ...
- Claude 给的初始建议: [一句话定性]
```

### Phase 7: 更新 state file

```json
{
  "benchmark_status": "imported",
  "benchmark_name": "<账号名>",
  "benchmark_sample_count": <N>
}
```

## Key Rules

1. **Way a 默认**——简单 + 准确。Way b 仅给"找不到 script 只有视频"的兜底
2. **必须问印象**——纯看 transcript 拆 pattern 容易抓表面，加用户印象才挖到深层
3. **Rubric 信号仅定性**——不直接给数值权重。5-10 样本拟合过拟合
4. **pattern 默认标 untested**——避免污染用户自己的 pattern 库
5. **不直接抓视频**——下载是用户的事，避免 TOS + 反爬
6. **可重复跑**——`--append` 加新视频，`--replace` 换账号
7. **MIN_SAMPLES = 3**：少于 3 拆不出 pattern，拒绝继续

## Refusals

- 「跳过印象判断，直接拆」 → 拒绝。印象是关键 input
- 「我只能给 1 条样本」 → 拒绝。最少 3 条
- 「直接给我数值权重」 → 拒绝。Phase 4 只给定性信号
- 「能不能不写 transcript 文件，只在内存里拆」 → 不行。transcript 持久化是后续 cheat-retro Phase 4b diff 的依据
- 「帮我下载对标视频」 → 拒绝。引导用户用 yt-dlp / BBDown 等工具自己下

## Integration

- 上游：`/cheat-init` Phase 2.5 在 cold-start 用户时**强烈建议**跑 `/cheat-learn-from`；calibration 用户**可选**
- 上游：`/cheat-status` 在 `benchmark_status=pending` + 距 init >24h 时持续提醒
- 下游：`/cheat-seed` brainstorm 时读 benchmark.md → 知道用户对标方向
- 下游：`script_patterns.md` 加新段，cheat-seed 写 draft 时按 pattern 选结构
- 下游：`rubric_notes.md` 加 benchmark-derived signals 段，cheat-bump 时作为参考之一
- N≥10 提示：`cheat-status` 在用户 calibration_samples ≥10 时提示"你已有足够自己数据，benchmark 影响淡出（保留作 sanity check）"

## benchmark 何时淡出

不是死磕样本数，是 **Claude 判断"用户数据信号是否已超过 benchmark"**：

- **默认参考**：calibration_samples ≥ 10 → benchmark 影响淡出
- **可以更早**：N=5 但用户的 (打分, 实绩) 配对里出现 ≥3 条与 benchmark pattern 不一致的——说明你账号已经走出对标的路径
- **可以更晚**：N=15 但用户的样本都很相似（都做同一类内容），benchmark 仍有信号价值

判断条件 + 默认值都在 cheat-status 触发器 #19 / cheat-seed Phase 0 里实现。

**淡出后**：
- cheat-seed brainstorm 仍读 benchmark.md，但**优先级低于用户自己的 predictions/**
- rubric_notes 的 benchmark signals 段标 `**Status: superseded by user data**`，不删但不再主导
- benchmark.md **不删**——保留作 sanity check（看你账号是否真的偏离对标方向太远）

**任何时候用户主动**：跑 `/cheat-learn-from --replace none` 完全解除 benchmark 影响

## 与其他 skill 的区别

| Skill | 用途 |
|---|---|
| `/cheat-learn-from` | **从对标账号**导入 pattern / rubric 信号（一次性 / 偶尔追加） |
| `/cheat-seed` | brainstorm 选题 + 写 draft（读 benchmark.md 作参考） |
| `/cheat-trends` | 抓今天的热点（与 benchmark 无关） |
| `/cheat-bump` | 升级 rubric（用户自己 N≥5 后用真实数据，不直接用 benchmark signals） |
