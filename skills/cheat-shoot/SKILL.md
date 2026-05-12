---
name: cheat-shoot
description: 登记一条视频已拍摄。**建 video folder + 询问实际拍摄稿是否与 scripts/<id>.md 一致 + buffer +1**。与 cheat-publish 配对：拍了进队列，发了出队列。触发词："拍了"/"拍了 X"/"shot"/"shot it"/"已拍 X"/"录完了"。
argument-hint: <scripts-path-or-id>
allowed-tools: Bash(*), Read, Write, Edit, Glob
---

# /cheat-shoot — 登记拍摄完成 + 建 video folder + (改稿则) 触发 v2 预测

把视频从"已写预测、未拍摄"状态推进到"已拍摄、未发布"状态。这一步：
1. **建 `videos/<同 id>/`** 目录（之前没有的话）
2. **询问用户**："实际拍摄时用的稿子和 `scripts/<id>.md` 一致吗？"
3. 算 diff——超过 V2_TRIGGER_THRESHOLD (默认 30%) → **delegate 到 `/cheat-predict — mode: v2`** 在原 prediction 文件 append `## 预测 v2` 段
4. 把 video folder 加进 state.shoots 队列，buffer +1

cheat-shoot 自己**不**写预测内容——所有预测落盘逻辑在 cheat-predict。cheat-shoot 只负责检测改稿 + 派发。

为什么单独一个 skill：
- buffer 警戒系统需要明确区分"拍了" vs "发了"。视频可以批量拍（一天拍 5 条），分散发（每天发 1 条）
- "实际拍摄稿" ≠ "pre-shoot 草稿"是常态。这一步是把 diff 显式化、触发 v2 重判、采集"用户改稿 pattern"信号的入口
- v2 预测 vs v1 预测的差异本身就是 rubric 升级证据——比如 v1 给 ER=4，v2 给 ER=5（用户改稿改高了 hook 强度），就告诉 rubric "这个用户的 ER 阈值跟我现在公式不一致"

## Overview

```
[用户：拍了 scripts/2026-05-04_abc123_停止期待.md]
  ↓
[Phase 0: 解析路径 + 验证 prediction 已存在]
  ↓
[Phase 1: 检查是否已登记（避免重复）]
  ↓
[Phase 2: 建 videos/<id>/ + 询问"实际拍摄稿一致吗？"]
  ↓
[Phase 3: 写 videos/<id>/script.md]
  ↓
[Phase 4: append state.shoots]
  ↓
[Phase 5: 输出 buffer 状态]
```

## Constants

- **REQUIRE_PREDICTION = true** — 拍前必须先有 v1 prediction 文件
- **V2_TRIGGER_THRESHOLD = 0.30** — normalize 后 char-level diff 超过 30% → 默认建议 v2 重判；低于 30% 询问用户是否仍要 v2
- **DIFF_METRIC = char_levenshtein_normalized**（**默认**）—— 通过 [`tools/diff_pct.py`](../../tools/diff_pct.py) 调用：先 normalize（去 markdown header / 分隔线 / 列表标记 / 装饰标点 / 折叠所有空白），再算 char-level Levenshtein / max(len_a, len_b)。preferred backend `rapidfuzz`，fallback `difflib.SequenceMatcher`（stdlib，永远可用）。**旧版 line-level 在口语化转录场景误报严重**（draft 长 markdown 句 vs whisper 转录的短断句，内容几乎不变但 line-level 算出 ~200% diff）—— PR #14 修复
- **DIFF_METRIC=lines** —— legacy fallback：当 python3 完全不可用或 tools/diff_pct.py 找不到时降级到 `diff -u | grep '^[+-]' | wc -l` 算法

## Inputs

| 必填 | 来源 |
|---|---|
| `<scripts-path-or-id>` | 用户参数；缺失则询问 |
| `.cheat-state.json` | 状态文件 |
| `scripts/*.md` | pre-shoot 草稿 |
| `predictions/*.md` | 验证对应预测存在 |

## Workflow

### Phase 0：解析 + 验证

1. 解析用户给的路径——支持几种形态：
   - 完整路径 `scripts/2026-05-04_abc123_停止期待.md`
   - 简写 `2026-05-04_abc123_停止期待`
   - id 简写 `abc123` → glob `scripts/*_abc123_*.md` 找匹配
2. 验证 `scripts/<id>.md` 存在：不存在 → 报错"找不到 pre-shoot 草稿"
3. 验证有对应 prediction `predictions/<同名>.md`：
   - 不存在 → **拒绝登记**，提示"先跑 /cheat-predict 写预测，否则违反盲预测原则——你不能拍完才写预测，那等于事后看了画面写"
   - 存在 → 通过

### Phase 1：检查重复

读 `.cheat-state.json`，检查 `shoots[]` 是否已含此 id：
- 已存在 → 警告"已登记过（X 天前）。是要重新登记，还是要用 /cheat-publish 发布？"
- 不存在 → 进入 Phase 2

### Phase 2：建 video folder + 询问稿子一致性

1. 建目录 `videos/<id>_<short>/`（同 scripts/ + predictions/ 的命名）
2. **询问用户**：

```
拍 「<title>」 的时候，你实际用的稿子和 scripts/<id>.md 一致吗？

a) 一致——按草稿拍的
b) 改了一些——你能给我看下实际拍摄稿吗？我重新打分一次（v2 预测）
c) 大改了，基本是另一条 → 走 _redo 流程：
   scripts/<id>_redo.md → 重新 cheat-predict → 再 cheat-shoot（原 prediction 留档脱钩）
```

### Phase 3：写 videos/<id>/script.md + (b 路径) 触发 v2 预测

**a 路径（一致）**：
- `cp scripts/<id>.md → videos/<id>/script.md`
- `script_consistency = consistent`
- 不重判，进 Phase 4

**b 路径（改了）**：
1. 询问用户实际拍摄稿——粘贴文本 / 文件路径 / 转录文件
2. 若用户提供 → 写入 `videos/<id>/script.md`
3. 若用户没保留（即兴）→ 标 `script_lost`，写占位文件 + 警告"v2 重判跳过——下次建议留稿（哪怕 voice memo 转录）"，进 Phase 4
4. 提供了的话：算 diff
   ```bash
   # 解析 cheat-on-content 源码根（cheat-shoot 是 symlink 装的）
   SKILL_REAL="$(readlink -f ~/.claude/skills/cheat-shoot 2>/dev/null || readlink ~/.claude/skills/cheat-shoot 2>/dev/null)"
   if [[ -n "$SKILL_REAL" ]]; then
     REPO_ROOT="$(cd "$SKILL_REAL/../.." && pwd)"
     DIFF_TOOL="$REPO_ROOT/tools/diff_pct.py"
   fi

   if [[ -n "${DIFF_TOOL:-}" && -f "$DIFF_TOOL" ]] && command -v python3 >/dev/null 2>&1; then
     # 默认 char-level Levenshtein on normalized text（rapidfuzz preferred, difflib fallback）
     diff_pct=$(python3 "$DIFF_TOOL" "scripts/<id>.md" "videos/<id>/script.md")
   else
     # legacy line-level fallback——只在 python3 或 diff_pct.py 都不可用时用
     added=$(diff -u scripts/<id>.md videos/<id>/script.md | grep -c '^+')
     removed=$(diff -u scripts/<id>.md videos/<id>/script.md | grep -c '^-')
     total_orig=$(wc -l < scripts/<id>.md)
     diff_pct=$(( (added + removed) * 100 / total_orig ))
     echo "⚠️  fallback 到 line-level diff——口语化转录会 inflate diff_pct，可能误触发 v2"
   fi
   ```

   **为什么 normalize + char-level**：line-level diff 在创作者真实场景（draft 是 markdown 长句、拍摄稿是 whisper 转录的口语化短行）算出 ~200% 差异但内容几乎不变。char-level Levenshtein 在 normalize 后稳定反映**内容**差异，而非格式差异。详见 [`tools/diff_pct.py`](../../tools/diff_pct.py) + `tools/diff_pct_test.sh`（3 fixture 在两个 backend 上全过）。
5. **判定 v2 触发**：
   - `diff_pct >= 30` → 默认建议 v2 重判，**主动调用** `/cheat-predict — mode: v2 — prediction-file: predictions/<id>.md` 传 `videos/<id>/script.md` 作 input。cheat-predict 走 v2 模式 append `## 预测 v2`
   - `diff_pct < 30` → 询问用户："只改了 N% 的内容，要重判吗？默认不（v1 预测仍有效）"。用户说要 → 同上调用；用户说不 → 跳过 v2，继续 Phase 4
6. cheat-predict 完成 v2 落盘后，控制权回到 cheat-shoot 进 Phase 4

**c 路径（大改）**：
- 不写 `videos/<id>/script.md`，提示走 `_redo` 流程
- 退出 cheat-shoot（不进 Phase 4）

### Phase 4：state 更新

```json
{
  "shoots": [
    ...,
    {
      "video_folder": "videos/2026-05-04_abc123_停止期待/",
      "prediction_file": "predictions/2026-05-04_abc123_停止期待.md",
      "scripts_path": "scripts/2026-05-04_abc123_停止期待.md",
      "shot_at": "<ISO timestamp>",
      "script_consistency": "consistent" | "modified" | "lost",
      "script_diff_pct": <0-100 int 或 null>,
      "v2_prediction_written": <true/false>,
      "script_hash_at_shoot": "<sha256:12 of videos/<id>/script.md>"
    }
  ]
}
```

`v2_prediction_written: true` 表示 prediction 文件里现在有 `## 预测 v2` 段，cheat-retro 应读 v2 算偏差；`false` 表示沿用 v1。

### Phase 5：输出 buffer 状态

读完 state 后立即算 buffer + 颜色（按 [cadence-protocol.md](../../shared-references/cadence-protocol.md) 的派生规则）：

```
✅ 已登记拍摄：videos/2026-05-04_abc123_停止期待/
   预测文件：predictions/2026-05-04_abc123_停止期待.md

📦 当前 buffer：3 篇（🟢 绿色，正常）
   按你的 cadence（隔日更）= 6 天 buffer，节奏稳定。

下一步：拍其他候选 / 等下个发布日 / 不动
```

如果 buffer 颜色变了（如从绿到蓝）→ 高亮提醒：
```
📦 当前 buffer：6 篇（🔵 蓝色，**积压**）
⚠️  建议暂停拍摄，全力发布存货 + 复盘。
   按你的 cadence（日更）= 6 天预备，已超过健康上限。
```

## Key Rules

1. **不写 prediction**——拍了 ≠ 发了。预测在 /cheat-predict 锁，拍只是事件
2. **不动 video folder 内容**——script.md / draft-v0.md 都不改
3. **必须先有 prediction**——否则违反盲预测（拍完看了画面再写预测 = 数据泄漏到判断）
4. **buffer 计算实时**——每次 shoot / publish 后立刻重算，state.shoots 是真值
5. **支持批量**：用户可以一天连说 "拍了 X / 拍了 Y / 拍了 Z" 三次连续登记

## Refusals

- 「拍了 X，但我从来没跑过 cheat-predict」 → 拒绝。v1 预测**必须拍前写**——拍完才写预测会被画面诱导事后修改。请先 /cheat-predict 写 v1 再来 /cheat-shoot。（v2 重判是另一回事——v1 已存在 + 拍后改稿才允许）
- 「我没有 video folder，我直接拍的」 → 询问用户 → 帮他建 video folder + 提示下次走完整流程；登记时标 `ad_hoc: true`
- 「我改稿了但你直接覆盖 v1 吧，别留 v2 段」 → 拒绝。v1 是档案，v2 才是当前判断——append 不覆盖。两段一起留是 rubric 学习的关键证据

## Integration

- 上游：`/cheat-predict` 写完 prediction → 用户拍摄 → `/cheat-shoot` 登记
- 下游：`/cheat-publish` 发布时把对应项从 state.shoots 移除
- `/cheat-status` 看板的 buffer 数字直接来自 `state.shoots.length`
- `/cheat-recommend` 看 buffer 颜色调推荐策略
- SessionStart hook 看 buffer 颜色决定报告第一行

## state.shoots 数据结构

```json
{
  "shoots": [
    {
      "video_folder": "videos/2026-05-04_abc123_停止期待/",
      "prediction_file": "predictions/2026-05-04_abc123_停止期待.md",
      "shot_at": "2026-05-04T18:30:00+08:00",
      "ad_hoc": false  // true if user shot without going through full flow
    }
  ]
}
```

按 `shot_at` 升序——最早拍的在前面。`/cheat-status` 显示最早一项的 days-since-shoot 警告（避免有视频拍了 30 天没发）。
