# adapters/trend-sources/aihot — AI 行业热点

**适合谁**：AI 教程 / Builder / 工具号 / AI 行业评论。**不适合**普通生活/职场/文化垂类（用 trendradar-mcp.md）。

---

## 它是什么

[AIHOT](https://aihot.news/) 的 Claude Skill 适配，查询中文 AI 行业动态、精选、热点和历史日报。

- **5 类内容**：模型 / 产品 / 行业 / 论文 / 技巧
- **查询范围**：最近 7 天的动态和精选，以及历史日报、周报和月报
- **匿名只读**：安装 Skill 后可以直接查询，无需 API key 或另外配置 MCP

## 装

```bash
bash <(curl -fsSL https://aihot.news/aihot-skill/install.sh) --target claude
```

[官方安装与升级说明](https://aihot.news/aihot-skill/README.md)包含其他环境的安装步骤。装完后 Claude 会在 `~/.claude/skills/aihot/SKILL.md` 看到这个 skill，自动在用户问 AI 资讯时触发。

## cheat-seed / cheat-trends 怎么调

**不要直接 curl** —— 让 Claude 自然触发 aihot skill 即可：

| cheat-seed 场景 | 给 Claude 的内部指令 |
|---|---|
| Mode C，content_form 含 AI/教程/Builder | "调 aihot skill 拿今天 AI 圈精选条目，按 content_form 过滤后给 5 条" |
| Mode A 用户提到 AI 产品名（"DeepSeek V5"） | "调 aihot skill 用 q 参数搜该关键词最近 7 天动态" |

aihot skill 的 SKILL.md 已经详尽描述了端点 + 路由优先级（默认走精选不走日报）——cheat-seed 不需要重复写这套逻辑，**信任 aihot skill 自己的判断**。

## 输出格式契约

aihot skill 默认返回 markdown，按 5 类（模型/产品/行业/论文/技巧）分组。cheat-seed 收到后：

1. 按 `content_form` 过滤掉不相关类别（如 opinion-video → 留行业 + 产品；tutorial-builder → 留模型 + 工具）
2. 用当前 rubric 粗筛 5 条最适合的
3. 转成 [candidate-schema.md](../../shared-references/candidate-schema.md) 的 schema 写入 `candidates.md`

## 失败模式

| 症状 | 处理 |
|---|---|
| 403 Forbidden | 核对 Skill 版本与官方安装说明；仍受限时使用现有降级路径 |
| 端点超时 / 5xx | 优雅降级到 trendradar-mcp 或 manual-paste；不抛异常 |
| 用户的 content_form 跟 AI 完全无关（如美食/妆教） | cheat-seed 应该**不调 aihot**——按 [data-source-routing.md](../../shared-references/data-source-routing.md) 的路由表 |

## 稳定性

★★★★★ — 公开 API，作者维护，无认证依赖。

---

## 与其他 adapter 的关系

- **vs trendradar-mcp.md**：互补不重叠。aihot 是 AI 垂直，trendradar 是综合。两者都启用时按 `content_form` 路由。
- **vs manual-paste**：永远的 fallback。aihot/trendradar 都失败时走 manual-paste。
