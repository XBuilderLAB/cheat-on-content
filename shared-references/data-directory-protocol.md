# Data Directory Protocol

cheat-on-content 区分两个根目录：

- **workspace root**：用户自己的内容工作区，可包含其他资料和项目文件。
- **data root**：cheat-on-content 的 state、rubric、scripts、predictions、videos、cache 和 deliverables 所在目录。

## 解析优先级

所有用户技能、adapter、hook 和 CLI 必须使用同一顺序：

1. 显式 `--dir <path>`
2. 环境变量 `CHEAT_DATA_DIR`
3. workspace root 的 `.cheat-content.json`
4. workspace root 本身（旧布局）

指针文件 schema：

```json
{"schema_version": 1, "data_dir": "cheat-content"}
```

相对路径相对 workspace root；绝对路径按原值使用。pointer schema 不识别、JSON 损坏或 `data_dir` 为空时必须报错，不得静默回落到错误目录。

## 兼容与安全

- 已有 `.cheat-state.json` 的旧项目不要求搬迁。
- `CHEAT_PROJECT_ROOT` 是 adapter 的旧 workspace-root 变量，不得压过 `CHEAT_DATA_DIR` 或指针文件。
- `.auth*`、`.cheat-cache/` 与 `deliverables/` 默认不入 Git。
- 任何客户数据不得写入 cheat-on-content 源码仓库。
- Channel B blind scorer 仍只读显式传入的 script 和 rubric 路径，不自行解析或探测 data root。
