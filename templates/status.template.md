# 状态

> 本文件由 `/cheat-status` 维护——每次跑 status 都会更新。手改无意义。

---

**最近更新**: [INIT-DATE]
**模式**: cold-start
**内容形态**: opinion-video
**当前 rubric**: v0
**校准样本**: 0 / 5（解锁第一次 bump 的门槛）

---

## 进度条

```
[░░░░░░░░░░░░░░░░░░░░] 0 / 30 → SQLite 升级建议门槛
[░░░░░░░░░░░░░░░░░░░░] 0 / 5  → 脱离 cold-start 门槛
```

## 🎬 待办

无——你刚初始化，先写第一篇稿子吧。

## 🔥 候选池

无（cold-start 期默认状态）。
- 想试试热点抓取 → 说 `抓热点`
- 想手动建池 → 编辑 `candidates.md`

## 📈 健康度

- `rubric_notes.md`: [X 行]（健康，<600 警戒线）
- prediction guard: [✅ enforced (<hooks_backend>) / ⚠️ honor-system；scripts=<guard_scripts_installed>]
- external audit configured: [✅ / ❌]

## 下一步建议

1. **写一份稿子**（任何观点视频脚本即可）
2. 跑 `打分这篇 path/to/draft.md` 看 rubric 给的初始评分
3. 准备发布前跑 `启动预测`
4. 发布后说 `已发布 https://...`
5. T+3 天跑 `复盘 path/to/draft.md`

第 5 篇之后会解锁 `/cheat-bump`，rubric 才真正开始校准。

完整工作流见 `WORKFLOW.md`。
