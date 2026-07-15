# Cheat-on-Content 商业化内测

第一版卖的不是“AI 帮你写”，而是一次能被检验的账号判断升级。

## 套餐

| 套餐 | 价格 | 交付 |
|---|---:|---|
| 单次账号体检 | ¥999 | 20–50 篇历史分析、3 个假设、四周实验计划、60 分钟解读 |
| 四周校准服务 | ¥2,999 | 单次体检 + 3 轮盲预测—发布—T+3 复盘 |

暂不提供无限次数订阅，不承诺绝对播放量，不做自动发布。

## 30 天目标

使用 `templates/commercial-pilot-scorecard.template.md` 跟踪三位付费客户。只有当全部硬门槛通过，才进入本地自助版；达到 10 个付费客户、3 个续费客户后，才讨论 SaaS。

## 操作入口

```powershell
# Windows 原生
powershell -ExecutionPolicy Bypass -File tools/cheat.ps1 --project C:\path\to\client init --agent codex --dir cheat-content
powershell -ExecutionPolicy Bypass -File tools/cheat.ps1 --project C:\path\to\client audit --input C:\path\to\notes.json --account-name "账号名"
```

```bash
# macOS / Linux / Git Bash
python tools/cheat_cli.py --project /path/to/client --dir cheat-content init --agent other
python tools/cheat_cli.py --project /path/to/client audit --input /path/to/notes.json --account-name "账号名"
```

客户原始数据放在客户项目，不放在 cheat-on-content 源码仓库。
