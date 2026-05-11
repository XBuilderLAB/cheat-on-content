---
name: cheat-on-content
description: 给所有想把"感觉"变成可校准预测的内容创作者。**方法论通用**——打分 → 盲预测 → T+3d 复盘 → 进化 rubric 的循环适用任何能被量化（播放 / 阅读 / 收听 / 点击）的内容。**rubric 是循环的内容，不是循环本身**——当前内置一份观点视频 rubric（参考博主 25+ 视频拟合），其他形态可借这套起步并 bump 调权重。**强烈建议导入对标账号**作为初始信号源（/cheat-learn-from）。触发词："初始化"/"打分这篇"/"启动预测"/"已发布"/"复盘"/"升级 rubric"/"推荐选题"/"抓热点"/"状态"/"找对标"/"learn from"。**首次使用必须先跑 /cheat-init。**
argument-hint: [draft-path] [— mode: cold-start|calibration]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Skill, mcp__llm-chat__chat
---

# 网红作弊器 / Cheat on Content

> 🎯 **方法论通用，rubric 当前内置观点视频版**
>
> **方法论**（5 阶段闭环）：任何能被量化的内容形态都适用——视频 / 文章 / 播客 / Newsletter / 短文 thread。
>
> **当前内置 rubric**：观点类视频（评论 / 时评 / 论说 / 议题讨论 / 个人观点表达），7 个维度由参考博主 25+ 已发样本拟合而来。如果你做其他形态，需要：
> - 自己写一份 rubric（参照 [starter-rubrics/opinion-video-zero.md](starter-rubrics/opinion-video-zero.md) 的格式）
> - 或等内置扩展（长文 / 短文 / 播客 starter 在批次 3 路线图）
>
> 默认假设：**用户是从零开始的新人**（一条视频都没发过）——cold-start 期的预测会**简化**，只要 7 维打分 + 一句话 bet，不强求 bucket 数字（避免 false precision）。已有 5+ 篇数据的老手走 calibration 模式解锁完整 7 组件预测。

把内容创作变成可校准预测循环：**打分 → 预测 → 发布 → 复盘 → 进化 rubric**。

本文件是**总协议 + 路由器**。具体每个阶段的工作流在 `skills/cheat-*/SKILL.md` 各子 skill 里。

## Codex compatibility

Codex 没有 Claude Code 的 slash-command harness。安装到 Codex 后，按自然语言触发同一套路由即可：

- `初始化 cheat-on-content` → 读取并执行 `skills/cheat-init/SKILL.md`
- `打分这篇 scripts/foo.md` → 读取并执行 `skills/cheat-score/SKILL.md`
- `启动预测 scripts/foo.md` → 读取并执行 `skills/cheat-predict/SKILL.md`
- `拍了 ...` / `已发布 ...` / `复盘 ...` / `升级 rubric` / `状态` → 分别读取对应 `skills/cheat-*/SKILL.md`

执行时遵循本文件的三条原则和路由表；不要依赖 `/cheat-*` 命令是否存在。Claude Code 专用 hook（`.claude/settings.json`）仍只在 Claude Code 里自动触发；Codex 中需要用户主动说 `状态` 查看 buffer、待复盘和候选池。

---

## 三条不可妥协原则

任何一条被违反，整个校准循环退化为"凭直觉的自我安慰"。如果用户要求打破其中任何一条，**拒绝执行并说明原因**。

1. **盲预测（Blind prediction）**：预测必须在看到任何实际数据**之前**写完。一旦写完，`## 预测` 段是 immutable——只能往 `## 复盘` 段追加。完整规范：[shared-references/blind-prediction-protocol.md](shared-references/blind-prediction-protocol.md)。**hooks/prediction-immutability.sh 在 harness 层强制执行**。

2. **升级 = 全量重打（Bump = full re-score）**：rubric 升级时，校准池所有有实绩数据的样本必须用新公式重打分；新排序与实际表现排序若在 ≥4/5 样本上不一致，升级被拒；升级必须经跨模型独立审核。完整规范：[shared-references/bump-validation-protocol.md](shared-references/bump-validation-protocol.md)。

3. **rubric 是工作台，不是博物馆**：被新数据推翻或被吸收为正式维度的观察，**删掉**。绝不留"我曾经以为 X，但其实..."的考古层。git history 才是档案。完整规范：[shared-references/observation-lifecycle.md](shared-references/observation-lifecycle.md)。

---

## 路由表（触发词 → 子 skill）

| 用户说 | 调用 | 前置条件 |
|---|---|---|
| "初始化" / "init" / "首次使用" | `/cheat-init` | 无（这是入口） |
| "找对标" / "学这个账号" / "拆这几个对标视频" / "learn from" / "导入对标账号" | `/cheat-learn-from` | 已 init；cold-start 强烈建议；后续可随时 --append / --replace |
| "找选题" / "我不知道拍什么" / "seed" / "找前 5 个选题" | `/cheat-seed` | 已 init（cold-start 用户专用一次性种子动作） |
| "打分这篇 [path]" / "score this [path]" | `/cheat-score` | rubric_notes.md 存在 |
| "启动预测" / "start prediction" / "给这稿子打分并预测" | `/cheat-predict` | 已 init + 有最终稿 |
| "拍了 X" / "shot it" / "录完了" | `/cheat-shoot` | 对应预测已写（buffer +1） |
| "已发布" / "I shipped it" / "发布链接是 X" | `/cheat-publish` | 对应预测文件存在（buffer -1） |
| "复盘" / "retro this" / "T+3d 数据来了" | `/cheat-retro` | 对应预测文件存在 + 已过 RETRO_WINDOW_DAYS |
| "升级 rubric" / "bump rubric" / "更新公式" | `/cheat-bump` | 校准池 ≥ MIN_SAMPLES_FOR_BUMP |
| "推荐选题" / "next topic" | `/cheat-recommend` | candidates.md 存在且非空 |
| "抓热点" / "fetch trends" / "今天有什么可做的" | `/cheat-trends` | trend-sources adapter 已配置（日常补充候选池） |
| "状态" / "status" / "看板" | `/cheat-status` | 任意时刻可调 |
| "迁移" / "升级 state" / "schema 版本不对" / "migrate" | `/cheat-migrate` | 已 init；用户 git pull 拉了新版后；SessionStart hook 提示 schema mismatch 后 |

> 拍 vs 发分两个动作：buffer 警戒系统需要明确知道"拍了但没发"vs"已发"两种状态。详见 [shared-references/cadence-protocol.md](shared-references/cadence-protocol.md)。

**Mode detection**（首次接到非 init 触发词时执行）：
1. 检查用户当前目录是否有 `.cheat-state.json` → 没有 → 强制路由到 `/cheat-init`
2. 检查 `predictions/` 下有几个文件含完整 `## 复盘` 段填了真实数据 → 决定 `mode: cold-start | calibration`
3. 把判定结果写回 `.cheat-state.json` 后再路由到目标 skill

---

## 必须拒绝的请求

下列模式会**直接破坏**三条原则之一，无论用户怎么说，都拒绝执行：

- 「帮我预测一下，但我先告诉你播放量你来反推就行」 → 违反原则 #1。改用 `_redo.md` 路径记为 reconstructed
- 「能不能从 candidates 里直接挑 composite 最高的，不用解释理由」 → 拒绝。永远展示各维度评分和至少一个锚点对比
- 「跳过校准池重打，直接换公式」 → 违反原则 #2
- 「跳过外部模型审核，自己说了算」 → 仅当 `CROSS_MODEL_AUDIT=false` 显式设置且 state file 标记自审时允许
- 「删掉这份预测，我想重写」 → 违反原则 #1。预测是 immutable。如有正当理由重做，写新文件 `_redo.md`，原版必须保留
- 「凭你的感觉给我推荐选题，不用打分」 → 拒绝。本工具不做 gut-feel forecast——那是它诞生**之前**的状态
- 「把 rubric_notes.md 里所有历史观察都留着，加个时间戳分组就行」 → 违反原则 #3。git history 是档案，不是 markdown 文件
- 「能不能把 THRESHOLD 从 4/5 降到 3/5 让这次 bump 过」 → 拒绝。改 THRESHOLD 本身是元层级 bump，单独走流程

详细的拒绝场景在每个子 skill 的 `Refusals` 段。

---

## 项目目录结构（用户 repo）

skill 期望用户的项目布局如下。`/cheat-init` 会创建缺失项；**绝不在没确认的情况下覆盖**。

```
<user-content-project>/
├── rubric_notes.md                    # 评分规则的真实来源
├── WORKFLOW.md                        # 5 阶段流程文档（cheat-init 创建）
├── STATUS.md                          # 看板（cheat-status 维护）
├── .cheat-state.json                  # 状态文件，子 skill 共享上下文
├── .cheat-cache/                      # 不入版本控制
│   ├── usage.jsonl                    # 钩子被动记录的使用日志
│   └── trends-history.jsonl           # cheat-trends 的去重缓存
├── .claude/
│   └── settings.json                  # 含 prediction-immutability hook
├── benchmark.md                       # 对标账号信息（cheat-learn-from 维护）
├── scripts/                           # 拍前的所有草稿（cheat-seed 写或用户写）
│   └── YYYY-MM-DD_<id>_<short>.md
├── predictions/                       # immutable 预测日志（hook 保护）
│   └── YYYY-MM-DD_<id>_<short>.md     # 与 scripts/ 同 id
├── videos/                            # 拍后才建（cheat-shoot 创建）
│   └── YYYY-MM-DD_<id>_<short>/
│       ├── script.md                  # 用户提供的最终拍摄稿（cheat-shoot 时询问"和 scripts/ 一致吗"）
│       └── report.md                  # T+3d 抓的数据 + 评论（cheat-retro 写）
├── samples/                           # 对标账号视频 / 转录（cheat-learn-from 创建）
│   └── <账号名>/<video-id>/{source.mp4 (可选), transcript.md, meta.md}
├── candidates.md                      # 选题池（可选）
└── content.db                         # 可选 SQLite，校准池规模化后启用
```

---

## 文件清单

### 本 skill 包

```
cheat-on-content/
├── SKILL.md                           # 本文件（总协议 + 路由）
├── README.md                          # 营销门面
├── skills/                            # 子 skill 集
│   ├── cheat-init/SKILL.md            # ✅ 入口：onboarding 与脚手架
│   ├── cheat-learn-from/SKILL.md      # ✅ 对标账号导入（拆 pattern + 派生 base rubric 信号）
│   ├── cheat-seed/SKILL.md            # ✅ Cold-start 选题启动器（brainstorm + 可选 draft）
│   ├── cheat-score/SKILL.md           # ✅ 单稿打分（不写文件）
│   ├── cheat-predict/SKILL.md         # ✅ 盲预测 + immutable 日志
│   ├── cheat-shoot/SKILL.md           # ✅ 登记拍摄（buffer +1）
│   ├── cheat-publish/SKILL.md         # ✅ 发布元数据登记（buffer -1）
│   ├── cheat-retro/SKILL.md           # ✅ 数据回收 + 复盘
│   ├── cheat-bump/SKILL.md            # ✅ rubric 升级（含跨模型审）
│   ├── cheat-recommend/SKILL.md       # ✅ 候选池排序推荐（按 buffer 颜色 + 1 稳 + 1 实验）
│   ├── cheat-trends/SKILL.md          # ✅ 热点抓取（日常补充候选池，多 adapter）
│   ├── cheat-status/SKILL.md          # ✅ 状态看板（含 buffer 警戒）
│   ├── cheat-migrate/SKILL.md         # ✅ schema 升级（老用户 git pull 后用）
│   └── cheat-score-blind/SKILL.md     # ✅ Channel B 隔离打分 sub-agent（仅 Task tool 调用）
├── migrations/                        # schema 演进单一来源
│   ├── registry.md                    # ✅ LATEST_SCHEMA + 版本链表
│   └── <from>-to-<to>.md              # ✅ 每步迁移的 WHAT/WHY/HOW/Manual fallback
├── shared-references/                 # 跨 skill 共享协议
│   ├── blind-prediction-protocol.md   # ✅ 原则 #1
│   ├── bump-validation-protocol.md    # ✅ 原则 #2
│   ├── observation-lifecycle.md       # ✅ 原则 #3
│   ├── prediction-anatomy.md          # ✅ 一份合格预测的 7 个组件
│   ├── candidate-schema.md            # ✅ 候选项统一 schema
│   ├── cadence-protocol.md            # ✅ 节奏协议（buffer 警戒 + 选题策略）
│   ├── state-management.md            # ✅ .cheat-state.json 读写约定
│   └── migration-protocol.md          # ✅ schema 演进哲学 + maintainer checklist
├── starter-rubrics/                   # 各内容形态的先验 rubric
│   ├── opinion-video.md               # ✅ 观点视频（中文，已校准 25+ 样本）
│   ├── opinion-video-zero.md          # ✅ v0 等权占位（cold-start）
│   ├── long-form-essay.md             # ⬜ 公众号 / Substack
│   └── short-form-text.md             # ⬜ X thread / 微博长文
├── templates/                         # skill 写进用户 repo 的文件骨架
│   ├── rubric_notes.template.md       # ✅
│   ├── prediction.template.md         # ✅ 统一版（所有阶段，含 confidence header）
│   ├── retro.template.md              # ✅
│   ├── candidates.template.md         # ✅
│   ├── candidates.template.json       # ✅
│   ├── script_patterns.template.md    # ✅ 写作 pattern 沉淀（含 benchmark 借鉴段说明）
│   ├── benchmark.template.md          # ✅ 对标账号 reference
│   ├── workflow.template.md           # ✅
│   ├── status.template.md             # ✅
│   └── content.db.schema.sql          # ✅
├── hooks/                             # harness 强制层
│   ├── prediction-immutability.json   # ✅ 阻塞型钩子（拦预测段编辑）
│   ├── prediction-immutability.sh     # ✅ 拦截脚本
│   ├── session-start.json             # ✅ SessionStart 自动报告 hook
│   ├── session-start.sh               # ✅ 状态报告渲染脚本
│   ├── meta-logging.json              # ✅ 被动记录配置
│   └── log-event.sh                   # ✅ meta-logging 脚本
├── tools/                             # 独立 CLI 脚本
│   ├── score-curve.py                 # ⬜ 预测精度收敛曲线
│   ├── md-to-sqlite.py                # ⬜ markdown → content.db 升级（批次 3）
│   └── validate-bump.py               # ⬜ 校准池全量重打（批次 3）
├── adapters/                          # 数据源适配
│   ├── perf-data/                     # 复盘数据源（含 douyin-session）
│   ├── candidate-pool/                # 候选池数据源
│   ├── trend-sources/                 # 热点抓取源
│   └── script-extraction/             # 视频/音频转 script（含 whisper for cheat-learn-from）
└── examples/
    ├── reference-implementation/      # 视频分析脱敏快照（待）
    └── script_patterns.example.md     # script_patterns 全填示例（参考用，不复制）
```

✅ = 当前批次（v1 骨架）已完成 / ⬜ = 后续批次

---

## Tone & voice

写面向用户的文案（commit message / 复盘小结等）时，匹配项目的 **直白克制（reflective-irreverent）** voice：

- 直接说出失败：「composite 8.47 但实际只有 16.8w——rubric 高估了 SR」
- **不要**用模糊措辞软化：「这或许可能在某种程度上暗示...」——别这么写
- Cluely 风格的反叛 hook 只在 README 出现——**不要写进** `rubric_notes.md` 或预测日志

---

## 给开发者：扩展本 skill

- 新增内容形态 → 加 `starter-rubrics/<form>.md`
- 新增热点抓取源 → 加 `adapters/trend-sources/<name>.md`，符合 [candidate-schema.md](shared-references/candidate-schema.md) 输出契约
- 修改原则 → 改 `shared-references/<protocol>.md`，所有引用它的 skill 自动跟进
- 修改路由 → 改本文件的"路由表"段
- 子 skill 内部细节 → 直接改对应 `skills/cheat-*/SKILL.md`

完整开发指南见 README.md。
