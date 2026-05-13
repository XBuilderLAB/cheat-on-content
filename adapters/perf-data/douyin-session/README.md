# Adapter: douyin-session（抖音爬取）

被 `/cheat-retro` 在 `state.data_collection=adapter` + `platform=douyin` 时自动调用。

> **来源**：照搬自参考博主项目（私有）的 `crawler.py` / `review.py` / `renderer.py`——已在中文观点视频博主账号上跑了 25+ 视频验证。

---

## 这个 adapter 是干嘛的

抖音视频页是**强 JS 渲染 + XHR 加载评论 + 反爬严重**——不带浏览器引擎和登录态的方案（比如 Claude 的 WebFetch、Python requests）拿不到任何数据。

douyin-session 用 **Playwright + 持久化 Chromium context** 模拟真实浏览器：
- 你首次扫码登录抖音创作者中心，cookie 存在**你的内容项目根目录** `.auth/`
- 之后每次抓取直接复用 cookie，不用重新登录
- 拦截抖音前端的 XHR responses 直接抓数据接口的 JSON（不解析 HTML）
- 抓 3 类数据：视频列表 / 详细数据（完播 / 转粉率）/ 评论

输出写到**你的内容项目** `videos/<...>/report.md`（`cheat-retro` 读这个文件 → 摘要写到 prediction 复盘段）。
调试产物（URL dump / 截图）写到 `.cheat-cache/douyin-session-debug/`，避免散落在 skill 源码目录。

## 安装（一次性）

```bash
# 1. 进你的内容项目根目录
cd ~/my-channel

# 2. 建虚拟环境（强烈建议——Playwright + Chromium 几百 MB，别污染 system Python）
python3 -m venv .venv
source .venv/bin/activate

# 3. 装 Playwright
pip install playwright>=1.44

# 4. 装 Chromium（首次必须）
playwright install chromium

# 5. 首次扫码登录抖音创作者中心
ADAPTER=$(find ~/.claude/skills -name "douyin-session" -type d 2>/dev/null | head -1)
# 如找不到（可能 adapter 不在全局），用源码路径：
# ADAPTER="$HOME/Desktop/cheat-test/cheat-on-content/adapters/perf-data/douyin-session"
python "$ADAPTER/crawler.py" login
# → 弹出 Chromium 窗口，扫码登录创作者中心
# → 登录成功后窗口自动关闭，cookie 存在 当前目录/.auth/
```

## 用法

cheat-retro 自动调用，你不需要手动跑。但如果想手动测试：

```bash
cd ~/my-channel
source .venv/bin/activate

# 列最近视频（看登录态有没有失效）
python "$ADAPTER/crawler.py" list

# 抓特定视频
python "$ADAPTER/review.py" video <aweme_id> <video_folder>/script.md

# 输出在 当前目录/videos/<日期>_<title>/report.md
```

## 怎么拿到 aweme_id

抖音视频 URL 形态：
- `https://www.douyin.com/video/7234567890123456789` → `aweme_id = 7234567890123456789`（直接在 URL 路径里）
- `https://v.douyin.com/abc123` → 短链需要 resolve（cheat-publish 自动做）

cheat-publish 会在登记发布时把 aweme_id 存到 prediction header（如能 resolve）。cheat-retro 启动时直接读这个字段。

## report.md 输出格式

由 `renderer.py` 生成。包含：
- 视频元信息（标题、发布时间、时长）
- 数据快照（播放、点赞、评论、转发、收藏 + 派生比率：赞播比 / 评播比 / 分播比）
- 完播率 / 3s 留存（如能抓到）
- Top 20 评论（按赞数排序，含评论文本 + 赞数）
- 评论关键词聚类（renderer 自动做，可选）

## 失败模式（按概率从高到低）

| 症状 | 原因 | 处理 |
|---|---|---|
| `ensure_login` 超时 | cookie 过期或抖音强制 reauth | 重新跑 `python crawler.py login` |
| `_parse_video_list` 返回空 | 抖音改了接口字段——结构性变化 | 看 `.debug/creator_urls.txt` 抓到的 URL，更新 crawler.py 的字段兜底 |
| `_parse_video_list` 视频列表不全 | 翻页没抓到——网络慢或反爬触发 | 调高 `crawler.py` 里的 `await asyncio.sleep(...)` 时长 |
| Chromium 崩溃 / 卡死 | 通常是机器内存不足 | 关闭其他 Chromium 进程；`playwright install chromium --force` 重装 |
| 评论抓取慢（>5min） | 评论页 XHR 多次滚动触发——慢网络 | 调小 `fetch_comments_creator` 的 `max_pages`，或换更稳的网络 |

**关键现实**：抖音接口结构每隔几个月会变一次。这个 adapter **需要持续维护**——如果有一天它突然失败，第一步是去看 `视频分析` 项目最新的 crawler.py 看有没有新版本。

## 稳定性等级

★★ — Playwright 方案能扛比纯 HTTP 强得多的反爬，但仍受抖音前端改版影响。建议每月手动跑一次 `crawler.py list` 验证健康。

## 风险提示

- **冷启动用户慎装**：Playwright + Chromium 体积大（~500MB），新人容易劝退
- **TOS 风险**：用自己的 cookie 抓自己后台数据是个人用途；别滥用
- **不要把 .auth/ 提交到 git**：cookie 里有你的会话凭据，泄露 = 他人能登录你的抖音账号
- `.cheat-cache/douyin-session-debug/` 也不应提交到 git：里面可能含调试截图和接口 URL dump

## 文件清单

```
adapters/perf-data/douyin-session/
├── README.md           # 本文件
├── requirements.txt    # playwright>=1.44
├── crawler.py          # 抓取核心（视频列表 / 详细数据 / 评论）
├── review.py           # CLI 入口（交互式或 video <aweme_id> 模式）
├── renderer.py         # 把抓回的 JSON 渲染成 report.md
└── run.sh              # cheat-retro 调用的 wrapper
```

## 与其他 adapter 的关系

- `youtube-data-api`（待）— YouTube 用官方 API，不需要 Playwright，更轻
- `bilibili-stat`（待）— B 站官方 stat 接口公开，也不需要 Playwright
- `xhs-explore`（待）— 小红书也走 Playwright 路线，可借鉴本 adapter

如果你做多平台内容，**只装你实际用的 adapter**——不需要全装。
