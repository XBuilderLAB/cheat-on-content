---
name: cheat-learn-from-v2
description: 从对标账号导入 script + 数据 → 拆 pattern + 派生 base rubric 信号 → 写到 benchmark.md / script_patterns.md / rubric_notes.md。落盘时利用 Agent Teams 进行初始自动评分，并运行风格特征提取器生成 style_fingerprint.json。这是对标学习联动体系的入口。
argument-hint: <账号名> [— way: a (default) | b] [— append | --replace]
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /skills/cheat-learn-from-v2 — 对标账号导入 (v2 深度联动版)

本技能是对标账号导入与冷启动初始化的优化版本。与原版相比，它在落盘时追加了**初始评分自动提取**与**量化文案指纹分析**，从而为后续写稿（`cheat-seed-v2`）和公式升级校验（`validate-bump-v2`）提供精准的数据底座。

## Overview

```
[用户：学这个账号 / 启动 cheat-learn-from-v2]
  ↓
[Phase 0: 检查 benchmark 状态]
  ↓
[Phase 1: 选 input 方式（Way a 默认）]
  ↓
[Phase 2: 收集材料]
  Way a: 用户粘 N 条 script 文本 + 数据
  Way b: 用 whisper 转录 samples/ 目录里的视频
  ↓
[Phase 3: 询问每条样本的"印象判断"（高/中/低 + 为啥）]
  ↓
[Phase 4: Claude 拆 pattern + 派生 rubric 信号]
  ↓
[Phase 5: 用户 review → 改 → 落盘]
  ↓
[Phase 6: 落地写入 & 联动自动化运行]
  ├─ 写入 benchmark.md / script_patterns.md / rubric_notes.md
  ├─ 对每篇稿子运行 agent-teams-evaluator.py 自动初打分并追加写入 meta.md
  └─ 运行 style-extractor.py 自动提炼生成 style_fingerprint.json
  ↓
[Phase 7: 更新 state file 并绑定 benchmark_fingerprint]
```

## Constants

- **MIN_SAMPLES = 3** — 最少 3 条样本（少于拆不出 pattern）
- **RECOMMENDED_SAMPLES = 5-10** — 推荐区间，平衡信号量 vs 用户工作量
- **MAX_SAMPLES_PER_RUN = 15** — 单次导入上限
- **DEFAULT_WAY = a** — Way a 简单 + 准确，是 default

## Inputs

| 必填 | 来源 |
|---|---|
| `<账号名>` | 用户参数；包装为命令参数或在对话中询问 |
| `.cheat-state.json` | 状态文件 |
| Way a: 用户粘的 script 文本 + 数据 | 对话输入 |
| Way b: `samples/<账号名>/*.mp4` 等视频文件 | 用户放置在本地 samples 目录 |

## Workflow

### Phase 0: 检查 benchmark 状态

读 `.cheat-state.json` 的 `benchmark_status`：

| 状态 | 处理 |
|---|---|
| `none` | 首次导入——继续 Phase 1 |
| `pending` | 用户之前答应等下找——继续 Phase 1 |
| `imported` 已有 benchmark | 询问"你已有 benchmark [当前名]，N 条样本。要做什么？  a) 追加新视频到当前 benchmark  b) 替换为新 benchmark  c) 只看不改" |

参数解析：
- `--append` → 追加到现有 benchmark
- `--replace <new-name>` → 用新 benchmark 替换
- 没标志 + 已有 benchmark → 走上面询问

### Phase 1: 选 input 方式（两个独立维度）

每条样本 = **script** + **数据**。

#### Phase 1a: script source（怎么拿稿子）

* a) **粘文本（最简单，推荐）**：复制解析后的字幕文案粘贴到终端。
* b) **whisper 转录视频文件**：下载视频到 samples 目录运行 whisper 转录。
* c) **跳过 script，只用元数据 + 印象**：只填数据与印象。

#### Phase 1b: data source（怎么拿播放/点赞/评论）

* a) **手填数字（最简单）**。
* b) **adapter 自动抓（如已配置）**：提供 URL 自动采集。

### Phase 2: 收集材料

按 Phase 1a + 1b 的组合走对应路径，收录每个样本的 script 文本、播放、点赞、评论与转发数。

### Phase 3: 询问"印象判断"

对每个样本询问其是高、中还是低表现样本，并阐述理由，记录在内存。

### Phase 4: Claude 拆 pattern + 派生 rubric 信号

分析收集到的 script 与印象数据：
- **4a. Script patterns**：拆出具体的开头钩子、主体结构、句式规律。
- **4b. Rubric 信号**：对比高中低样本，定性分析重要维度。

### Phase 5: 用户 review

展示拆解成果给用户确认，获得 feedback 并进行调整。

### Phase 6: 落盘

#### 6a. benchmark.md
按格式写入到 `samples/` 目录下的 `<user-channel>/benchmark.md`。

#### 6b. samples/<账号名>/
为每条样本建子目录：
```
samples/<账号名>/<video-id>/
├── source.mp4 (Way b 才有，Way a 没有)
├── transcript.md (从粘文本写 / whisper 转出来)
└── meta.md (标题 / 数据 / 印象 / 印象理由)
```

**【联动打分与落盘】**：为了让对标样本可以参与后期的升级 Spearman 刚性校验，在 Python 脚本完成 ASR 写入后：
- 由 Agent (我们) 自动读取新样本的 `samples/<账号名>/<video-id>/transcript.md`；
- 在会话中，Agent 自动扮演打分团队进行内生多智能体博弈评估，生成 7 维专家打分；
- 随后由 Agent 调用文件修改工具，将该打分的 Markdown 表格作为 `## 初始打分` 区块追加写入到 `samples/<账号名>/<video-id>/meta.md` 文件底部。


#### 6c. script_patterns.md
在 `script_patterns.md` 中写入 untested 对标借鉴 pattern 块。

#### 6d. rubric_notes.md
在 `rubric_notes.md` 中写入 benchmark-derived 定性信号作为初版 Rubric 的大纲参考。

#### 6e. style_fingerprint.json (自动特征指纹生成)
在以上落盘动作全部完成后，自动在后台运行文案风格指纹提取器：
`python3 tools/style-extractor.py --samples-dir samples/<账号名>/ --output-json samples/<账号名>/style_fingerprint.json`
生成结构化的风格量化指纹文件，提供给后续写稿和打分模板使用。

### Phase 7: 更新 state file

更新并写入 `.cheat-state.json`，其中增加保存 `benchmark_fingerprint` 指向生成的指纹文件：
```json
{
  "benchmark_status": "imported",
  "benchmark_name": "<账号名>",
  "benchmark_sample_count": <N>,
  "benchmark_fingerprint": "samples/<账号名>/style_fingerprint.json"
}
```

## Integration

- 上游：`/cheat-init` Phase 2.5 在 cold-start 时强烈建议跑 `/skills/cheat-learn-from-v2/SKILL.md`。
- 下游：`/skills/cheat-seed-v2/SKILL.md` 自动读取 `style_fingerprint.json` 翻译并生成高还原度 Draft。
- 下游：`tools/validate-bump-v2.py` 升级公式时扫描 `samples/` 中的 meta.md 获取初始评分进行 Spearman 相关性刚性校验。
