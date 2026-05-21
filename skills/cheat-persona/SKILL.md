---
name: cheat-persona
description: 从复盘评论数据派生 / 刷新账号的受众画像，写入 audience.md。这是和 rubric 平行的第二个派生物——rubric 答"怎么打分"，persona 答"谁在看"。cheat-seed 选题 / 写稿时读它。**audience.md 含实绩信号，cheat-score-blind 硬禁读**。触发词："构造受众画像"/"更新 persona"/"我的观众是谁"/"build persona"/"刷新受众画像"/"看看我的受众画像"。
argument-hint: [— seed-from-benchmark] [— rebuild]
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep
---

# /cheat-persona — 受众画像派生

从 `predictions/*.md` 复盘段的评论数据，聚类出账号真实受众画像，写入 `audience.md`。

---

## 核心定位

persona 是和 rubric **平行**的第二个派生物，**不是 rubric 的一部分**：

```
复盘数据（评论 + 完播 + 转粉）
   ├──→ rubric 进化（cheat-bump）   —— "怎么打分"
   └──→ 受众画像（cheat-persona）    —— "谁在看"
两者都喂给 cheat-seed，但用途不同
```

- **rubric**：这稿子会不会爆 → 喂 cheat-predict 打分
- **persona**：谁会因为这条多看 3 秒 / 留评论 / 转发 → 喂 cheat-seed 选题 + 写稿

**绝不混**：persona 不进打分公式。rubric 的 AB 维度（受众广度）可以参考 persona，但那是 cheat-bump 的事，不是这里。

## ⚠️ 污染隔离（不可省）

`audience.md` 从复盘评论派生 = **含已发布作品的实绩信号**。因此：

- `audience.md` 在 [cheat-score-blind](../cheat-score-blind/SKILL.md) 的 hard refusal list 里，refusal_code `blocked_audience`
- persona 影响 cheat-seed **写什么**（creative direction），不影响 cheat-predict **怎么打分**（blind sub-agent 永远不读 audience.md）
- 这是干净的：persona 塑造的内容进了成稿，blind sub-agent 照成稿本身打分——没有 leak。leak 只会发生在 sub-agent 能读 audience.md "因为这受众爱 X 所以加分" 的情况，而它读不到

## Overview

```
[用户：构造受众画像 / 更新 persona]
  ↓
[Phase 0: 收集数据 — 扫 predictions/*.md 复盘段评论 + benchmark.md]
  ↓
[Phase 1: 数据量判定 → 派生 Confidence 等级]
  ↓
[Phase 2: 评论聚类 — 自我认同 / 情绪寄存 / 反驳点 / 语言]
  ↓
[Phase 3: persona × rubric 交叉检验]
  ↓
[Phase 4: 写 audience.md（覆盖式重建，header 记 version + last_rebuilt）]
  ↓
[Phase 5: 控制台报告 + 跟上次画像的 diff]
```

## Constants

- **AUDIENCE_PATH = audience.md** — 受众画像落盘位置
- **MIN_RETROS_FOR_DATA_GROUNDED = 3** — 复盘数 ≥3 才算"数据扎实"（可基于评论质量软判断）
- **MIN_COMMENTS_PER_TRAIT = 3** — 一条"验证特征"至少要 3 条评论证据，否则降到"假设特征"
- **SEED_FROM_BENCHMARK = auto** — 无自己复盘数据但有 benchmark 时，seed 一份未验证画像

> 💡 调用覆盖：`/cheat-persona — seed-from-benchmark`（强制用 benchmark seed）/ `— rebuild`（即使数据没变也重建）

## Inputs

| 来源 | 用途 |
|---|---|
| `predictions/*.md` 的 `## 复盘` 段 | **主数据源**——top 评论（带赞数）。persona 的金矿 |
| `videos/*/report.md` | 完播 / 转粉率——薄信号，推"留得住 vs 留不住" |
| `benchmark.md` | 冷启动 seed——"看对标的人 ≈ 你想要的人" |
| `rubric_notes.md` | Phase 3 交叉检验用——persona 食欲 vs rubric 校准现实 |
| `audience.md`（如已存在） | 上一版画像，用于 Phase 5 diff |

## Workflow

### Phase 0: 收集数据

1. Glob `predictions/*.md`，对每个文件读 `## 复盘` 段（**只读复盘段——这是 channel A，本来就看实绩**）
2. 抽取每篇的 top 评论（带赞数）+ 实绩 bucket
3. 统计：有评论的复盘篇数 `N_retros`、评论总数 `N_comments`
4. 读 `benchmark.md`（如存在）
5. 读 `audience.md`（如已存在）→ 留作 Phase 5 diff

### Phase 1: 数据量判定 + Confidence

| 情况 | Confidence | 行为 |
|---|---|---|
| `N_retros == 0` 且无 benchmark | 🔴 无数据 | **不强行造**——告诉用户"persona 需要复盘数据。先跑几篇 cheat-retro，或导 benchmark"，退出 |
| `N_retros == 0` 但有 benchmark | 🟠 benchmark-seed 未验证 | seed 一份 aspirational persona，**全文标"未验证"** |
| `N_retros` 1-2 | 🟡 早期信号 | 能产出但特征多落"假设"段 |
| `N_retros` 3-5 | 🟢 数据扎实 | 正常产出 |
| `N_retros` ≥6 | 🔵 稳健 | 正常产出 + 可做更细的食欲分层 |

Confidence 等级写进 audience.md header。

### Phase 2: 评论聚类

对收集到的所有评论，按四个维度聚类：

1. **自我认同**——"我也是…" / "这就是我" / "作为一个…" 模式。统计哪类身份反复出现（"大厂打工人" / "一人公司" / "考研党" / ...）
2. **情绪寄存**——观众来评论是为了什么情绪？被验证（"说得太对了"）/ 宣泄（"我也好累"）/ 抬杠（"我不同意"）/ 求助（"那该怎么办"）。统计占比
3. **反驳点**——哪些观点引来稳定的反对声。这是 persona 边界
4. **语言**——他们怎么说话。玩梗密度、真诚 vs 戏谑、有没有复制你的金句

**聚类纪律**：
- 一条"验证特征"至少 `MIN_COMMENTS_PER_TRAIT`（3）条评论证据。不够 → 降到"假设特征"段
- 每条特征**必须**能引出具体评论 + 出处（哪篇 prediction 的复盘段）+ 条数
- 发现"反画像"信号（你以为的受众 vs 实际评论的人不一样）→ 写"反画像"段

### Phase 3: persona × rubric 交叉检验

读 `rubric_notes.md` 当前 rubric + 校准历史。检查：

- persona 说"受众爱 X 类主题" → rubric 校准池里 X 类主题真的 over-perform 吗？
- 不一致 → 在 audience.md 的"persona × rubric 交叉检验"段 **flag 出来**

诚实要求：两个派生物矛盾时**不要**强行调和。明确写"persona 说 A，rubric 校准说 B，待下次复盘澄清"——矛盾本身是信号。

### Phase 4: 写 audience.md

**覆盖式重建**（不是 append）——persona 是活文档，每次 rebuild 重写全文。但：

- header 的 `Persona 版本` +1（v0 → v1 → v2）
- header 记 `Last rebuilt` 日期 + `数据基础`（N 篇复盘 / M 条评论）+ `Confidence`
- 文件底部"版本历史"段 **append 一行**：`vN — 基于 M 篇复盘 / K 条评论，主要变化：...`（这是唯一保留的历史；不搞 memo 累积——persona 是活文档不是公式）

用 [templates/audience.template.md](../../templates/audience.template.md) 的结构。

⚠️ **不走版本 memo / 不调跨模型审**——persona 不是高风险不可逆动作（写错了重跑一次就好），过度工程没必要。

### Phase 5: 报告

```
✅ 受众画像已更新：audience.md（v2，🟢 数据扎实）

数据基础：4 篇复盘 / 87 条评论
核心画像：25-35 岁职场人，来找情绪共鸣不来找信息……

跟 v1 的主要变化：
- 新验证："深夜刷手机" 场景共鸣强（v1 是假设，本次 17 条评论验证）
- 新反画像：原以为"学生党"是受众，但评论里学生占比 <5% → 移到反画像
- ⚠️ 交叉检验 flag：persona 说受众爱"职场吐槽"，但 rubric 校准显示职场类 composite 偏低——下次复盘留意

下一步：
- cheat-seed 选题 / 写稿时会自动参考这份画像
- 再跑 3 篇复盘后建议再 /cheat-persona 刷新
```

## Key Rules

1. **数据派生，不手写**——persona 必须来自评论聚类。用户想手动加特征 → 允许，但标 `user-asserted`（未经数据验证）
2. **证据强制**——验证特征必须带评论条数 + 出处。无证据的进"假设"段
3. **覆盖式重建**——每次 rebuild 重写 audience.md 全文，只在版本历史段 append 一行
4. **不进打分**——persona 永远不喂 cheat-predict / cheat-score-blind。它是 cheat-seed 的 creative lens
5. **矛盾不调和**——persona × rubric 冲突时如实 flag，不强行编一个故事
6. **冷启动诚实**——没数据就说没数据，benchmark seed 全程标"未验证"

## Refusals

- 「我觉得我的受众就是 X，你直接写进 audience.md」 → 可以写，但标 `user-asserted` 放"假设特征"段，不放"验证特征"。persona 的价值在于数据 vs 你的幻想之间的 gap
- 「persona 也给 cheat-predict 用，让打分更准」 → 拒绝。persona 是实绩派生物，进打分 = 把 channel B 的隔离打穿。persona 只服务 cheat-seed
- 「跳过评论聚类，你凭感觉给我画一个」 → 拒绝。凭感觉画的是营销话术不是 persona。没评论数据就老实说"先去复盘"
- 「把 persona 写进 rubric_notes.md，省一个文件」 → 拒绝。rubric_notes.md 是 blind 白名单，写 persona（实绩派生）进去 = 实绩泄漏漏洞重演（见 observation-lifecycle.md 的 leak guard）

## Integration

- 上游：`cheat-retro` 每完成一篇复盘 → flag "已累计 N 篇复盘，可跑 /cheat-persona 刷新画像"
- 上游：`cheat-init` 创建空 audience.md 骨架；如导了 benchmark → 提示可 `/cheat-persona — seed-from-benchmark`
- 下游：`cheat-seed` Mode A/B/C 读 audience.md 作为"这个 persona 会在乎吗"的镜子
- 下游（phase 2 路线）：`cheat-recommend` persona-fit 排序；`cheat-status` persona 新鲜度 nag
- **隔离**：`cheat-score-blind` 硬禁读 audience.md（refusal_code `blocked_audience`）

## Known limitations

1. **评论 ≠ 全部受众**——留评论的是受众里最活跃的一小撮（沉默大多数不在数据里）。persona 偏向"会评论的人"，不是"所有看的人"
2. **平台评论可被污染**——水军 / 引战 / 跑题评论会进数据。cheat-persona 聚类时对明显异常值降权，但不能完全过滤
3. **persona 滞后于真实受众变化**——画像基于过去 N 篇的评论。受众结构变了，要等新复盘累积才反映
4. **不解决"我想要的受众 ≠ 我实际的受众"**——persona 只如实报告"现在谁在看"。想转向另一种受众是选题战略问题，cheat-persona 只提供"现状 vs 目标"的 gap，不替你做战略
