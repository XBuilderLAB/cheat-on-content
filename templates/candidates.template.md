# 候选选题池

> **本文件由 `/cheat-trends` 写入热点抓取结果，由 `/cheat-recommend` 读取并排序。
> 也可手动编辑——把候选标题贴成 H3 entry 即可。**
>
> Schema 完整规范：[shared-references/candidate-schema.md](../cheat-on-content/shared-references/candidate-schema.md)。

---

## 使用说明（首次见到本文件请读）

每个候选项是一个 H3 entry（`### [tier] 标题`），下面带 metadata bullets。最简版本只需要 title 一行——`/cheat-recommend` 会自动调 `/cheat-score` 给未打分的 entry 粗打分。

### 字段含义速查

- **id**：12 位 hash，用于跨文件去重。手加 entry 留空，`/cheat-trends` 自动算
- **source**：来源标识，格式 `<adapter-type>:<source-name>`
- **snapshot_at**：抓取 / 录入时间（ISO 8601 或 YYYY-MM-DD）
- **tier**：粗分类 `tier1` / `tier2` / `tier3` / `skip` / `risky` / `done`
- **read_status**：`unread` / `skimmed` / `deep_read` / `done`
- **composite (vN)**：当前 rubric 下的综合分（粗打分，**不是预测**）
- **predicted bucket**：粗预测桶（粗略，仅用于排序）
- **note**：备注（如"等节点再发"、"待重读"、"风险议题"）

### 手加 entry 的最简格式

```markdown
### 标题
- snapshot_at: 2026-05-04
```

剩下的字段会被 `/cheat-recommend` 在下次调用时补全（自动调 `/cheat-score`）。

---

## 候选项

> 删除下方所有示例 entry，从你的真实候选开始累计。
> 示例展示的是「视频分析」项目当前 candidates pool 的真实样本（已脱敏）。

### [tier1] "为你好"高密度家庭体系

- **id**: e7c2f1a4d3b6
- **source**: pool:manual
- **snapshot_at**: 2026-05-01
- **tier**: tier1
- **read_status**: deep_read
- **composite (v2)**: 9.18 — ER=5 HP=5 QL=4 NA=4 AB=5 SR=5 SAT=4
- **predicted bucket**: 30-100w（中枢 ~60w）
- **note**: 议题厚重，不适合连续 2 篇都打这种

> 「为你好」三个字是中国家庭对子女控制的最高级修辞，背后是一整套「我比你更懂你的需要」的认知体系。
> [snapshot_text 段——deep_read 后的精读笔记，可选]

---

### [tier1] 哈哈长度

- **id**: 229f5798b1d8
- **source**: pool:manual
- **snapshot_at**: 2026-05-03
- **tier**: tier1
- **read_status**: deep_read
- **composite (v2)**: 8.71 — ER=3 HP=5 QL=5 NA=4 AB=5 SR=4 SAT=5
- **predicted bucket**: 30-100w（中枢 ~55w）
- **note**: v2.1 候选维度 MS+TS 双 5——v2.1 升级的关键 A/B 验证样本

> 社交媒体中"哈哈"长度与沟通意愿的非线性关系研究。
> 与谁问你了构成完美 A/B 对照——同 ER/HP/QL/SR/SAT，差异仅在 MS 和 TS 各 +3。

---

### [tier1] 弗洛伊德的性压抑哲学

- **id**: 8c4d92e1f0b3
- **source**: trend:manual-paste
- **snapshot_at**: 2026-04-28
- **tier**: tier1
- **read_status**: skimmed
- **composite (v2)**: 9.53 — ER=4 HP=5 QL=5 NA=4 AB=5 SR=5 SAT=5
- **predicted bucket**: 30-100w（中枢 ~70w）
- **note**: **risky**（性议题），需评估账号 risk tolerance

> 弗洛伊德的核心理论被 21 世纪心理学界否定，但他对「压抑→症状」的描述在亲密关系实务里仍有解释力。

---

### [skip] [示例 - 已跳过的候选]

- **id**: a1b2c3d4e5f6
- **source**: trend:hackernews
- **snapshot_at**: 2026-05-02
- **tier**: skip
- **rejected_at**: 2026-05-02
- **rejected_reason**: 与本账号议题不符（纯技术新闻）

---

### [done] [示例 - 已发布的候选]

- **id**: ab61ed09f0a1
- **source**: pool:manual
- **snapshot_at**: 2026-04-22
- **tier**: done
- **read_status**: done
- **composite (v2)**: 8.24
- **published_at**: 2026-04-24
- **predictions_file**: predictions/2026-04-24_ab61ed09_停止期待.md

> done tier 的 entry **不出现在 `/cheat-recommend` 的输出**——已发过的不再推。

---

## 维护建议

- **保持 < 100 条 active**（tier1+tier2+tier3，不含 skip/done）。超过这个数排序不稳
- **定期清理 skip**：超过 6 个月的 skip 可以从 `.cheat-cache/trends-history.jsonl` 自动剔除（`/cheat-trends` 重复抓到时会再出现）
- **risky 标签认真用**：`/cheat-recommend` 会高亮 risky 项让你二次确认；不要把所有"有点争议"都标 risky，会麻木
