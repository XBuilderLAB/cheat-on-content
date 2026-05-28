# Progress - cheat-on-content Agent Teams Integration

## 路线图 (Roadmap)
- [x] 基础模版补全 (starter-rubrics)
- [x] 制定 Agent Teams 协议 (agent-teams-protocol.md)
- [x] 开发升级验证工具 (validate-bump.py)
- [x] 开发 Agent 团队打分引擎 (agent-teams-evaluator.py)
- [x] 改造核心子技能 (SKILL.md, score, predict, bump)
- [x] 开发量化风格提取器 `style-extractor.py` (v2独立版)
- [x] 开发防风控抖音视频网页解析与 ASR 音轨 Whisper 转换下载器 (v2独立版)
- [x] 全链路真实抖音链接抓取与转录评分实证测试
- [x] Git 提交

## 已完成 (Completed)
- [x] 项目结构与规范梳理
- [x] 制定实施方案与任务清单
- [x] starter-rubrics/long-form-essay.md (公众号长文模板)
- [x] starter-rubrics/short-form-text.md (微博/X短文模板)
- [x] shared-references/agent-teams-protocol.md (多智能体协作打分协议)
- [x] tools/validate-bump.py (Spearman秩相关系数与相对排序回归校验工具)
- [x] tools/agent-teams-evaluator.py (多Agent协作评估与博弈模拟引擎)
- [x] 改造 skills/cheat-score/SKILL.md 接入 team 模式
- [x] 改造 skills/cheat-predict/SKILL.md 接入 team 模式并记录 Scored By 元数据
- [x] 改造 skills/cheat-bump/SKILL.md 接入 2 阶段自动脚本强校准
- [x] 改造根 SKILL.md 路由与原则声明
- [x] 开发 `tools/style-extractor.py` & `tools/文案风格指纹提取器_v1.0.py` 提取风格特征
- [x] 开发 `tools/douyin-fetcher.py` & `tools/抖音视频解析器_v1.0.py`（融合 iesdouyin 路由与主页分流，支持 ffmpeg 视频/音频转换提取）
- [x] 修复本地 `ffmpeg` macOS brew 共享库依赖缺失
- [x] 用真实抖音主页链接 `https://v.douyin.com/wzGV6q53PEo/` 跑通全链路 ASR 台词识别、自动落盘与评估降级匹配测试
- [x] 完成 Git 中文 Commit 提交
- [x] 重构项目为 skills 分支架构，大模型打分与决策完全上移至 Agent 内生模拟，剥离外部 API 依赖

## 下一步 (Next Steps)
- 等待用户对免 API 运行的实证反馈。


