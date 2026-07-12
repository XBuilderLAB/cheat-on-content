---
name: cheat-migrate
description: 把老用户的 .cheat-state.json 升级到当前 schema_version。读 migrations/registry.md 算迁移链，按顺序应用每一步迁移文件。幂等：跑两次结果一样。失败停在中间版本不前进。触发词："迁移"/"升级 state"/"migrate"/"我的 state 是老版本"/"schema 版本不对"。
argument-hint: "[— from: <version>] [— to: <version>] [— dry-run]"
allowed-tools: Bash(*), Read, Write, Edit, Skill
---

# /cheat-migrate — Schema 版本迁移

把用户 `.cheat-state.json` 从旧 `schema_version` 升级到 cheat-on-content 当前期望的 `LATEST_SCHEMA`。

---

## Overview

```
[用户：迁移 / 或 SessionStart 提示后用户跑]
  ↓
[Phase 0: 读 .cheat-state.json + migrations/registry.md → 确定迁移链]
  ↓
[Phase 1: dry-run（默认）展示迁移计划，等用户确认]
  ↓
[Phase 2: 备份 .cheat-state.json → .cheat-state.json.backup-<timestamp>]
  ↓
[Phase 3: 按顺序对每个 step 应用对应迁移文件的 HOW 段]
  ↓
[Phase 4: 验证升级后 state 文件能被解析 + schema_version 已更新]
  ↓
[Phase 5: 报告 + 提示如有备份需要清理]
```

---

## Constants

- **REGISTRY_PATH = `${SKILL_DIR}/../../migrations/registry.md`** — 版本链单一来源
- **MIGRATIONS_DIR = `${SKILL_DIR}/../../migrations/`** — 迁移文件目录
- **DRY_RUN_BY_DEFAULT = true** — 首次跑展示计划，不直接改文件
- **BACKUP_BEFORE_WRITE = true** — 写之前必备份；备份文件保留至下次成功 init / 用户手动清理
- **STOP_ON_STEP_FAILURE = true** — 任何 step 失败 → 停在中间版本，不前进，不回滚

> 💡 调用时覆盖：`/cheat-migrate — dry-run: false` 直接执行 / `/cheat-migrate — to: 1.2` 仅升到指定版本

---

## Inputs

| 必填 | 来源 |
|---|---|
| `.cheat-state.json` | 用户项目根 |
| `migrations/registry.md` | LATEST_SCHEMA + 版本链表 |
| `migrations/<from>-to-<to>.md` | 每步具体迁移指令 |

---

## Workflow

### Phase 0: 确定迁移链

1. 读 `.cheat-state.json` → 解析 `current_version = state.schema_version`
2. 读 `migrations/registry.md` → 解析 `LATEST_SCHEMA` 字段（行：`LATEST_SCHEMA = "X.Y"`）
3. 解析 `args.to` 覆盖（如有）；否则 target = LATEST_SCHEMA
4. 解析 `args.from` 覆盖（罕见场景：用户的 state 文件 schema 字段坏了，强制指定起点）
5. **状态判断**：
   - `current_version == target` → 输出"✅ state 已是 {target}，无需迁移" → 退出
   - `current_version > target`（比如用户跑了 dev 版又切回 release）→ 报错"无法降级，请手动调整或重新 init"
   - `current_version < target` → 继续，从注册表查出迁移链
6. 从注册表"版本链"表算出 `chain = [(from, to, file), ...]`，按顺序串起 current → target

如果某一步在注册表里缺失（比如 `current_version` 不在表里）→ 报错并展示"目前已知版本：[1.0, 1.1, ...]"，让用户检查。

### Phase 1: dry-run

输出迁移计划：

```
📋 迁移计划

当前版本: 1.0
目标版本: 1.2
将按顺序跑 2 步：

  [1/2] 1.0 → 1.1（MINOR）
       新增字段：typical_duration_seconds, target_publish_cadence_days, ...（共 12 字段）
       删除字段：mode, prediction_complexity, bucket_scheme
       详见: migrations/1.0-to-1.1.md

  [2/2] 1.1 → 1.2（MINOR）
       新增字段：[...]
       详见: migrations/1.1-to-1.2.md

⚠️ 备份位置: .cheat-state.json.backup-<timestamp>

继续吗？回 yes 执行 / no 退出 / dry-run-detail 看每步具体改什么。
```

如 `args["dry-run"] == false` 或用户回 yes → 进 Phase 2。

### Phase 2: 备份

```bash
cp .cheat-state.json .cheat-state.json.backup-$(date +%s)
```

输出："📦 备份到 .cheat-state.json.backup-1714838400"

### Phase 3: 按顺序应用每步

对 chain 里的每个 (from, to, file)：

1. 输出 "→ [N/M] 应用 {file}..."
2. 读 `migrations/<file>` → 找到 `## HOW (Claude steps for /cheat-migrate)` 段
3. **按段内自然语言步骤逐项执行**——这是关键：迁移是 Claude 读 markdown 跑的，不是 python 脚本
4. 每步完成后：
   - 更新内存里的 state.schema_version = to
   - **原子写**到磁盘（写 .tmp → rename）
5. 如某步失败：
   - 输出"❌ {file} 第 N 步失败：{error}"
   - 不前进、不回滚（state 已停在前一步成功的中间版本）
   - 提示："已停在 schema_version: {last_success_version}。修复后重跑 /cheat-migrate 会从这里继续"
   - 退出

### Phase 4: 验证

升完后：
1. 读 `.cheat-state.json` → 解析 → 应能成功
2. 检查 `schema_version == target`
3. 检查所有"必填字段"非缺失（参照 [shared-references/state-management.md](../../shared-references/state-management.md) 完整 schema）
4. 失败 → 报错"迁移完成但验证失败：{detail}。state 文件可能不一致——查看备份恢复"

### Phase 5: 报告

```
✅ 迁移完成

  从: 1.0
  到: 1.2
  应用步骤: 2

state 文件现在含 X 字段，全部通过验证。

📦 备份保留：.cheat-state.json.backup-1714838400
   （确认一切正常后可手动 rm；下次成功 /cheat-init 也会清理过期备份）

下一步建议：
  - 跑 /cheat-status 确认看板正常
  - 如有 hooks 重装需求，跑 bash <skill_repo>/install.sh --reinstall-hooks
```

---

## Key Rules

1. **幂等**：在已升过的 state 上重跑应该立刻退出"无需迁移"，**不**重复应用步骤。靠对比 `current_version == target` 实现
2. **不跳版**：1.0 → 1.3 必须按 1.0→1.1→1.2→1.3 顺序，每步独立可恢复。不允许"直接升 1.0 → 1.3 的合并 migration"
3. **不静默兼容**：state 文件 schema_version 不识别 → 明确报错"未知版本 X，最近已知版本 Y"，不假装能继续
4. **失败停在原地**：第 N 步失败时 schema_version 停在 N-1 已成功的版本，不回滚到迁移前。重跑能从断点继续
5. **备份是硬约束**：写之前必有备份。即使用户跑 `--dry-run: false`，备份动作仍执行
6. **不动 predictions / rubric / videos**：只改 `.cheat-state.json`。其他用户数据由各自 skill 负责，迁移 skill 不碰
7. **MAJOR vs MINOR 透明**：dry-run 输出必标 (MAJOR) / (MINOR)。MAJOR 时额外提示"老 skill 用旧字段读会出问题，迁移完不能回退到老 skill 版本"

---

## Refusals

- 「跳过 dry-run，立刻覆盖我的 state」 → **允许**（`--dry-run: false`），但备份仍强制执行
- 「我的 state 损坏了 / schema_version 字段没了，能不能猜一个版本来跑」 → 允许指定 `--from: 1.0`，但要警告"基于猜测的迁移可能导致字段错位"
- 「降级到旧版本（current > target）」 → 拒绝。schema 演进单向。要降级请手动 cp 历史 git 快照
- 「合并多步迁移成一个 atomic」 → 拒绝。每步独立可恢复是设计核心
- 「在跑 cheat-bump / cheat-predict 中途调 migrate」 → 拒绝。等其他 skill 完成再跑，避免 in_progress_session 状态被破坏

---

## Integration

- 上游：SessionStart hook 检测 `state.schema_version != LATEST_SCHEMA` → 输出红色警告 + 建议跑 `/cheat-migrate`
- 上游（手动）：用户 git pull 拉了新版后，看 CHANGELOG 标 BREAKING → 主动跑
- 下游：跑完后所有其他 skill 读 state 都能拿到最新字段
- 与 `cheat-init`：init 写新 state 时直接用 LATEST_SCHEMA，不需要走 migrate
- 与 `install.sh --reinstall-hooks`：迁移**不**重装 hook 脚本（hook 脚本属于 skill 包代码，不属于用户 state）。这两件事解耦

---

## State 字段读写

本 skill **写**：
- `schema_version`（每步成功后更新）

本 skill **读**：
- 所有现有字段（取决于具体 migration 文件的 HOW 步骤）

本 skill **绝不**写：
- `calibration_samples` / `pending_retros` / `shoots` 等业务状态（这些是其他 skill 的职责）
- 例外：迁移文件明确说"派生新字段值时需要扫 predictions/ 算 baseline_plays"，那是初始化新字段，不是改老字段

---

## Examples

### 示例 1：用户从 v0.1.0 升到 v0.2.0（假设 0.2 引入 schema 1.2）

```
用户：迁移
Claude: [跑 cheat-migrate]
  Phase 0: current=1.1, target=1.2, chain=[(1.1, 1.2)]
  Phase 1: dry-run 输出计划
  用户: yes
  Phase 2: 备份
  Phase 3: 应用 1.1-to-1.2.md（MINOR：新增 platform_metrics_url 等字段）
  Phase 4: 验证 OK
  Phase 5: 报告 ✅
```

### 示例 2：用户跳了多版

```
用户：我从 v0.1.0 升到 v0.5.0，state 还是 1.0
Claude: [跑 cheat-migrate]
  Phase 0: current=1.0, target=1.4 (LATEST), chain=[(1.0, 1.1), (1.1, 1.2), (1.2, 1.3), (1.3, 1.4)]
  Phase 1: dry-run 输出 4 步计划
  ...
```

### 示例 3：迁移中途失败

```
Phase 3:
  → [1/4] 应用 1.0-to-1.1.md ✓
  → [2/4] 应用 1.1-to-1.2.md ✓
  → [3/4] 应用 1.2-to-1.3.md... ❌ 失败：用户 baseline_plays 字段含非数字值，无法转 int
  
state 已停在 schema_version: 1.2。
修复 .cheat-state.json 后重跑 /cheat-migrate 会从 1.2 → 1.3 继续。
```
