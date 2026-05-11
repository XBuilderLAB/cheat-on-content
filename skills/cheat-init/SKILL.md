---
name: cheat-init
description: cheat-on-content 的首次 onboarding 与脚手架创建器。统一流程——所有用户都走相同 5 阶段闭环，唯一区别是"发过视频的人"会在 init 时多一步：抓取已有视频建立历史 context（用于后续 cheat-seed 给更贴合的选题、更准的 baseline）。触发词："初始化"/"init"/"首次使用"/"我是新用户"/"setup cheat-on-content"。**必须在用户第一次会话执行；其他子 skill 在 .cheat-state.json 不存在时自动路由到此。**
argument-hint: [— form: opinion-video|long-essay|short-text|podcast]
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /cheat-init — 首次 onboarding

让用户从零到能跑第一篇预测，全程 ≤ 5 分钟（没发过历史的）或 ≤ 10 分钟（已发过、要 import 历史的）。

## Overview

```
[用户首次说"初始化"]
  ↓
[Phase 0: 检测当前状态]
  ↓
[Phase 1: 首屏文案 — 适用性 + 期望管理]
  ↓
[Phase 2: 6 个问题（Q1-Q5 都问；Q2 决定是否走 user-history import）]
  ↓
[Phase 2.5: 对标账号 — 强烈建议（cold-start 必须问，已发用户可选）]
  ↓
[Phase 3: 创建脚手架（含 scripts/ + videos/ + samples/ 空目录 + 模板文件含 benchmark.md）]
  ↓
[Phase 3.5: user-history import 流程（仅 Q2=有发过历史 + 用户同意）]
  ↓
[Phase 4: 测试 hook 是否生效]
  ↓
[Phase 5: 给"下一步该说什么"清单]
```

## Constants

- **DEFAULT_RETRO_WINDOW_DAYS = 3**
- **INSTALL_HOOKS = ask** — 默认询问；用户选 `auto` 直接装；`skip` 不装
- **TREND_DEFAULT_SOURCES = ["manual-paste"]**

## Inputs

无。所有信息从 6 个对话问题里收集。

## Workflow

### Phase 0: 检测当前状态

1. 读用户当前工作目录（**用户的 content project，不是 cheat-on-content 自己**）
2. 检查是否已存在 `.cheat-state.json`：
   - 存在 → 提示"项目似乎已初始化（state file 存在）。要重新初始化会覆盖现有配置——确认？" 等用户明确确认才继续
   - 不存在 → 进入 Phase 1
3. 检查是否已存在 `rubric_notes.md` / `predictions/` 等核心文件——存在但 state file 不存在 → 是"半初始化"状态，提示用户并询问"要从现有文件推断状态还是重置？"

### Phase 1: 首屏直白告知期望（含适用性验证）

向用户输出（一字不漏，不要软化）：

```
🎯 Cheat on Content / 网红外挂 — 初始化

你的下一条内容已经在改写 3 个月后的你。
规律是客观存在的，区别是你**看见**还是**没看见**。
这套让你看见。

接下来 5-10 分钟我会问你 5-6 个问题搞清楚你做什么、有什么、怎么用。
两件事先说在前面：

1. **早期预测会不准**——前 5 篇精度大概 ±50%，这是数学事实。
   工具用 🔴🟠🟡🟢🔵 标 confidence 等级，不藏数字——
   你自己判断这次能不能信。

2. **强烈建议导对标账号**——5-10 条对标视频，工具立刻有 anchor。
   不然第一批预测基本是占星。后面 Q5 会再问一次。

准备好开始吗？
```

如果用户答"继续"或类似肯定回应 → Phase 2。
不再因为 content_form 拒绝继续——任何形态都允许，只是 `rubric_form_mismatch` 字段标真，cheat-status 后续会持续提示用户"你的形态需要 bump 调权重"。

### Phase 2: 6 个问题（一问一答，**不**批量提问）

**Q1: 内容形态**

> "你的内容更接近哪一种？
> a) **观点视频**（评论 / 时评 / 论说 / 议题讨论 / 个人观点）— 直接匹配内置 rubric
> b) **长文 essay**（公众号 / Substack / Medium）— 可借观点视频 rubric 起步，bump 时调权重
> c) **短文 / thread**（X / 微博 / 即刻）— 同上
> d) **播客 / 视频长内容**（YouTube 长片 / 播客）— 同上
> e) **教程 / 工具教学 / Builder**（教别人怎么用 X 工具 / 怎么做 Y 项目）— 同上
> f) **其他**（游戏 / 美食 / 妆教 / 新闻 / 剧情）— 工作流通用，但 rubric 维度需要调
>      （ER / SR / HP 这套对你形态可能不太预测，需要自己拆出适合的维度）
> g) **混合**"

记录到 `content_form` + `rubric_form_mismatch`。

**Q1 → `content_form` enum 映射**（**必须存 enum 值，不是字母**）：

| 用户答 | `content_form` 写入值 |
|---|---|
| a | `"opinion-video"` |
| b | `"long-essay"` |
| c | `"short-text"` |
| d | `"podcast"` |
| e | `"tutorial-builder"` |
| f | `"other"` |
| g | `"mixed"` |

`rubric_form_mismatch` 派生：
- 选 a → `false`
- 选 b/c/d/e/f/g → `true`，cheat-status 持续提示"你的形态可能需要 bump 调权重"
- **不再有"严重不匹配"档**——所有形态都能跑工作流，只是有的 rubric 需要更激进的 bump

**Q1.5: 典型时长**（仅 Q1=a/d/f 时问）

> "你的视频典型时长？
> a) 30秒-1分钟  b) 1-3分钟  c) 3-5分钟（推荐起步）
> d) 5-10分钟   e) 10分钟以上"

记录到 `typical_duration_seconds`（30 / 90 / 240 / 450 / 900）。

**Q1.6: 发布频率**

> "你打算多久发一篇？
> a) 日更   b) 隔日   c) 每周   d) 灵活 / 不固定（关闭 buffer 监控）"

记录到 `target_publish_cadence_days`（1 / 2 / 7 / null）。

**Q2: 你这个频道发过视频吗？**

> "a) 没发过 — 我会帮你从兴趣 + 热点 brainstorm 5 个候选 + 写 5 份初稿
>  b) 发过 — 不管 1 条还是 100 条，我会帮你抓历史让后续 brainstorm 更贴合你做过什么"

如选 a → state 写 `calibration_samples: 0`，**Phase 3.5 跳过**，直接进入 Phase 4。
如选 b → 进入 **Q2.1**。

**Q2.1: 平台 + 抓取计划**（仅 Q2=b）

> "你内容主要在哪个平台？
> a) 抖音 — 装 douyin-session adapter（Playwright + 扫码登录抖音创作者中心）
> b) YouTube — 装 youtube-data-api adapter（需 API key）
> c) B 站 — bilibili-stat adapter
> d) 其他 / 多平台 — 走 manual paste 模式"

如选 a/b/c → 询问 Q2.2；如选 d → 跳到 Q2.3 manual。

**Q2.2: adapter 安装时机**（仅 Q2.1=a/b/c）

> "现在装 adapter 自动抓取，还是先手动告诉我？
> - 现在装 — 引导你装 Playwright + 扫码 → 抓回最近 N 条数据
> - 等下再装 — 先 manual 模式，state 标 'pending_adapter_setup'，
>            cheat-status 持续提示装"

如选"现在装"→ 走 adapter install 引导（详见各 adapter README）→ 验证抓取可用 → Q2.3。
如选"等下"→ 跳到 Q2.3 manual。

**Q2.3: 抓取范围 / 历史规模**

如 adapter 已装并验证可用：
> "我可以抓你最近多少条作为基础？
> （建议 10-25 条；样本越多 baseline 越准。最多到你账号实际数量）"
→ 用户给数字 N，Phase 3.5 抓取 N 条

如 manual 模式：
> "你大概发过多少条？给个范围就行（比如 '5-10 条' / '20+ 条'），
>  这只用来标 calibration_samples 估值，不用准确。"
→ 用户给一个估值，Phase 3.5 跳过抓取，calibration_samples 写估值

**Q3: 数据回收方式**

> "T+3 天复盘怎么拿数据？
>
> a) 手动粘 — 候补方案。**你必须粘 top 20+ 评论（带赞数）**，不是只粘播放数。
>    评论才是真信号——'她不一样'这种模因爆发只能从评论看出，
>    播放数永远告诉不了你什么内容真的击中了观众。
> b) **[推荐默认]** adapter 自动抓 — 评论 + 数据全要。
>    如果你现在没装 adapter，没关系，state 标 'pending_adapter_setup'，
>    第一次 publish 之前装上就行（cheat-status 会持续提醒装）。
>    装的指引在 adapters/perf-data/<platform>/README.md。"

**Q3 → `data_collection` enum 映射**：

| 用户答 | `data_collection` 写入值 |
|---|---|
| a | `"manual"` |
| b（默认） | `"adapter"` |

默认推荐 b——除非用户明确说 "a 我就要手动"。

**Q4: 候选选题**

> "你现在有候选选题列表吗？（如有外部 markdown / Notion 维护的）
> a) 没有（默认）— 一会儿我帮你 brainstorm，或日常用 /cheat-trends 抓
> b) 有，markdown 列表
> c) 有，Notion / 其他"

**Q4 → `pool_status` enum 映射**：

| 用户答 | `pool_status` 写入值 |
|---|---|
| a（默认） | `"none"` |
| b | `"markdown"` |
| c | `"notion"` |

**Q5: 装几个 hook（默认装，不需要你决定）**

> "Q5：我顺便装几个 hook，回 'yes' 或 'enter' 就装：
>
> 1. **预测锁** — 我们一起做完预测后，文件被锁。你或我都不能改预测段。
>    复盘只能往同一文件下半段追加，不污染上半段判断。
>    （没这个锁，事后看到数据想"修一下当时的预测"几乎是必然的——你或我都会犯）
>
> 2. **SessionStart 自动报告** — 每次开新会话顶部显示 buffer / 待复盘 / 候选 top
>
> 3. **静默使用日志** — 异步记录使用频率，不阻塞，给将来诊断用
>
> 三个一起装。**不装也可以**（回 'no'）但你失去预测锁，校准价值会下降。
>
> 回 yes / no。"

**Q5 → `hooks_installed` 映射**：

| 用户答 | `hooks_installed` 写入值 |
|---|---|
| yes / enter / 默认 | `true`（bool，**不是字符串 `"yes"`**） |
| no | `false` |

默认 yes——除非用户明确说 no。

### Phase 2.5: 对标账号（**所有用户都问**，cold-start 强烈建议）

> 工具早期最重要的信号源是**对标账号**——你 init 完没数据，rubric 等权 v0 等于占星。
> 但如果你能找一个你想做成那样的账号，导入 5-10 条它的高 / 中 / 低样本，工具就有了 anchor。

询问：

```
🎯 对标账号

你能找一个对标账号吗？至少 3 条该账号的视频。

  - 你**完全没发过历史**（Q2=a/b）→ **强烈建议**——rubric 没 anchor 全靠对标。
    不找的话用通用 v0 等权 rubric，前 5 篇精度更差更久
  - 你**已发历史**（Q2=c）→ **可选**——你也可以只用自己历史 calibrate；
    但建议至少导 1 个对标做 sanity check（看你账号是否真的偏离对标方向）

a) 现在找 → 立刻进入 /cheat-learn-from（5-15 分钟，看你材料准备程度）
b) 等下找 → state 标 `benchmark_status: pending`，cheat-status 持续提醒
c) 不找 → state 标 `benchmark_status: none`，用通用 v0 起步

回 a / b / c。
```

行为：
- 选 a → Phase 3 创建脚手架完毕后，**自动 dispatch 到 /cheat-learn-from**（不让用户手动跑——已经在 init 流程里了）。完成后回 init Phase 4
- 选 b → state 标 `benchmark_status: pending` + `benchmark_name: null`
- 选 c → state 标 `benchmark_status: none`

记录到 `benchmark_status` / `benchmark_name`（如 a 选则在 cheat-learn-from 里写入）。

### Phase 3: 创建脚手架（逐项解释）

按顺序创建并**解释每一项的作用**：

1. **`.cheat-state.json`**
   ```
   "正在创建 .cheat-state.json — 各子 skill 共享上下文的地方。
    这次 init 收集的所有答案都会写在这里。"
   ```
   写入（**所有 `<...>` 占位必须查上面 Q 的映射表换成具体 enum 值，绝不直接存字母**）：
   ```json
   {
     "schema_version": "1.3",
     "skill_version": "1.0.0",
     "rubric_version": "v0",
     "content_form": "<查 Q1 映射表，写 enum 字符串如 \"opinion-video\">",
     "typical_duration_seconds": <Q1.5 派生：30/90/240/450/900>,
     "target_publish_cadence_days": <Q1.6 派生：1/2/7/null>,
     "rubric_form_mismatch": <Q1=a→false；其他→true>,
     "benchmark_status": "<Phase 2.5 派生：a→\"imported\"/b→\"pending\"/c→\"none\">",
     "benchmark_name": <imported 则字符串名，否则 null>,
     "benchmark_sample_count": <imported 则数字，否则 0>,
     "baseline_plays": null,
     "calibration_samples": <Q2=a→0；Q2=b→Phase 3.5 import 回填或 Q2.3 估值>,
     "data_collection": "<查 Q3 映射表，写 \"manual\" 或 \"adapter\">",
     "pool_status": "<查 Q4 映射表，写 \"none\"/\"markdown\"/\"notion\">",
     "data_layer": "markdown",
     "hooks_installed": <查 Q5 映射表，写 bool true/false>,
     "enabled_trend_sources": ["manual-paste"],
     "enabled_perf_adapters": <Q2.1=a→[\"douyin-session\"]；b→[\"youtube-data-api\"]；c→[\"bilibili-stat\"]；其他→[]>,
     "last_bump_at": null,
     "last_bump_self_audited": false,
     "last_published_at": null,
     "last_published_file": null,
     "last_retro_at": null,
     "last_trends_run_at": null,
     "last_trends_added_count": 0,
     "last_prediction_self_scored": false,
     "last_self_scored_at": null,
     "consecutive_directional_errors": [],
     "pending_retros": [],
     "shoots": [],
     "in_progress_session": null,
     "initialized_at": "<本地 ISO 8601 含时区，如 \"2026-05-05T20:11:13+08:00\"，**不要用 UTC 的 Z 后缀**>"
   }
   ```

2. **`rubric_notes.md`**
   ```
   "正在创建 rubric_notes.md — 你的评分维度的真实来源。
    用的是 v0 占位 rubric——等权 7 维（每个维度同等重要）。
    
    为什么叫 v0：v0 是没校准前的占位。你的账号自己的真权重要从你
    的数据反推，不是预设。跑完 5 篇有数据的内容后，会自动提议
    升级到「校准 v1」（你的第一个真正校准过的 rubric）。"
   ```
   - 复制 `cheat-on-content/starter-rubrics/<form>-zero.md`（cold-start）或 `<form>.md`（已有数据时仍可参考）

3. **`script_patterns.md`**
   ```
   "正在创建 script_patterns.md — 你的写作 pattern 沉淀（与 rubric 解耦）。
    rubric_notes.md 教 Claude 怎么打分；
    script_patterns.md 教 Claude 怎么写。"
   ```
   - 复制 `cheat-on-content/templates/script_patterns.template.md`

4. **四个目录**：`scripts/` + `predictions/` + `videos/` + `samples/`（都加 `.gitkeep`）
   ```
   "正在创建四个目录：
    
    scripts/      — 拍前的草稿（cheat-seed 写或你写）
    predictions/  — immutable 预测日志（hook 保护）
    videos/       — 拍后的工作目录（cheat-shoot 创建子目录）
    samples/      — 对标账号视频 / 转录（cheat-learn-from 创建子目录）
    
    前三处用同一组 <date>_<id>_<short> 命名相互关联。
    samples/ 按对标账号名分组：samples/<账号名>/<video-id>/。"
   ```

4.5. **`benchmark.md`**（仅 Phase 2.5 选 a/b 时）
   ```
   "正在复制 benchmark.md 占位模板（实际内容由 cheat-learn-from 填）—— 
    这是你的对标账号的中央 reference。
    前期工具的 rubric / pattern / 选题方向感大量从这里推；
    后期 N≥10 后影响淡出，但保留作 sanity check。"
   ```
   - 复制 `cheat-on-content/templates/benchmark.template.md` → `<user-repo>/benchmark.md`
   - **Phase 2.5 选 c 不创建** → benchmark.md 不存在，state 标 `benchmark_status: none`

5. **`WORKFLOW.md`** + **`STATUS.md`**
   - 复制 templates/ 对应文件

6. **如果 Q5=是 → 安装 hooks**
   - 读 `.claude/settings.json`（如不存在则创建空 `{}`）
   - merge 进 `hooks/prediction-immutability.json` 的 `hooks.PreToolUse`
   - merge 进 `hooks/session-start.json` 的 `hooks.SessionStart`
   - merge 进 `hooks/meta-logging.json` 的 hooks（如同时启用）
   - 复制 `prediction-immutability.sh` + `session-start.sh` + `log-event.sh` 到 `.cheat-hooks/`，chmod +x
   - settings.json 里的 command 路径用 `${CLAUDE_PROJECT_DIR}/.cheat-hooks/`

7. **(Pool 选项 c—Notion)** 仅记录到 state file 的 `pool_status: notion`，后续 cheat-trends 调用时再处理

### Phase 3.5: import 流程（仅 Q2=b 且用户同意抓取）

如 Q2.2=现在装 → 走 adapter install + login（详见 [adapters/perf-data/<platform>/README.md](../../adapters/perf-data/)）。

抓取成功后，对每条已发视频：

1. **建 video folder**：`videos/<date>_<id>_<short>/`
   - `<date>` = 视频实际发布日
   - `<id>` = 12 位 hash，对 (title + 平台 ID) 做 sha256
   - `<short>` = 标题前 3-8 字
2. **写 report.md**：从 adapter 抓回的数据（播放 / 点赞 / 评论 / 转发 / top 评论）填入
3. **询问用户原稿**："video 「{标题}」 你保留了原稿吗？"
   - 是 → 用户提供 → 存为 `videos/<id>/script.md`
   - 否 → 标 `script_lost`（仍建 video folder，只是 script.md 缺失）
4. **写 reconstructed prediction**：`predictions/<date>_<id>_<short>.md`
   - header 标 `**Reconstructed retrospective — NOT a blind prediction**`
   - 7 维打分基于 script + 复盘段实绩数据**反向打**——明确这是非校准用途
   - 不计入 calibration_samples（这是导入的历史，不是校准积累）

import 完成后：
- 派生 `baseline_plays` = 抓回视频的播放中位数 → 写入 state file
- 派生 confidence 等级 → 后续 cheat-predict 写预测时直接用
- 输出汇总："已 import N 条历史。最近一条 X w 播放，中位数 Y w，已建 N 个 video folder + reconstructed predictions"

### Phase 4: 测试 hook 是否生效（仅当 Q5=是）

跑一次假的 Edit 拦截测试：
1. 创建临时文件 `predictions/_test_hook.md`，含 `## 预测\n[test]\n## 复盘\n`
2. 尝试 Edit 这个文件的 `## 预测` 段
3. 钩子应 exit 1 阻塞 → 报告"✅ immutability 钩子生效"
4. 删除测试文件
5. SessionStart hook 验证：直接调一次 `bash .cheat-hooks/session-start.sh` → 应输出报告（即使是空的也行）

如果钩子未生效 → **不要假装成功**，明确告诉用户："钩子安装失败，可能是 .claude/settings.json 配置没生效。建议手动检查或重启 Claude Code。"

### Phase 4.5: 如 Phase 2.5 选 a → dispatch 到 /cheat-learn-from

如果用户在 Phase 2.5 选了 a（现在导对标账号）→ **自动触发 /cheat-learn-from**：

```
✅ 脚手架 + hooks 装完。

下面立刻进入 /cheat-learn-from 帮你导入对标账号——
你 init 时选了"现在找"，不让你又开一个会话才跑。

[invoke /cheat-learn-from]
```

cheat-learn-from 完成后回到 init 的 Phase 5。

如 Phase 2.5 选 b/c → 跳过 Phase 4.5，直接 Phase 5。

### Phase 5: 给"下一步该说什么"清单

```
✅ 初始化完成（rubric: v0，calibration_samples: <N>，confidence: <emoji 等级>）

下次你可以直接说这些：

📝 写完一篇稿子 → "打分这篇 scripts/<...>.md"
🎯 准备发布前  → "启动预测 scripts/<...>.md"
🎬 拍完了      → "拍了 scripts/<...>.md" → 建 video folder + buffer +1
🚀 发布后      → "已发布 https://..."
📊 T+3 天      → "复盘 videos/<...>/"
📈 任何时候    → "状态"（看完整看板）

<如果 Q4=没有候选选题:>
🌱 现在跑 /cheat-seed 找选题？
   - 没发过历史的：纯 brainstorm（兴趣 × 热点）
   - 发过历史的（已 import）：brainstorm 会基于你过去做过什么给推荐
   回 "yes, seed" 立刻跑，回 "no" 你自己想。

💡 你的 confidence 是 <当前等级> —— 它会随着你跑更多复盘自动提升。
   不要因为 confidence 低就跳过预测——预测的纪律本身就是工具的核心，
   早期预测的"价值"是数据采集，不是决策。第 5 次复盘后 rubric 第一次校准，
   confidence 会跨入 🟡 偏低；第 10 次后 🟢 中。
```

## Key Rules

1. **不假装成功**：任何步骤失败 → 明确告诉用户哪一步出错。绝不写"✅ 初始化完成"如果实际没完成
2. **不批量提问**：5 个问题一次问一个
3. **不静默 mkdir**：每创建一个文件都解释它的作用
4. **不强推 SQLite**：所有用户给 markdown，提一句"将来到 30 篇会建议升级"就够了
5. **state 字段统一**：删掉 mode / prediction_complexity / bucket_scheme 等枚举字段——单一用 calibration_samples 整数 + confidence 派生
6. **import 失败不阻塞**：Q2=b 但 adapter 装失败 / 抓取失败 → 优雅降级到"标 calibration_samples 估值，不导入历史 video folder"

## Refusals

- 「跳过 Q1-Q5，直接给我创建所有文件」 → 拒绝。问题答案直接影响默认配置（content_form、cadence、hooks）
- 「我已经在别处初始化过了，把那个项目的配置同步过来」 → 慎重。提示用户手动 cp 现有 `.cheat-state.json` 和 `rubric_notes.md`，不自动跨项目同步
- 「不装 hook 但保留 immutability 承诺」 → 允许，state 标 `hooks_installed: false`，cheat-status 持续提示"你的 immutability 是君子协定"

## Integration

- 写完后，主 SKILL.md 的路由就解锁了所有其他子 skill
- `cheat-status` 读 `.cheat-state.json` 的 `calibration_samples` 字段决定显示哪个 confidence 等级
- 如 Q2=b 走了 import → 历史 reconstructed predictions 进 `predictions/` 和 `videos/<...>/`，但**不**计入 calibration_samples（不是真校准样本）
- `/cheat-seed` 读 `predictions/` 的所有历史 reconstructed prediction → brainstorm 时知道"用户过去做过什么"

## State 字段写入清单

| 字段 | 写入时机 | 来源 |
|---|---|---|
| `schema_version` | Phase 3 | 硬编码 "1.1" |
| `skill_version` | Phase 3 | 硬编码 "1.0.0" |
| `rubric_version` | Phase 3 | "v0" |
| `content_form` | Phase 3 | Q1 → 查映射表换 enum 值（**不是字母**） |
| `typical_duration_seconds` | Phase 3 | Q1.5 派生 |
| `target_publish_cadence_days` | Phase 3 | Q1.6 派生 |
| `rubric_form_mismatch` | Phase 3 | Q1≠a → true |
| `benchmark_status` | Phase 3 / 2.5 | Q2.5 答案派生 |
| `benchmark_name` | Phase 3 / 2.5 | Q2.5 用户提供 |
| `benchmark_sample_count` | Phase 3 / 2.5 | cheat-learn-from import 后回填 |
| `baseline_plays` | Phase 3.5（如 import 成功） | import 数据中位数；否则 null |
| `calibration_samples` | Phase 3 / Phase 3.5 | Q2=a→0；Q2=b→Q2.3 估值或 import 数 |
| `data_collection` | Phase 3 | Q3 → 查映射表换 enum 值 |
| `pool_status` | Phase 3 | Q4 → 查映射表换 enum 值 |
| `enabled_perf_adapters` | Phase 3 | Q2.1 派生（如 Q2=a 则 `[]`） |
| `hooks_installed` | Phase 3-4 | Q5 → bool（不是字符串） |
| `last_bump_at` / `last_published_at` / `last_published_file` / `last_retro_at` / `last_trends_run_at` | Phase 3 | 全部 `null` |
| `last_bump_self_audited` | Phase 3 | `false` |
| `last_trends_added_count` | Phase 3 | `0` |
| `last_prediction_self_scored` | Phase 3 | `false` |
| `last_self_scored_at` | Phase 3 | `null` |
| `initialized_at` | Phase 3 | now() 本地 ISO 8601，含 `+08:00` 时区，**不要 UTC `Z`** |
