# Active Context - cheat-on-content Agent Teams Integration

## 当前状态
正在初始化集成工作。已分析项目结构，确定了“Agent Teams 协作打分与预测架构”的设计，并写好了实施计划 `implementation_plan.md` 和任务跟踪 `task.md`。

## 上次做了什么
- 浏览并理解了项目的 README.md, SKILL.md, 以及打分、预测、升级相关的子技能定义。
- 确认了 `tools/` 目录下除 `score-curve.py` 之外缺失的所有核心工具（`validate-bump.py` 暂未实现）。
- 梳理了在项目中集成 Agent Teams 架构的可行性方案。

## 下一步具体操作
1. 补全 starter-rubrics 模版（`long-form-essay.md` 和 `short-form-text.md`）。
2. 编写 `shared-references/agent-teams-protocol.md`。
3. 编写 `tools/validate-bump.py` 脚本，实现 rubric 升级验证逻辑。
4. 编写 `tools/agent-teams-evaluator.py` 脚本，实现多 Agent 评估核心代码。
5. 改造子技能 `skills/cheat-score/SKILL.md` 等。

## 关键报错和技术决策
- **决策一**：引入 `tools/agent-teams-evaluator.py` 脚本，以便将多 Agent（多角色）评估抽象成命令行脚本，既可以被 IDE Agent（如 Claude Code）在 `--mode team` 模式下直接调用并解析其 Markdown 结果，也能作为一个独立 CLI 工具在其他环境中运作。
- **决策二**：定义 `Hook Spec Expert`、`Logic & Structure Expert`、`Audience & Market Expert` 三个专门子 Agent 进行独立打分，并通过 `Manager Agent` 进行共识协调，从而符合 Agent Teams 的运作模式。
