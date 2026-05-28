# Adapter: xhs-explore（小红书爬取）

被 `/cheat-retro` 在 `state.data_collection=adapter` + `platform=xhs` 时自动调用。

> **来源**：照搬 `douyin-session` adapter 的架构（Playwright 持久化登录态 + 被动拦截 XHR），
> 接口路径与字段参考 NanmiCoder/MediaCrawler 与 ReaJason/xhs。已在真实创作者账号端到端验证（2026-05）。

---

## 这个 adapter 是干嘛的

小红书反爬靠 `x-s`/`x-t`/`x-s-common` 签名 + `xsec_token`——纯 HTTP / requests 拿不到数据。

xhs-explore 用 **Playwright + 持久化 Chromium context** 模拟真实浏览器，**不逆向签名、不伪造请求**，
让页面自己发带签名的请求，我们只被动拦截返回的 JSON：

- 首次扫码登录创作者中心，cookie 存在**你的内容项目根目录** `.auth-xhs/`
- 之后每次抓取复用 cookie
- 抓两路数据：
  1. **创作者中心 galaxy 接口**（`/api/galaxy/v2/creator/note/user/posted`）— 你**自己**笔记的运营数据：观看/点赞/收藏/评论/分享，**不需要 xsec_token**，最稳。列表每条自带 `xsec_token`，抓自己的笔记无需手动粘带 token 的链接
  2. **前台 web API**（`/api/sns/web/v1/feed` + `/api/sns/web/v2/comment/page`）— 拿确认字段的点赞/收藏数 + 评论文本

输出写到**你的内容项目** `videos/<...>/report.md`。
调试产物（URL dump / 截图 / galaxy 原始 JSON）写到 `.cheat-cache/xhs-explore-debug/`。

## 字段映射（已校准）

galaxy `note/user/posted` 的真实字段名已用真实账号确认并写死在 `crawler.py` 的 `_normalize_note()`：
观看 `view_count`、点赞 `likes`、收藏 `collected_count`、评论 `comments_count`、分享 `shared_count`、
发布时间 `visible_time`（unix 秒）/ `time`（本地时间串）、单篇 `xsec_token`。

万一小红书改版导致某项显示 0：打开 `videos/<...>/report.md` 末尾的"galaxy 原始字段"JSON，
把新 key 加进 `_normalize_note()` 对应的 `_first(v, ...)` 候选列表即可（多候选兜底仍保留）。

## 安装（一次性）

```bash
# 1. 进你的内容项目根目录
cd ~/Documents/my-channel

# 2. 建虚拟环境
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. 装 Playwright + Chromium
pip install playwright>=1.44
playwright install chromium

# 4. 首次扫码登录小红书创作者中心
ADAPTER=$(find ~/cheat-on-content -name "xhs-explore" -type d 2>/dev/null | head -1)
python "$ADAPTER/crawler.py" login
# → 弹出 Chromium 窗口，用小红书 App 扫码
# → 登录成功后窗口自动关闭，cookie 存在 当前目录/.auth-xhs/
```

> Windows 提示：adapter 在 `~/cheat-on-content/adapters/perf-data/xhs-explore`（克隆源码处），
> 不在 `~/.claude/skills`（install.sh 只复制 15 个 skill，不复制 adapter）。

## 用法

cheat-retro 自动调用。手动测试：

```bash
cd ~/Documents/my-channel
source .venv/bin/activate

# 列最近笔记（验证登录态没失效）
python "$ADAPTER/review.py" list

# 抓特定笔记
python "$ADAPTER/review.py" note <note_id> [script.txt]

# 输出在 当前目录/videos/<日期>_<标题>/report.md
```

## 怎么拿到 note_id

小红书笔记 URL：
- `https://www.xiaohongshu.com/explore/66f1a2b3c4d5e6f700112233?xsec_token=...` → `note_id = 66f1a2b3c4d5e6f700112233`
- `https://xhslink.com/xxxxx` → 短链，cheat-publish 会 resolve

cheat-publish 登记发布时把 note_id 存到 prediction header，cheat-retro 启动时读这个字段。

## report.md 输出格式

由 `renderer.py` 生成：
- 笔记元信息（标题、发布时间、链接、IP 归属）
- 数据快照（曝光/浏览、点赞、收藏、评论、分享 + 派生比率：赞曝比 / 藏曝比 / 评曝比 / 分曝比 + 涨粉）
- galaxy 原始字段 JSON（debug / 接口改版时核对字段用）
- Top 评论（按赞数排序，含文本 + 赞数 + IP）

## 失败模式（按概率从高到低）

| 症状 | 原因 | 处理 |
|---|---|---|
| 曝光显示 0 但 JSON 有数 | galaxy 字段 key 不在候选列表 | 看 report.md 里 galaxy JSON，把真实 key 加进 `_normalize_note` |
| `ensure_login` 超时 | cookie 过期 | 重跑 `python crawler.py login` |
| 笔记列表为空 | 创作者中心改了 galaxy 接口路径 | 看 `.cheat-cache/xhs-explore-debug/creator_urls.txt`，更新 `GALAXY_*_KEYS` |
| 评论抓不到 | xsec_token 缺失 / 评论被关 | 看 `frontend_urls.txt`；拿不到就降级 manual 粘评论（cheat-retro 会提示） |
| Chromium 崩溃 | 内存不足 | 关其他 Chromium；`playwright install chromium --force` |

**关键现实**：小红书接口 path（`/feed`、`/comment/page`、galaxy）相对稳定，但签名和 xsec_token 机制常变。
本 adapter 用被动拦截规避签名风险——最易抖动处是 **galaxy 创作者接口**和**评论回复**。

## 稳定性等级

★★ — Playwright + 登录态能扛比纯 HTTP 强得多的反爬，但仍受小红书前端改版影响。
评论路径（依赖 xsec_token）比创作者数据路径脆，必要时降级 manual。

## 风险提示

- **冷启动用户慎装**：Playwright + Chromium ~500MB
- **TOS 风险**：用自己的 cookie 抓自己后台数据是个人用途；别滥用、别高频
- **不要把 `.auth-xhs/` 提交到 git**：cookie 含会话凭据，泄露 = 他人能登录你的小红书账号
- `.cheat-cache/xhs-explore-debug/` 也不应提交（含调试截图 / 接口 URL / 原始 JSON）

## 文件清单

```
adapters/perf-data/xhs-explore/
├── README.md           # 本文件
├── requirements.txt    # playwright>=1.44
├── crawler.py          # 抓取核心（galaxy 笔记列表+数据 / 前台 interact+评论）
├── review.py           # CLI 入口（login / list / note <note_id>）
├── renderer.py         # 把抓回的 JSON 渲染成 report.md
├── paths.py            # 项目根 / .auth-xhs / debug 路径解析
└── run.sh              # cheat-retro 调用的 wrapper
```

## 与其他 adapter 的关系

- `douyin-session` — 抖音，本 adapter 的架构来源
- `youtube-data-api`（待）— YouTube 官方 API，更轻
- `bilibili-stat`（待）— B 站官方 stat 接口

如果你做多平台内容，**只装你实际用的 adapter**。
