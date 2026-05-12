# Changelog

All notable changes to cheat-on-content will be documented here.

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### Fixed — cheat-shoot DIFF_METRIC 在口语化场景的 v2 误触发（**BREAKING for v2-trigger-logic**）

**问题**：cheat-shoot Phase 3b 用 line-level unified diff 算 `diff_pct = (added + removed) * 100 / orig_lines`。但**创作者真实场景**——draft 是 markdown 长句（一行 ~50 字），拍摄稿是 whisper 转录的口语化短断句（每行 ~5-10 字）——同样的内容会 inflate diff_pct 到 100-200%，触发本不该的 v2 重判。

**实测复现**（use clone PR pre-fix）：
- draft markdown 63 行 / ~380 字
- 拍摄转录 100 行 / 同 ~380 字
- 内容几乎完全保留（审稿人原句一字不差 + 5 年前反应概念 + 升维段所有金句）
- 唯一新增：1 句 brand 锚定 "全面拥抱 AI"
- **line-level diff_pct = 198%** ⚠️ v2 错误触发
- 语义内容真实 diff ≈ 15-25%

**修复**：拆 metric。
- **DIFF_METRIC=char_levenshtein_normalized**（新默认）—— [tools/diff_pct.py](tools/diff_pct.py) 先 normalize（去 markdown header / 分隔线 / 列表标记 / 装饰标点 / 折叠所有空白），再算 char-level Levenshtein / max(len_a, len_b)
- backend 优先级：`rapidfuzz`（C-backed，~ms 级；需 `pip install rapidfuzz`） → `difflib.SequenceMatcher`（stdlib，永远可用，~10ms 级）
- **V2_TRIGGER_THRESHOLD = 0.30** 保持不动（阈值经验合理）
- legacy line-level 保留为终极 fallback（只在 python3 + tools/diff_pct.py 都不可达时降级）

**测试**：3 fixture × 2 backend = 6 case，全过：

| Case | 内容 | 期望范围 | difflib | rapidfuzz |
|---|---|---|---|---|
| 1 | markdown 长句 vs 转录短断句（内容同） | < 30 | 7 | 12 |
| 2 | 完全不同主题 | ≥ 60 | 88 | 97 |
| 3 | 加 20% outro/CTA | 10-30 | 14 | 25 |

跑 `bash tools/diff_pct_test.sh` 复现。

**已知局限**：
- 历史 v2 prediction 文件保留 line-level 数字作 audit trail——不重新走过去的 prediction
- normalize 是启发式（中文标点）——对其他语言 / 非典型 markdown 可能需调整 regex

### Fixed — `rubric_notes.md` 实绩泄漏漏洞（**BREAKING for blind channel integrity**）

**问题**：PR #11 引入的 cheat-score-blind sub-agent 承诺只读 `scripts/<id>.md` + `rubric_notes.md` 两个文件。但 cheat-bump Phase 5 把升级 Memo（含真实视频名 + 实绩 + 派生证据）写进了 `rubric_notes.md`——sub-agent 通过白名单读到了本不该看的实绩，盲打分变成"看过实绩的事后合理化"。实测复现：5 条已发视频里 2 条 sub-agent 自动标 `any_contamination_signal: true`（refusal=`non_blind_warning`，所有维度 confidence 降 medium）。

**修复**（拆 file）：
- **新增 `rubric-memo.md`**——升级 Memo 累积档案。cheat-bump Phase 5 写**这里**，**不**写 rubric_notes.md。append 模式累积多次 bump
- **`rubric_notes.md` 严格收窄**——只放公式 + 通用语言维度定义 + bucket 边界 + 顶部 metadata 指向 rubric-memo.md。**绝不**含真实视频名 / 实绩 / 派生证据带命名锚
- **`cheat-score-blind` 硬禁读 `rubric-memo.md`**——refusal_code `blocked_rubric_memo`；同时加白名单文件**兜底自检**（grep 命中实绩 pattern → 标 `non_blind_warning`）
- **`cheat-bump` Phase 5 leak guard**——写完 rubric_notes.md 后 grep 自检，命中违禁 pattern → abort + 回滚
- **`shared-references/observation-lifecycle.md` 加约束**——任何 skill 写 rubric_notes.md 都不许含实绩 pattern（防止将来再犯）

**老用户必跑**：v0.x 任何已有 `rubric_notes.md` 含 bump Memo 的项目，git pull 后**必须**跑 `/cheat-migrate` 把 rubric_notes.md 拆分为两份文件。不跑 → blind sub-agent 仍泄漏。详见 [migrations/1.3-to-1.4.md](migrations/1.3-to-1.4.md)。

### Changed — schema 1.3 → 1.4（MINOR but BREAKING for blind channel）

- state 字段**无变化**——`schema_version` bump 仅标识"老用户须跑文件层拆分迁移"
- [migrations/1.3-to-1.4.md](migrations/1.3-to-1.4.md) 7 步标准流程（备份 → 扫描 → 抽离 → 写 rubric-memo.md → 清理 rubric_notes.md → 自检 → bump schema）
- cheat-init, SessionStart hook LATEST_SCHEMA, registry.md 三处同步

### Added — Blind scoring sub-agent（channel B 隔离）

**问题**：cheat-on-content 的 7/9 维打分原本在主对话 inline 完成——但主 Claude 已经看过用户对话、实绩数据、复盘段历史，打分被污染。`/cheat-bump` Phase 2 校准池重打分时尤其严重——rank 一致性可能 overfit 而非真信号。

**改动**：引入 [skills/cheat-score-blind](skills/cheat-score-blind/SKILL.md) 作为 **channel B** 隔离打分 sub-agent。三 channel 模型：
- **A** = 主对话：决策 / 写 retro / 跟用户交互
- **B** = blind sub-agent (新)：只接收 `script_path` + `rubric_notes_path`，硬拒绝读 state file / predictions/ / videos/，输出严格 JSON 9 维分 + per-dim confidence
- **C** = 跨模型 audit（qwen-max via `mcp__llm-chat__chat`，已有）：bump 终局 sanity check

具体落地：
- **`cheat-score` Step 3** 改为 Task tool delegate 到 cheat-score-blind（不再 inline 打分；cheat-score 无 `--skip-blind` 因为是轻量探索）
- **`cheat-predict` Phase 2** 默认 delegate；新 **Phase 2.5** 做 disagreement detection——blind 与主 Claude 自估 |delta| ≥ 2 弹用户裁定（选 a/b/c）；header 新增 `BlindScored By` + `BlindScore Disagreement` 字段（**所有维度必记**，delta=0 也记，作为复盘分析素材）
- **`cheat-predict --skip-blind`** flag 是 escape hatch：触发 `state.last_prediction_self_scored=true` + `last_self_scored_at` 时间戳，cheat-status / SessionStart hook 持续 nag 至下次正常调用清回
- **`cheat-bump` Phase 2** **强制** sub-agent，**不接受任何 fallback**——Task tool 不可用 → abort bump，不接受"自审"；每条 prediction 的 `Re-scored under vN` 行额外标 `blind: true`
- **SessionStart hook** 检测 `last_prediction_self_scored && days_since >= 7` 输出红色警告
- **install.sh / uninstall.sh** 加 `cheat-score-blind` 到 SKILLS 数组（14 个子 skill）

### Changed — schema 1.2 → 1.3（MINOR）

- 新增 `last_prediction_self_scored: bool`（默认 false）+ `last_self_scored_at: ISO 8601 / null`
- [migrations/1.2-to-1.3.md](migrations/1.2-to-1.3.md) 含 4 段标准格式（WHAT/WHY/HOW/Manual fallback）
- 老 state 跑 `/cheat-migrate` 升级；不跑也兼容（skills 用 `state.get(field, default)` 兜底）

### Known limitations（写进 cheat-score-blind/SKILL.md）

1. **sub-agent ≠ 真独立** —— 同 Claude 模型，RLHF priors 共享；新 context 不等于另一个判分体系
2. **不解决 rubric 设计 bias** —— 用户自己写的 rubric 自然让自己内容显得好。这层 bias 由 channel C 跨模型 audit 和定期 bump 验证解决
3. **不解决 review 阶段的覆盖** —— 主 Claude 拿到 blind 分后，可能在 Phase 2.5 被实绩诱导覆盖。disagreement detection + 用户裁定减轻但不消除

### Changed — README / cheat-init voice 重塑（递归宿命感）

- **README tagline 改递归宿命版**："你正在读这段话——这个 skill 预测过了。... 你停下来思考'这是不是真的'——也在它的预测里。" 替代原"凭感觉发是猜，这套让你算"框架
- **新增 🌀 起源段**：创作者本人视频脚本精华（一阶宿命 → 二阶宿命的觉醒）作为 README 中段叙事 hook
- **closing tagline 加 callback**："你看到这一行——也是它预测的"——首尾呼应把读者卡进预测循环
- **cheat-init Phase 1 首屏同步**：从 "做内容本质上就是作弊" 改成 "你的下一条内容已经在改写 3 个月后的你。规律是客观存在的，区别是你看见还是没看见。这套让你看见。"
- **GitHub repo description** 同步递归版

### Changed — 多语言 README 拆分

- `README.md` 现为**英文默认**——国际用户首屏
- `docs/README_CN.md` 为简体中文（原 README 内容 + 宿命感重塑）
- 两份顶部加 language switcher（QuantDinger 风格）
- logo 路径 + 内部链接按相对路径调整

### Added — Star History 图表

两份 README 末尾加 [star-history.com](https://star-history.com) 图表，社区可视化项目热度。

### Changed — 弱化 Claude Code 强调

README 安装段从"### Claude Code"+"### Codex"双标题，改为"默认 + supported agents 列表"——把 skill 包装成跨 agent 的工作流而不是 Claude Code 专属。日常用法段同步换成 "skill-compatible agent" 泛称。

### Added — Terminal-style logo SVG

- `docs/logo.svg`（1.9KB 原生 SVG，无图片资源依赖）
- 终端窗口 + traffic lights + `$ fatesnail` 命令行 + 5 阶段循环 + `// cheat on content` 注释
- README hero 居中嵌入

### Added — cheat-seed Mode 重构 + 双热点工具集成

**问题**：原 Mode B 给"a/b/c 三种例子"让用户讲经历——但同样的话术对**有方向但抽象的用户**（"想做职场"）和**完全没想法的用户**（"帮我想"）一视同仁，前者其实有真动机不需要 AI 列举，后者需要的是外部素材而不是 prompt。

**改动**：

- **Mode B 改成单问"为什么想做这个主题？"** —— 用户内省窗口，**不调任何热点工具**。3 类回答：含具体经历→转 Mode A；空动机→反问最多 2 轮；真没想法→转 Mode C
- **Mode C 整合外部素材**：按 `content_form` 路由热点工具——AI 类形态调 [aihot](adapters/trend-sources/aihot.md)，文化/社会形态调 [trendradar-mcp](adapters/trend-sources/trendradar-mcp.md)，混合两个都调；用户挑一条后**回到内省**问"你为啥对这条最有感觉"，再转 Mode A 深挖
- **Mode A 灰色场景**（用户给了时事话题）：Phase 2A.5 询问"要不要拉外部数据作参考"——**不主动调**，避免外部信息带偏用户视角
- **聊经历三选项移到 Mode C 兜底**：仅当用户拒绝外部素材或外部都不感兴趣时呈现

### Added — 两个一等公民 trend source

- **[aihot](adapters/trend-sources/aihot.md)**（Claude skill）：[aihot.virxact.com](https://aihot.virxact.com) 的中文 AI 行业每日精选，5 类（模型/产品/行业/论文/技巧）。无 auth，curl 公开 API，rate limit 600/min
- **[trendradar-mcp](adapters/trend-sources/trendradar-mcp.md)**（MCP server）：[TrendRadar](https://github.com/sansan0/TrendRadar)（57k stars，GPL-3.0 通过 MCP 调用不构成 linking）。25+ MCP 工具——除 `get_latest_news` 外还有 `analyze_topic_trend`（爆火/衰退判定）、`compare_periods`（周环比）、`analyze_sentiment`

### Added — `shared-references/data-source-routing.md`

热点工具的触发与路由协议——单一来源记录："何时调"（5 个入口的触发矩阵）+ "调哪个"（content_form → adapter 路由表）+ "不调时怎么办"（失败降级链）+ Token 成本意识。

### 哲学保持不变

> 热点工具是"前置素材库"，不是"主菜单"——AI 给材料，用户决定 angle。

cheat-seed 的核心论点"好内容来自用户的真实经历，AI 不凭空 brainstorm"完全保留。新设计只是让"完全没想法"这条 cold-cold-start 路径不再死锁。

### Added — v2 预测重判系统（拍后改稿场景）

- **append-only v2 prediction**：cheat-shoot 检测拍摄稿与 `scripts/<id>.md` 行级 diff ≥ 30%（`V2_TRIGGER_THRESHOLD`）→ 自动调用 `/cheat-predict — mode: v2 — prediction-file: <path>` → 在原 prediction 文件 `## 复盘` 之前 append `## 预测 v2 (replaces v1)` 段。**v1 段绝不修改**（hook 物理强制），v2 才进 cheat-retro 的偏差计算
- **immutability hook awk 升级**：单个 `## 预测` 改为可识别多个 `## 预测 vN` 段（v1 / v2 / 任意 vN 一起锁），同时兼容 v0.1.0 的 legacy 裸 `## 预测` 写法。端到端 5 场景验证通过（编辑 v1 / 编辑 v2 / 编辑 legacy 都 BLOCK；append 新段、改 ## 复盘 都 ALLOW）
- **cheat-predict 加 Phase 0.7 模式判定**：检测目标 prediction 文件已含 `## 预测...` 段 → 自动切 v2 模式（Edit 在 `## 复盘` 边界 append，不 Write 覆盖）
- **cheat-retro 升级**：识别多个 `## 预测 vN`，取最后一段作校准依据；预测段哈希校验扩展为"全部 v? 段合并哈希"，任一被改即报错回滚
- **prediction header 新字段 `Prediction Basis`**：`pre_shoot`（v1 默认）/ `post_shoot_pre_publish`（v2）。score-curve 与 cheat-bump 据此区分两条数据线避免混样
- **shoots[] 项 schema 扩展**：新增 `scripts_path` / `script_consistency` / `script_diff_pct` / `v2_prediction_written` / `script_hash_at_shoot`（详见 [migrations/1.1-to-1.2.md](migrations/1.1-to-1.2.md)）

### Changed — schema 1.1 → 1.2（MINOR）

- 升级 [migrations/registry.md](migrations/registry.md) `LATEST_SCHEMA` 标记 + 版本链表
- cheat-init 新建 state 写 `"schema_version": "1.2"`
- SessionStart hook `LATEST_SCHEMA="1.2"` —— 老用户 git pull + 跑会话 → hook 提示 schema mismatch → 用户跑 `/cheat-migrate` 5 秒升上来。MINOR 兼容，不强制（skills 用 `state.get(field, default)` 兜底）

### Why now

用户实际工作流：写完草稿 → **常常拍摄时即兴改文案** → 草稿和实际播出版本脱节。原"拍前预测，拍后只登记"的严格盲预测让"预测对的稿子"与"实际播出的稿子"不是同一份——校准失真。

v2 系统让"拍后改稿"成为一等公民：v1 留作档案，v2 基于实际拍摄稿重判，diff(v1, v2) 本身成为 rubric 升级的强证据（用户改稿改高了 ER → 工具学到这个用户的 ER 阈值跟当前公式不一致）。盲预测原则保留：v2 仍在发布前完成，没有播放数据可"作弊"。

### Added — Codex 安装兼容（@songth1ef [#6](https://github.com/XBuilderLAB/cheat-on-content/pull/6)）

- **`install.sh --codex`**：安装根路由 skill `cheat-on-content` 和 13 个子 skill 到 `~/.codex/skills/`
- **`install.sh --all`**：同时安装 Claude Code 和 Codex skill
- **`uninstall.sh --codex` / `--all`**：对称卸载 Codex 或双端安装
- **Codex 路由说明**：Codex 用自然语言触发同一套流程，不依赖 Claude Code 的 `/cheat-*` slash-command harness

### Added — Migration 系统（让长期迭代不打断老用户）

- **`/cheat-migrate` skill**：把老用户 `.cheat-state.json` 从旧 `schema_version` 升级到当前 `LATEST_SCHEMA`。幂等、不跳版、失败停在断点
- **`migrations/` 目录**：版本演进单一来源
  - `registry.md`：`LATEST_SCHEMA` 标记 + 完整版本链表
  - `<from>-to-<to>.md`：每步迁移 4 段（WHAT changed / WHY / HOW Claude steps / Manual fallback）
- **`shared-references/migration-protocol.md`**：演进哲学 + maintainer checklist（bump schema 必做的 4 件事）
- **SessionStart hook 增强**：检测 `state.schema_version != LATEST_SCHEMA` → 输出非阻塞警告，建议跑 `/cheat-migrate`
- **`install.sh --reinstall-hooks <project>`**：git pull 后重写用户项目 `.cheat-hooks/` 的脚本（不动 state / rubric / predictions）
- **state-management.md 升级**：所有 schema 升级文档指向 cheat-migrate；明确 MINOR / MAJOR 边界

### Why now

v0.1.0 用户的 state 是 schema 1.1。后续如果改字段语义、删字段、重命名等 → 没有迁移系统的话老用户 git pull 后会卡住。这套系统让"长期迭代不打断老用户"成为常态。

### Fixed

- **cheat-init `content_form` 存成字母 bug**：Phase 3 state JSON 模板用 `<Q1>` 抽象占位，导致 Claude 字面把 `"a"` 写进 state 文件而不是 enum `"opinion-video"`。修复：Q1/Q3/Q4/Q5 各加明确字母→enum 映射表 + Phase 3 模板加粗 warning。同时补全 7 个缺失的 `last_*` init 字段（之前靠 `state.get(field, default)` 兜底）+ `enabled_perf_adapters` 派生 + 强制 `initialized_at` 用本地 `+08:00` 时区不用 UTC `Z`

### Changed — README 重写（v0.1.0 ship 后的定位调整）

- 标题：英文 `Cheat on Content`，副标 `网红外挂`（之前 `网红作弊器`）
- Tagline 直面"作弊"框架：「做内容本质上就是作弊——谁先看穿规律，谁就拿走流量」
- 新增"那 ChatGPT / 豆包 / DeepSeek 不是也能干这个？"段——核心定位为"你自己的运营专家 + 自动进化"
- 删早期产品警示段（badge + 本 CHANGELOG 已经在传达，重复就是不自信）
- 砍 ARIS attribution（保留多 adapter 设计思路，去掉外部归功）
- README 总长 330 行 → 90 行
- cheat-init Phase 1 首屏文案同步重写：删方法论哲学，2 条 caveats（早期不准 + 强烈建议导对标）

### 余项

- Step B：软化更多硬编码规则
- 完整 reference-implementation 脱敏快照

---

## [0.1.0] — 2026-05-05

> ⚠️ **早期产品（v0.x）—— state schema 仍可能 breaking**
>
> 在 v1.0 之前，每次升级可能改变 `.cheat-state.json` 的字段结构。**升级前建议 backup 你的整个 `<your-channel>/` 目录**。重大 breaking 改动会在本 CHANGELOG 标 `BREAKING`，并在可能的情况下给手动迁移步骤。

### Added

- **方法论 + 12 个子 skill**：完整闭环 init → learn-from → seed → score → predict → shoot → publish → retro → bump，加 status / recommend / trends 辅助
- **3 条不可妥协原则**：盲预测 + 升级=全量重打 + rubric 是工作台不是博物馆（详见 `shared-references/`）
- **`/cheat-learn-from` 对标账号导入**：5-10 条对标样本派生 base rubric 信号 + script patterns。两种 input 方式（粘文本 默认 / whisper 转录）+ 两种 data 方式（手填 / adapter 自动抓）
- **Buffer 警戒系统**（cadence-protocol）：按发布频率派生颜色阈值，断更预警
- **统一预测格式 + confidence 等级**：所有阶段同一 7 组件预测，header 显示 🔴/🟠/🟡/🟢/🔵 信心等级
- **prediction-immutability hook**：harness 层强制原则 #1（端到端验证 5/5 通过）
- **SessionStart auto-report hook**：每次开会话自动渲染状态报告
- **跨模型 bump 审核**（mcp__llm-chat__chat）：rubric 升级时调外部 LLM 独立判定
- **douyin-session adapter**（Playwright）：自动抓抖音视频 + 评论数据
- **whisper adapter**：转录视频文件为 transcript
- **9 份 templates** + **2 份 starter rubrics**（opinion-video v2 校准 / opinion-video-zero v0 等权）
- **score-curve.py**：预测精度收敛曲线诊断工具

### 软规则（Claude 判断为主，非死磕门槛）

下面规则**有默认参考值**但 Claude 可基于强信号软违反：

- bump 触发样本数（默认 ≥5，可基于强反例破例）
- 同向偏差触发（默认连续 ≥3 次，可基于 1 次极端偏差破例）
- benchmark 影响淡出（默认 calibration_samples ≥10，可基于"用户数据 vs benchmark 差异度"破例）
- observation 升格门槛（默认 ≥2 样本，可基于强信号破例）

软违反时 Claude 必须显式标注 `judgment-driven` 让用户审视。

### 硬约束（不可软违反）

- bump 验证 `THRESHOLD = 4/5`（统计刚性）
- prediction immutability hook（binary）
- `RETRO_WINDOW_DAYS = 3` 默认（用户可配置 1/7）
- 必须有 ≥3 条 benchmark 样本才能拆 pattern
- 必须 ≥20 top 评论才能完成 manual paste 复盘

### 已知 limitations

- **v0.x 无自动 migration**：升级时若 state schema 变了，老用户需手动 wipe + 重 init
- **adapter fragility**：抖音 / 小红书 adapter 依赖反爬绕过，平台改版时可能 break，需要持续维护
- **whisper 中文准确度**：medium 模型够用，long-form 准确度一般，关键稿子建议 manual review

---

## 升级指南（pre-v1.0）

每次 git pull 之后：

1. **Symlink 模式装（推荐）**：直接生效，无需重装
2. **Copy 模式装**：重跑 `bash install.sh --copy`
3. **如果 CHANGELOG 标了 `BREAKING`**：照 manual migration steps 操作。无 steps 时建议 wipe + 重 init
