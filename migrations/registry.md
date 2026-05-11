# Migrations Registry

cheat-on-content 的 schema 版本演进单一来源。`/cheat-migrate` 读这份文件决定要跑哪些迁移。

---

## 当前 schema_version

**`1.4`** —— 由 `cheat-init` Phase 3 写入新 state 文件。

下方 `LATEST_SCHEMA` 标记位被 `cheat-migrate` skill 和 SessionStart hook 引用：

```
LATEST_SCHEMA = "1.4"
```

> 维护者注意：bump 这个值的同时**必须**新增对应迁移文件 + 在下方"版本链"追加一行。

---

## 版本链

按时间顺序，每行表示一个 schema 升级。`/cheat-migrate` 用此表算出从用户当前版本到 LATEST_SCHEMA 需要按顺序跑哪些 step。

| from | to | breaking? | 迁移文件 | 描述 |
|---|---|---|---|---|
| (none) | 1.0 | — | (内置) | v1 首版 schema |
| 1.0 | 1.1 | NO | [1.0-to-1.1.md](1.0-to-1.1.md) | 删 `mode` / `prediction_complexity` / `bucket_scheme` 三个枚举字段；新增 `target_publish_cadence_days` / `baseline_plays` / `benchmark_*` / `shoots` 等 |
| 1.1 | 1.2 | NO | [1.1-to-1.2.md](1.1-to-1.2.md) | `shoots[]` 项扩展 5 字段（`scripts_path` / `script_consistency` / `script_diff_pct` / `v2_prediction_written` / `script_hash_at_shoot`）— 配合"拍后改稿触发 v2 预测重判"工作流 |
| 1.2 | 1.3 | NO | [1.2-to-1.3.md](1.2-to-1.3.md) | 新增 `last_prediction_self_scored: bool` + `last_self_scored_at` 字段——配合 cheat-score-blind sub-agent 引入的 channel B 隔离打分。`true` 表示上次预测走了 `--skip-blind`，cheat-status 持续 nag |
| 1.3 | 1.4 | **BREAKING for blind channel** | [1.3-to-1.4.md](1.3-to-1.4.md) | rubric 文件拆分：`rubric_notes.md` → `rubric_notes.md`（blind 白名单，通用语言）+ `rubric-memo.md`（blind 硬禁读，含真实视频名/实绩）。state 字段不变；老用户必须跑 migrate 把现有 rubric_notes.md 拆开。不跑 → blind sub-agent 仍会标 non_blind_warning |

---

## 迁移文件命名约定

- 文件名：`<from>-to-<to>.md`（如 `1.1-to-1.2.md`）
- 每份必含 4 段：
  1. **WHAT changed** — 字段层 diff（新增 / 删除 / 重命名）
  2. **WHY** — 为什么这个改动
  3. **HOW (Claude steps)** — Claude 跑 `/cheat-migrate` 时按顺序执行的自然语言步骤
  4. **Manual fallback** — 如果用户不想跑 skill，手改 `.cheat-state.json` 的最小指令

---

## 哲学（详见 [shared-references/migration-protocol.md](../shared-references/migration-protocol.md)）

- **MINOR bump**（如 1.1 → 1.2）：仅新增字段或软化 enum 取值。老 state 用 `state.get(field, default)` 读到默认值，**可以不跑 migrate**——但跑了能让 state 文件变完整
- **MAJOR bump**（如 1.x → 2.0）：删字段 / 重命名字段 / 改字段语义。老 state **必须**跑 migrate，否则 skill 会读到不一致的字段
- **不允许跳版**：1.0 用户升到 1.3 必须按顺序跑 1.0→1.1、1.1→1.2、1.2→1.3。每步幂等
- **失败停在原地**：迁移到第 N 步失败 → state.schema_version 仍是 N-1（不是目标版本）。修复后重跑能从断点继续

---

## 给开发者：新增一个迁移

bump schema 时（顺序）：

1. 想清楚是 MINOR 还是 MAJOR（参考上面哲学段）
2. 改 `cheat-init/SKILL.md` 的 `schema_version` 硬编码为新值
3. 改本文件的 `LATEST_SCHEMA = "X.Y"` 标记位
4. 本文件"版本链"表追加一行
5. 新建 `migrations/<old>-to-<new>.md`，4 段都填
6. CHANGELOG.md 标 `BREAKING`（major）或 `MINOR`，加迁移文件链接
7. 跑一遍：在 fixture 老 state 上调 `/cheat-migrate`，验证升级到新版且 state 字段齐全

如果懒得写 4 段的标准 migration 文件，把 schema bump **推迟**到下一次有规模改动时一起做——不要先 bump schema 再补文档。
