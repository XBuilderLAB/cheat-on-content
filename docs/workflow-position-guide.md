# 工作流位置追踪功能 — 使用与维护指南

## 功能说明

每次启动 Claude Code 会话时，SessionStart hook 自动显示当前处于工作流的哪一步以及下一步该做什么：

```
🔄 当前位置：✍️ 第 3 步：选题写稿
➡️ 下一步：选一个话题开始 → /cheat-seed
💡 说'今天 AI 圈有什么'可调用 aihot 获取 AI 热点
```

## 补丁文件

`docs/workflow-position.patch` 包含对 `hooks/session-start.sh` 的修改。

---

## 方案 A：git pull 后重新应用补丁

当上游仓库更新后，用以下步骤恢复功能：

```bash
# 1. 拉取最新代码
git pull

# 2. 应用补丁（如果有冲突会提示）
git apply docs/workflow-position.patch

# 3. 如果有冲突，手动解决后：
git add hooks/session-start.sh

# 4. 重新安装 hook 到 .cheat-hooks/
cp hooks/session-start.sh .cheat-hooks/session-start.sh
```

### 常见问题

**补丁应用失败（conflict）**：说明上游修改了同一区域。手动编辑 `hooks/session-start.sh`，按补丁内容重新添加工作流位置逻辑。

**jq 未安装**：hook 会静默跳过。安装 jq：
```bash
winget install jqlang.jq
```

---

## 方案 B：提交 PR 到上游仓库

### 步骤 1：Fork 仓库

1. 访问 https://github.com/XBuilderLAB/cheat-on-content
2. 点击右上角 **Fork** 按钮
3. Fork 到你自己的 GitHub 账号

### 步骤 2：克隆你的 Fork

```bash
git clone https://github.com/<你的用户名>/cheat-on-content.git
cd cheat-on-content
```

### 步骤 3：创建功能分支

```bash
git checkout -b feat/workflow-position-tracking
```

### 步骤 4：应用补丁

```bash
git apply docs/workflow-position.patch
```

### 步骤 5：提交并推送

```bash
git add hooks/session-start.sh
git commit -m "feat: add workflow position tracking to SessionStart hook

- Show current step in workflow cycle (导入对标/选题写稿/评分预测/拍摄/发布/复盘/升级公式)
- Show next recommended action with specific command
- Show contextual tips (aihot for topics, humanizer-zh for drafts, etc.)
- Priority-ordered detection: retro (time-sensitive) > publish > shoot > bump > seed"
```

### 步骤 6：推送并创建 PR

```bash
git push origin feat/workflow-position-tracking
```

然后在 GitHub 上：
1. 访问你的 fork 页面
2. 点击 **Compare & pull request**
3. 填写 PR 描述（见下方模板）
4. 点击 **Create pull request**

### PR 描述模板

```markdown
## Summary

在 SessionStart hook 中增加工作流位置追踪功能，每次开会话自动显示：
- 当前处于工作流的哪一步（带序号和 emoji）
- 下一步推荐动作（带具体命令）
- 上下文提示（如 aihot 热点、humanizer-zh 去 AI 味等）

## Changes

- `hooks/session-start.sh`：新增读取 `benchmark_status`、`in_progress_session`、`last_bump_at`、`consecutive_directional_errors` 字段；新增工作流位置判断逻辑和输出

## Workflow Steps

| 步骤 | 条件 | 显示 |
|------|------|------|
| 📚 导入对标 | benchmark_status != imported, calibration_samples == 0 | /cheat-learn-from |
| 📊 复盘 | pending_retros 有到期项 | /cheat-retro |
| 📤 发布 | buffer > 0 | /cheat-publish |
| 🎬 拍摄 | in_progress_session 存在 | /cheat-shoot |
| 🔧 升级公式 | samples >= 5 未 bump 或连续 3+ 同向偏差 | /cheat-bump |
| ✍️ 选题写稿 | 默认 | /cheat-seed |

## Testing

```bash
# 应用补丁后测试
bash .cheat-hooks/session-start.sh
```

## Related

- 补丁文件：`docs/workflow-position.patch`
- 使用指南：`docs/workflow-position-guide.md`
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `hooks/session-start.sh` | 源文件（git 追踪），补丁应用目标 |
| `.cheat-hooks/session-start.sh` | 安装副本（git 忽略），从源文件复制 |
| `docs/workflow-position.patch` | 补丁文件 |
| `docs/workflow-position-guide.md` | 本文档 |
