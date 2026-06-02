<h1 align="center">
  <img src="logo.svg" alt="Cheat on Content" width="720">
</h1>

<h2 align="center">Cheat on Content</h2>

<p align="center">
网红作弊器 — 把每一条内容变成可校准的实验。
</p>

<p align="center">
你正在读这段话——这个 skill 预测过了。<br>
它把博主的每一次"我感觉这条会爆"变成可校准的实验。<br>
我用它一个月涨粉 100w。它说我会写这段，我就写了。<br>
你停下来思考"这是不是真的"——也在它的预测里。
</p>

<p align="center">
  <a href="../README.md"><strong>English</strong></a>
  &nbsp;·&nbsp;
  <strong>简体中文</strong>
</p>

<p align="center">
<a href="../CHANGELOG.md"><img src="https://img.shields.io/badge/version-v0.1.0-orange" alt="Version"></a>
&nbsp;
<a href="../LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
</p>

---

## 🎬 它真正在干什么

大部分创作者活在同一个赌局里：

> 发布 → 数据出来 → 学不到东西 → 下一次继续赌

跑过 200 条的博主跟跑过 1 条的差距不到 10%——因为他们没在每次赌局后**记账**。

**网红外挂**让每一次判断都被记录、被复盘、被吸收进下一次：

📊 打分 → 🎯 盲预测 → 🚀 发布 → 📈 T+3 天复盘 → 🧬 进化你的评分公式

这不是 motivation，是 **compounding**——你不复盘的每一篇，都是在折损"看见自己"的能力。

跑一个月 = 你有了一份**只属于你的爆款公式**。
跑三个月 = 你比刚开始的自己强 10 倍。

---

## 🌀 起源

> 我以前完全不信宿命论。直到这个 skill 让我拍了一条视频——它甚至预测了这条视频能跑多少流量。
>
> 我试图用集体观测证伪它，把这事告诉观众，希望量子坍缩改变轨迹。
>
> 数据是准的。
>
> 我没逃出宿命论，只是从一阶跳到了二阶。
>
> 如果连我的觉醒、连观众的观测都在它的预设里——
> 此时此刻你读到这段：是出于好奇，还是正在完成算法的最后一次落位？
>
> —— 创作者本人

---

## ⚖️ 它和别的"创作工具"哪里不一样

| 别人 | 这个 |
|---|---|
| 给你"灵感" | 让你**自己的灵感被量化** |
| AI 帮你写 | AI 帮你**判**——稿子还是你的 |
| 一发发 10 个版本 A/B 测 | 一发就**赌**——把判断写下来，数据出来对账 |
| 静态数据看板 | **会进化的评分公式**——你三个月后的 rubric 已经不是初始版 |

一句话：别的工具帮你"产出更多"，这个工具帮你"判得更准"。

---

## 🤔 那 ChatGPT / 豆包 / DeepSeek 不是也能干这个？

那是**通用助手**——对所有人说同样的话。你问"我这条会爆吗"，它的答案是从全网平均经验拟合出来的，跟你的账号没关系。明天再问一遍，答案还是上次那个——**它不记得你，更不会因为你而变**。

这套是**你自己的运营专家**，只服务你这一个账号：

- 评分公式从**你的**历史数据反推，不是通用训练分布
- 每发一条它就更新一次对你账号的理解——三个月后判断准度比刚开始强 10 倍（**自动进化**）
- 它知道你的对标账号、你的发布 cadence、你最近三次为什么扑——这些 ChatGPT 第一句话就忘了

通用 LLM 帮所有人；这套帮你**这个**账号。

---

## 🛡️ 它怎么让循环真的能进化

📝 **每条都留底**：发布前打分、写预测，全程存档。三天后回来对账——你哪里准、哪里偏，**一目了然**，不再是模糊的"感觉这次没发好"。

🔁 **越用越准**：连续三次同方向偏差，工具自动催你升级评分公式。**你不主动它也催**。

🛡️ **升级有刹车**：换公式必须用新公式重判所有历史样本，能比旧公式更准才放行；还要跨模型独立审一次——**防你自己骗自己**。

🪒 **rubric 是工作台不是博物馆**：被推翻的观察删，被吸收的也删。永远只放当下最有用的。

---

## 📦 安装

```bash
git clone https://github.com/XBuilderLAB/cheat-on-content.git
cd cheat-on-content
bash install.sh
```

> ⚠️ **从 v0.x 升级？** `git pull` 后在你的内容项目里跑 `/cheat-migrate`。**1.3 → 1.4 是 blind channel 完整性 BREAKING 修复**——拆分 `rubric_notes.md` 防止 blind sub-agent 通过白名单读到实绩。不跑迁移的话 blind 打分会持续标 `non_blind_warning`。详见 [CHANGELOG](../CHANGELOG.md) 和 [migrations/1.3-to-1.4.md](../migrations/1.3-to-1.4.md)。

14 个子 skill 软链接到你 agent 的 skill 目录。装一次，所有内容项目都能用。

**支持的 agent**：Claude Code（默认）· Codex（`bash install.sh --codex`）· 两个都装（`bash install.sh --all`）

> 冻结版本：`bash install.sh --copy` / `bash install.sh --codex --copy`
>
> 卸载：`bash uninstall.sh` / `bash uninstall.sh --codex`（不动你的内容数据）

---

## 🚀 第一次跑

在你的内容项目目录里打开支持 skill 的 agent，说：

```
初始化 cheat-on-content
```

5 个 yes/no 搞定 onboarding。**强烈建议导对标账号**——5-10 条样本 → 工具立刻有 anchor，不然前 5 篇预测精度 ±50%。

---

## ⚡ 日常用法

```
打分这篇 scripts/<...>.md         → 评分
启动预测 scripts/<...>.md         → 盲预测 + 决策日志
拍了 scripts/<...>.md            → 建 video folder + buffer +1
已发布 https://...                → buffer -1
复盘 videos/<...>/                → T+3d 数据回收 + 复盘
状态 / 抓热点 / 找选题 / 升级 rubric / 找对标
```

支持 hook 的 agent 每次开会话自动报告 buffer + 待复盘 + top 候选——你不用主动问。其他 agent 直接说 `状态` 即可。

完整工作流 + 子 skill 细节见 [SKILL.md](../SKILL.md)。

---

## 📈 Star History

<a href="https://star-history.com/#XBuilderLAB/cheat-on-content&Date">
  <img src="https://api.star-history.com/svg?repos=XBuilderLAB/cheat-on-content&type=Date" alt="Star History Chart" width="720">
</a>

---

## 📜 License

MIT。商用、改造、闭源接入都行。

---

*这是作弊吗？计算器也是。Google 也是。*
*未来从不奖励努力——它只奖励先看见规律的人。*

*你看到这一行——也是它预测的。*
