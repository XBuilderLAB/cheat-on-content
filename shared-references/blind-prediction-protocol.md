# Blind Prediction Protocol（盲预测协议）

被这些子 skill 引用：`cheat-predict`、`cheat-retro`、主 SKILL.md。

这是项目原则 #1 的完整规范。任何子 skill 在写预测前都必须执行本协议。

---

## 核心定义

**盲预测**：在预测者（人或模型）看到任何关于该作品发布后真实表现数据**之前**完成的预测。

预测一旦写入 `predictions/*.md`，从第一个 `## ` 标题到 `## 复盘` 之前的正文即为 **immutable**。这包括输入快照（当时打的分数）、预测 v1/v2、推理因素、锚点对比、反事实场景和关键校准假设。第一个 `## ` 之前的 header 仍可改（发布登记写在那里）。只能往 `## 复盘` 段追加，不能改预测正文的任何字符。

---

## "见过数据"的边界（关键，常被违反）

下列任一条件成立 → 已不再 blind，**禁止写预测**：

| 信息 | 是否破坏 blind | 例外 |
|---|---|---|
| 该作品任何平台的播放数 / 阅读数 | ✗ 破坏 | 无 |
| 该作品的点赞 / 评论 / 转发数 | ✗ 破坏 | 无 |
| 该作品的具体评论内容 | ✗ 破坏 | 无 |
| 该作品的算法推荐位 / 热门榜位置 | ✗ 破坏 | 无 |
| 该作品发布后的截图 / 后台数据 | ✗ 破坏 | 无 |
| **同期发布的其他人**作品的表现 | ○ 不破坏 | — |
| **历史上类似主题**作品的表现 | ○ 不破坏（这正是锚点对比要做的） | — |
| 该作品**发布前**的稿子内容 | ○ 不破坏 | 这是预测的输入 |
| 用户口述的"我感觉这条还行" | △ 谨慎 | 用户的主观感觉不算"数据"，但要在预测里标注用户偏见 |

**判断捷径**：只要这条信息**只能在作品发布后才能获得**，就算"数据"。

---

## 预测者必须主动声明的情况

子 skill 在启动 `cheat-predict` 前，必须自检并向用户**主动声明**：

1. **作品已发布超过 RETRO_WINDOW_DAYS 天**（默认 3 天）→ 必须拒绝写"预测"，改记为 `**Reconstructed retrospective**`，明确标注非预测
2. **作品已发布但 < RETRO_WINDOW_DAYS 天，用户尚未透露任何数据**→ 允许 blind 预测，但在文件头部标记 `published_before_prediction: true` + `blind_status: confirmed_no_data_seen`
3. **用户在对话里已粘贴了任何后续数据**→ 同 #1 处理，记为 reconstructed

`BLIND_CHECK=strict`（默认）：上述任何破坏条件命中，**拒绝执行**。
`BLIND_CHECK=lenient`：仅警告 + 强制标注，允许继续——只用于离线测试或学术演练，**不推荐用于真实校准**。

---

## Immutable 的工程边界

预测正文的不可修改是**用户体验承诺**，由 hook 层强制：

- `hooks/prediction-immutability.sh` 在 PreToolUse(Edit|Write|MultiEdit) 上检查 `predictions/` 下含 `## 预测` 的文件
- **锁定区** = 第一个 `## ` 标题到 `## 复盘` 之前。改动与锁定区重叠 → **exit 2**。Claude Code 只在退出码 2 时拦截工具调用；退出码 1 是非阻塞错误，编辑仍会执行（[Hooks](https://code.claude.com/docs/en/hooks)）
- 改 header（第一个 `## ` 之前）、用 old_string 从 `## 复盘` 这一行开始插入 `## 预测 v2`、在 `## 复盘` 里追加 → 放行
- 对已存在的预测文件用 Write 整体覆盖 → exit 2

**禁止的"绕开"模式**（子 skill 必须拒绝）：
- "把预测段重写得更准一点" → 拒绝。如有正当理由重做，创建新文件 `<原文件名>_redo.md`，原文件保留
- "我的概率分布写错了 0.5%，让我改一下" → 拒绝。在复盘段追加 `修正：原概率分布 X% 应为 Y%，于 <date> 发现笔误`
- "我前面没考虑 SR=4，重打一下分" → 拒绝。同上路径

唯一允许编辑预测段的场景：**纯 markdown 排版错误**（标题层级错误、列表 bullet 格式错），且用户明确说明这是格式修复。这种情况 hook 仍会阻塞，需要用户显式 bypass（手动设置环境变量 `CHEAT_BYPASS_IMMUTABILITY=1` 单次）——bypass 应在 git history 留痕。

---

## 文件名约定（**三处一致**）

一个内容三处文件，**用同一组 `<date>_<id>_<short>` 命名**：

```
scripts/<date>_<id>_<short>.md        ← pre-shoot 草稿（cheat-seed 写或用户写）
predictions/<date>_<id>_<short>.md    ← immutable 预测（cheat-predict 写）
videos/<date>_<id>_<short>/           ← 拍后才建（cheat-shoot 创建）
  ├── script.md                       ← 用户提供的最终拍摄稿
  └── report.md                       ← T+3d 数据（cheat-retro 写）
```

- `<date>`：**草稿首次落盘日期**（即 `scripts/<id>.md` 的创建日），不是预测日 / 拍摄日 / 发布日。理由：保持 ID 稳定——草稿大改后 hash 变了仍想保持文件可追溯
- `<id>`：12 位 sha256 前缀，对**草稿首次落盘的内容**做 hash。用户 edit 草稿后**不变**——便于跨文件引用
- `<short>`：3-8 字中文或英文短名，便于人类辨识

Reconstructed 重做：在 `<short>` 后加 `_redo`，三处都加：
- `scripts/<date>_<id>_<short>_redo.md`
- `predictions/<date>_<id>_<short>_redo.md`
- `videos/<date>_<id>_<short>_redo/`

原文件保留（不删）。

---

## 子 skill 必须做的检查清单

`cheat-predict` 启动时：
1. 读 `BLIND_CHECK` 常量
2. 询问用户该作品当前发布状态（未发 / 已发 < RETRO_WINDOW_DAYS / 已发 ≥ RETRO_WINDOW_DAYS）
3. 询问对话历史里是否提到过该作品的任何后续数据（如有，自检对话里有没有 "播放/阅读/点赞/评论" 等关键词）
4. 若 #2 或 #3 命中破坏条件 → 按 `BLIND_CHECK` 模式处理
5. 通过后才允许写 `predictions/*.md`

`cheat-retro` 启动时：
1. 读目标 prediction 文件
2. **先在内存里 cache 住 `## 预测` 段**——后续任何对该文件的写都必须先校验该段未变
3. 抓数据 → 追加 `## 复盘` 段
4. 写完后**再次校验**：写入后该文件的 `## 预测` 段哈希应等于步骤 2 的 cache。不等 → 报错并回滚

主 SKILL.md：
- 用户说出"重写预测" / "改一下预测段" / "你之前预测错了我帮你改" 时，**直接拒绝并解释**，引导改用 `_redo.md` 路径

---

## 异常状态处理

| 场景 | 处理 |
|---|---|
| 预测文件不小心被人手编辑了预测段 | 不自动回滚（破坏更大）。下次 `cheat-retro` 检测到不一致 → 在复盘段追加 `**Integrity warning**: 预测段于 <ISO timestamp> 被外部修改，无法保证盲度`，校准价值降级为"参考"，不计入 bump 校准池 |
| 预测文件遗失 / 被删 | git log 找回。找不到 → 在 `rubric_notes.md` 记录"<id> 预测文件遗失，校准池缺该样本" |
| 用户原本是 cold-start，半路想"补"已发作品的预测 | 一律记为 `**Reconstructed retrospective**`，不计入校准池——这是补的不是预测。可作为"观察"记录到 `rubric_notes.md` |

---

## 反模式（必须拒绝的请求）

- 「帮我预测一下，但我先告诉你播放量你来反推就行」 → 拒绝。直接破坏盲度
- 「这条已经发了 5 天数据出来了，但你假装没看到，给我做个预测看会不会准」 → 拒绝。请改用 `_redo.md` 走 reconstructed 路径
- 「上次预测算错了，帮我把概率分布改一下」 → 拒绝。在复盘段说明
- 「能不能跳过 blind check 我有特殊原因」 → 询问原因；只有"格式修复"是合法的 bypass 理由

---

## Why（为什么这套这么严）

盲预测是整个 cheat-on-content 校准循环的**唯一信号源**。一旦预测段被事后修改，所有"哪个维度被验证 / 推翻"的判断都失去基线——你不知道当初是真预测对了，还是事后改对了。

校准价值 = 预测精度 × 预测可信度。
- 预测精度可以靠 rubric 升级慢慢提升。
- 预测可信度一旦破坏不可恢复——**这是为什么 immutability 是 hook 层强制，不是君子协定**。
