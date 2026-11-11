---
name: cheat-publish
description: 登记一篇内容已发布，把 URL/平台 ID/发布时间写入对应预测文件 header 和 state file。这是一个轻量动作——只更新元数据，**不动预测段任何字符**。触发词："已发布"/"I shipped"/"发布链接是 X"/"刚发完 [url]"/"publish registered"。
argument-hint: "<prediction-file-or-url> [— platform: youtube|bilibili|douyin|...]"
allowed-tools: Bash(*), Read, Edit, Glob
---

# /cheat-publish — 发布登记

把作品的发布元数据（URL、发布时间、平台）补到预测文件 header 与 state file。**禁止改预测段**——hook 会拦。

## Overview

```
[用户：已发布 https://...]
  ↓
[Phase 0: 找到对应的预测文件]   ← 通过 in_progress_session 或匹配
  ↓
[Phase 1: 解析 URL → 平台/发布时间]
  ↓
[Phase 2: 更新 prediction 文件 header（仅 metadata 段）]
  ↓
[Phase 3: 更新 .cheat-state.json，清除 in_progress_session]
```

## Constants

- **AUTO_DETECT_PLATFORM = true** — 从 URL 模式自动识别平台
- **VERIFY_BLIND = true** — 提醒用户：从此刻起看到任何后续数据都会破坏盲度声明的诚信

## Inputs

| 必填 | 来源 |
|---|---|
| `<prediction-file>` 或 URL | 用户参数；缺失则用 `.cheat-state.json` 的 `in_progress_session.file` |
| `.cheat-state.json` | 用户项目根 |

## Workflow

### Phase 0: 找到对应的预测文件

按优先级：
1. 用户参数明确给了 prediction 文件路径 → 用它
2. 用户参数只给了 URL → 读 `.cheat-state.json` 的 `in_progress_session.file`
3. 都没有 → 列出 `predictions/*.md` 中 header 没填 `published_at` 的文件，让用户选

**警告路径**：若 `in_progress_session.file` 与用户给的 URL 时间差超过 14 天 → 提示"这个预测写于很久之前，确认是这篇？"

### Phase 1: 解析平台

`AUTO_DETECT_PLATFORM=true` 时按 URL 模式：

| URL 模式 | 平台 |
|---|---|
| `youtube.com/*` `youtu.be/*` | youtube |
| `bilibili.com/*` `b23.tv/*` | bilibili |
| `douyin.com/*` `iesdouyin.com/*` `v.douyin.com/*` | douyin |
| `xiaohongshu.com/*` `xhslink.com/*` | xhs |
| `mp.weixin.qq.com/*` | wechat |
| `substack.com/*` `*.substack.com/*` | substack |
| `medium.com/*` `*.medium.com/*` | medium |
| `twitter.com/*` `x.com/*` | twitter |
| 其他 | unknown — 询问用户 |

发布时间获取：
- 不强求自动抓——绝大多数平台需要登录态
- 询问用户："发布时间是？（默认：现在）" → 接受 ISO 8601 或自然语言（"今天 14:30" / "20 分钟前"）
- 解析失败 → 用 now()

### Phase 2: 更新 prediction 文件 header

**绝不**触碰 `## 预测` 段及之后。只动文件最顶部的 metadata 块。

读文件，定位到 metadata 块（在第一个 `##` 之前的所有行）。检查是否已有这些字段——有则警告"已登记过"并询问是否覆盖；无则追加：

```markdown
**Published at**: 2026-05-04T14:32:00+08:00
**Platform**: douyin
**URL**: https://v.douyin.com/abc123
**Video Folder**: videos/2026-05-04_a3f2c1d4_停止期待/
**Aweme ID**: 7234567890123456789  (douyin / 视频号 等需要的 platform-specific ID)
```

**关于 platform-specific ID**：
- 抖音：从 URL 短链 resolve 后提取 `aweme_id`（v.douyin.com → 重定向后含 modal_id 或 item_id 参数）
- B 站：BV 号
- 小红书：note_id
- YouTube：v= 参数后的 video_id

如果用户给的是分享短链（无法立刻 resolve）→ 标 `Aweme ID: pending`，下次 `/cheat-retro` 时由 adapter 解析。

**video folder 处理**：到 cheat-publish 这一步，对应的 `videos/<id>/` 目录**应该已经由 cheat-shoot 创建**（含 script.md）。

- 如 video folder 不存在 → 警告"你跳过了 cheat-shoot？建议先跑 cheat-shoot 把拍摄稿登记进 video folder 再发"，**询问用户是否跳过登记直接发**：
  - 是 → 自动建一个 video folder（fallback），但不询问稿子一致性，标 `ad_hoc_publish: true`
  - 否 → 让用户先跑 cheat-shoot 再回来 publish

用 Edit 工具（不是 Write 重写整个文件）。

**hook 行为预期**：因为只动 metadata 段（在 `## 预测` 之前），immutability hook 应放行。如果 hook 误拦 → 报告 bug，**不要绕过 hook**。

### Phase 3: 更新 state file

```json
{
  "in_progress_session": null,
  "last_published_at": "<ISO timestamp>",
  "last_published_file": "predictions/<filename>",
  "last_published_video_folder": "videos/<...>/",
  "last_published_platform_id": "<aweme_id 或 BV 号 等>",
  "pending_retros": [
    "predictions/<filename>"
  ],
  "shoots": [
    // 移除 video_folder 匹配本次发布的项；buffer -1
  ]
}
```

**`shoots` 队列处理**（buffer 跟踪关键）：
1. 读 state.shoots[]
2. 找 `video_folder == 本次发布的 video_folder` 的项 → 移除
3. 如果没找到 → 警告"buffer 队列里没有这条视频。是直接发布没经过 /cheat-shoot 吗？"——不阻塞，但提示用户下次走 /cheat-shoot 让 buffer 跟踪准确

`last_published_platform_id` 是 cheat-retro 调 adapter 时的输入——如 douyin-session 需要 aweme_id 直接抓数据。

`pending_retros` 是待复盘列表——`cheat-status` 会基于这个列表 + RETRO_WINDOW_DAYS 显示"今天该复盘哪些"。

### Phase 4: 提醒 + 下一步 + buffer 状态

```
✅ 登记完成：predictions/2026-05-04_a3f2c1d4e5b6_停止期待.md
   - Published at: 2026-05-04 14:32
   - Platform: douyin
   - URL: https://v.douyin.com/abc123

📦 Buffer：N 篇（颜色 + 含义）
   按你的 cadence（X）= N×X 天 buffer
   [如颜色变了，提示"现在该去拍/暂停拍"]

⚠️  从此刻起，你看到任何关于这条作品的播放/点赞/评论数据
    都会破坏盲度声明的诚信。如果不小心看到，告诉我——
    我会在文件里追加一个 integrity warning。

📅 计划复盘：T+3d，约 2026-05-07
   到时间说："复盘 predictions/2026-05-04_..."
```

Buffer 颜色由 [shared-references/cadence-protocol.md](../../shared-references/cadence-protocol.md) 派生。如本次发布让 buffer 跌入红色（断更风险）→ 高亮警告"今天必须再拍 ≥1 条"。

## Key Rules

1. **不动预测段**。即使是修复笔误，也不允许在 publish 时改预测段
2. **不抓数据**。publish 是登记动作，不是数据回收（那是 cheat-retro 的活）
3. **state 字段名固定**。`pending_retros` / `last_published_at` 是其他子 skill（特别是 cheat-status / cheat-retro）依赖的契约
4. **平台未知不强报**。无法识别 → 询问用户，允许 `platform: other` 作为兜底
5. **重复登记需明示**。已有 published_at → 询问"覆盖？"，绝不静默覆盖

## Refusals

- 「我顺手把预测段也改一下」 → 拒绝。请走 `_redo.md` 路径
- 「URL 我等会儿补，先把发布时间记上」 → 允许：URL 字段可后续追加；published_at + platform 必填
- 「跳过 metadata 更新，直接清 in_progress_session」 → 拒绝。元数据是复盘时的关键上下文（特别是 platform 决定数据回收用哪个 adapter）

## Integration

- 上游：`/cheat-predict`（写出 prediction 文件并设 in_progress_session）
- 下游：T+RETRO_WINDOW_DAYS 后 → `/cheat-retro`
- `cheat-status` 用 `pending_retros` 字段计算"今天该复盘哪些"
- 平台字段被 `cheat-retro` 用来路由到对应的 perf-data adapter（manual-paste / youtube-data-api / 等）
