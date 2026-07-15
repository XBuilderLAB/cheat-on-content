---
name: cheat-audit
description: 给成熟创作者做一次可交付的历史账号体检。导入本人账号最近 20–50 篇内容，生成账号基线、Top/Bottom 证据、受众信号、3 个增长假设和四周实验计划。历史数据一律标 reconstructed，绝不冒充盲预测或增加 calibration_samples。触发词："给这个账号做体检"/"账号诊断"/"account audit"/"生成校准报告"。
argument-hint: "[input-json] [— account-name: <name>] [— dir: <data-dir>]"
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# /cheat-audit — 可售卖的账号体检

把现有校准能力压缩成一个客户能理解的结果，不做玄学式“爆款预测”。

## 不可破坏的边界

1. 只分析客户本人账号，或客户明确授权的数据。
2. 历史数据必须写 `source_classification: reconstructed`。
3. 账号体检不得增加 `.cheat-state.json.calibration_samples`。
4. 任何历史分析都不得写入 `predictions/` 并伪装成盲预测。
5. 每条中等或更高置信假设至少引用两个内容 ID；否则降为 low。
6. 报告必须保留“这是决策校准，不是爆款保证”的声明。

## Phase 0：解析工作目录

使用统一优先级解析数据目录：

1. 用户显式 `--dir`
2. `CHEAT_DATA_DIR`
3. 工作区 `.cheat-content.json`
4. 当前目录旧布局

推荐用跨平台 CLI 验证：

```text
python <skill-root>/tools/cheat_cli.py --project <workspace> status
```

如果不存在 `.cheat-state.json`，先路由 `/cheat-init`。不得在源码仓库里创建客户数据目录。

## Phase 1：确认输入与授权

向用户确认一次：

- 这是本人账号或已获授权。
- 样本范围为最近 20–50 篇。
- 用户接受历史报告属于 reconstructed 分析，不是盲预测。

输入路径二选一：

### A. xhs-explore 直接抓取（默认）

```text
python <skill-root>/adapters/perf-data/xhs-explore/review.py audit <data-dir>/deliverables/account-audit 30 "<账号名>"
```

首次使用先运行 `review.py login`。原始导出写到 `.cheat-cache/account-audit/account-notes.json`，不得入 Git。

### B. 已有 JSON

JSON 可以是 note 数组，也可以是 `{"notes": [...]}`。运行：

```text
python <skill-root>/tools/cheat_cli.py --project <workspace> --dir <data-dir> audit \
  --input <input.json> --account-name "<账号名>"
```

## Phase 2：确定性生成

必须生成三个文件：

- `deliverables/account-audit/account-audit.json`
- `deliverables/account-audit/account-audit.md`
- `deliverables/account-audit/four-week-experiments.md`

引擎负责：

- 去重和指标标准化。
- 均值、中位数、P25/P75，而不是只报平均值。
- Top/Bottom 内容及内容 ID/链接。
- 选题聚类、开头类型和收藏/评论驱动信号。
- 评论派生的自我认同、提问、反驳证据与反画像。
- 恰好三个可证伪假设和四周实验计划。

## Phase 3：交付前自检

逐项检查：

- `account-audit.json.audit_version == "1.0"`
- `source_classification == "reconstructed"`
- `calibration_samples_increment == 0`
- 恰好三个 hypotheses
- `confidence != low` 的 hypothesis 至少两个 evidence
- Markdown 每个 Top/Bottom 条目都带内容 ID 或链接
- 数据不足、评论缺失、零曝光等局限有明确标注
- 客户凭证、Cookie、原始缓存没有进入源码目录或 Git

任一不满足则修复后再交付，不允许人工把低置信改写成高置信。

## Phase 4：交付与下一步

向客户展示：

1. 账号基线。
2. 三个假设及证据。
3. 第 1 周唯一实验变量。

接下来选择一篇尚未发布的新稿，正常走 `/cheat-predict`；发布后走 `/cheat-publish` 和 `/cheat-retro`。只有这条真正的盲预测—复盘才增加 calibration_samples。

## Refusals

- “把历史爆款补写成你早就预测到了” → 拒绝，必须标 reconstructed。
- “没有授权，帮我抓竞品后台数据” → 拒绝；公开对标研究改走 `/cheat-learn-from`。
- “证据只有一篇，但写成确定规律” → 拒绝，confidence 必须 low。
- “顺便自动发布” → 本技能不做自动发布。
