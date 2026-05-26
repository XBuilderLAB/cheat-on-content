---
name: cheat-seed-v2
description: 对话讨论选题并自动撰写草稿 (v2 风格指纹版)。本版本在写稿时自动读取对标账号的风格指纹 JSON，并将量化句长、标点倾向、过渡词与高赞评论 Meme 词翻译为 Prompt 刚性约束，生成高还原度对标文案。
argument-hint: [— batch: N] [— sources: <comma-separated>]
allowed-tools: Bash(*), Read, Write, Edit, Glob, WebFetch, Skill
---

# /skills/cheat-seed-v2 — 选题与风格指纹约束写稿 (v2 深度联动版)

本技能在原 `cheat-seed` 选题对话的基础上，增加了**文案风格指纹约束写稿**功能。它能够读取冷启动阶段生成的风格指纹，将对标账号的文字节奏量化映射为 Prompt 写作纪律，确保 AI 生成的草稿直接具备对标账号的“语感和神韵”。

## 三种 Mode（自动分流）

1. **Mode A — 用户主动给主题**：用户输入主题或经历，AI 进行深度挖掘（最长 4 轮），提炼出一个精准角度并生成草稿。
2. **Mode B — 用户给方向但不具体**：用户仅提供大类别（如“职场”），AI 反问“为什么”以引导用户内省。
3. **Mode C — 用户完全没想法**：调用热点分析工具呈现 5 条热门素材，引导用户挑选并内省。

---

## 风格指纹翻译机制 (Style Fingerprint Translator)

当状态机检测到有导入的风格指纹 `samples/<账号名>/style_fingerprint.json` 时，写稿引擎在 Phase 4 会自动调用**指纹翻译映射规则**，生成写作硬约束指令并注入 Prompt：

### 1. 句长与方差翻译 (Rhythm Constraints)
* **平均句长 (`average_sentence_length` < 12 字)**：
  - `翻译指令`：“文案风格要求短小精悍。多用超短句，禁止使用多重修饰的长从句，每句话控制在 10 字以内，快速换行。”
* **平均句长 (`average_sentence_length` ≥ 12 字)**：
  - `翻译指令`：“文案要求叙事饱满、逻辑绵密。多用词义完整、论证详实的叙事长句，避免过于琐碎的断句。”
* **句长方差 (`sentence_length_variance` > 15)**：
  - `翻译指令`：“节奏要求极强，长短句剧烈交错。多使用一长句铺垫情绪或场景，随后紧跟 2-3 个短促断句砸地，制造强烈的语言韵律感。”
* **句长方差 (`sentence_length_variance` ≤ 15)**：
  - `翻译指令`：“句式长短应保持平缓一致，避免过大的节奏跳跃，确保情绪流平稳连贯。”

### 2. 标点与情绪烈度翻译 (Emotion & Tone)
* **叹号率 (`exclamation_mark_ratio` > 0.15)**：
  - `翻译指令`：“情感爆发力要强。全篇情绪昂扬，多使用叹号，多写情绪激昂的感叹句和设问句。”
* **问号率 (`question_mark_ratio` > 0.20)**：
  - `翻译指令`：“互动性要强。多使用疑问句和反问句，连续向读者发问，引导受众代入思考。”
* **省略号率 (`ellipsis_ratio` > 0.10)**：
  - `翻译指令`：“在转折、思考留白或情感延伸的停顿处，合理使用省略号（……），营造悬念或意犹未尽的氛围。”
* **每百字换行率 (`newline_ratio_per_100_chars` > 8.0)**：
  - `翻译指令`：“分段极其紧凑，通常单句即为一段，多用空行隔开，降低阅读屏障。”

### 3. 高频词语硬注入 (Signature Words Injection)
* **过渡词注入**：强行规定大模型在承上启下或逻辑转折时，优先使用 `signature_transitions` 列表（如“其实”、“也就是说”、“但是”）中的前 3 个常用过渡词。
* **Meme 词共鸣**：强行规定大模型在 MVP 金句或收尾引发互动时，巧妙融入 `audience_memes` 列表（如“暗恋”、“自嘲”、“笑死”）中的高频词，引发评论区共振。

---

## Workflow

### Phase 0: 前置检查 + 加载指纹 Context

1. 读 `.cheat-state.json`，校验项目初始化状态。
2. 读 `rubric_notes.md`，拿当前公式。
3. 读 `script_patterns.md`，拿已有 Pattern 结构。
4. **加载 Context B (对标与指纹)**：
   - 检查 `state.benchmark_status == "imported"`，读取 `benchmark.md`。
   - 读取并加载 `state.benchmark_fingerprint` 指向的 `samples/<账号名>/style_fingerprint.json`。
   - 解析其中的 `style_metrics`、`signature_transitions` 和 `audience_memes`，为 Phase 4 提供翻译输入。

### Phase 1: Mode 分流

根据用户参数（如 `--batch`）和输入内容，自动判定并分流进入 Mode A/B/C。

### Phase 2: 对话讨论与选题收敛

与用户保持一问一答，针对用户的输入深挖核心瞬间与情感锚点。收敛后给出拟定角度与粗打分估算。

### Phase 3: 候选池记录

将确认的角度写入 `candidates.md` 标为 `tier1`。

### Phase 4: 风格指纹约束写 Draft

`WITH_DRAFT=yes` → 顺次撰写草稿，写入 `scripts/<YYYY-MM-DD>_<id>_<short-title>.md`。

**指纹约束注入步骤**：
1. 运行指纹翻译机制，将对标账号的 `style_metrics` 数据转换为 3-5 条明确的自然语言“写作规则”。
2. 将过渡连词列表和高频 Meme 词列表作为 Prompt 的核心词库输入。
3. 在草稿生成 Prompt 中融合用户经历 + 结构选型 + **指纹写作规则**，命令大模型执行生成。
4. 草稿的 Meta 头部追加打印指纹的量化数据，方便用户肉眼比对：
   ```markdown
   **对标指纹特性**: {平均句长: X, 句长方差: Y, 叹号率: Z, 问号率: W}
   **对标指纹高频连词**: [A, B, C]
   **对标指纹高频Meme词**: [X, Y, Z]
   ```

### Phase 5: 输出“下一步”与收尾

草稿写入落盘，提示用户可以直接在 `scripts/` 中进行二次润色与改写，改完后即可运行 `/cheat-predict` 或进行校验。

## Key Rules

1. **翻译必须直白可执行**：严禁直接把复杂的方差和浮点数扔给 AI 写作 Prompt，必须翻译为具体的格式与语气约束。
2. **遵守字数和时长换算**：按照 `typical_duration_seconds` 自动映射目标字数，防止生成过长或过短。
3. **保留原版功能一致性**：选题讨论机制和三种 Mode 的判定标准与原版保持完全一致，仅在 Phase 0 Context 读取与 Phase 4 Draft 生成上深度优化。
