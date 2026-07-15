# Adapter: wechat-channels（视频号助手）

用于抓取自己账号在视频号助手后台的作品运营数据。

## 原理

- Playwright 持久化 Chromium 登录态
- 被动监听 `channels.weixin.qq.com/platform/` 页面自行发出的 JSON
- 不逆向签名，不读取微信客户端文件
- 登录态保存在内容项目的 `.auth-wechat-channels/`

## 安装与登录

```powershell
cd <内容项目>
.\.venv\Scripts\python.exe -m pip install -r <adapter>\requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe <adapter>\review.py login
```

扫码登录后验证：

```powershell
.\.venv\Scripts\python.exe <adapter>\review.py list
```

## 抓取单条作品

```powershell
.\.venv\Scripts\python.exe <adapter>\review.py post <post_id> [script.txt]
```

运行时只在内存中处理页面自行发出的 JSON。adapter 不把原始响应、请求体、
完整后台 URL、后台页面文本或截图写入磁盘；诊断信息只在终端输出计数和错误原因。

## 当前限制

- 第一版优先实现作品列表和播放/点赞/爱心/评论/分享数据。
- 已支持从“互动管理 → 评论”自动抓评论文本、点赞数和作者回复。
- 默认按点赞和时间排序，报告最多写入 Top 20；接口有分页时自动翻页。
- 如果指定的 post_id 不在最近作品列表中，会以非 0 状态退出，避免生成 0 值 report.md 污染复盘。
- `run.sh` 会在每次抓取前删除目标目录内的旧 `report.md`；抓取失败时不会把陈旧报告误报为成功。

## TOS / 风险边界

- 仅用于用户自己登录后可见的视频号助手后台数据。
- 不抓取他人作品，不绕过登录，不逆向签名，不自动发布内容。
- 不持久化原始响应、请求体、signed media URL、内部用户名/ID、cookie、secret、后台截图或页面文本。
- `report.md` 仍含用户自己的运营数据和评论文本，应保存在私有内容项目中；对外分享前须审阅和脱敏。
- 请低频手动触发，用于个人内容复盘和 NotebookLM/cheat-on-content 分析。

## 本地验证

```bash
python -m unittest discover -s adapters/perf-data/wechat-channels -p 'test_*.py' -v
bash adapters/perf-data/wechat-channels/test_run_contract.sh
```
