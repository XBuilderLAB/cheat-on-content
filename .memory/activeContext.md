# Active Context - cheat-on-content Agent Teams Integration

## 当前状态
所有的集成和改进工作已经顺利完成。新增了全自动抖音防风控真实数据抓取逻辑（iesdouyin 路由与主页分流），成功联通了本地 openai-whisper 的 ASR 台词提取与冷启动打分，完成了对真实链接的实证测试，已将所有代码全部 Git Commit 存盘。

## 上次做了什么
- 针对抖音 API 的 400 风控拦截，重构了 `抖音视频解析器_v1.0.py` 链接探查解析逻辑。支持免 API 的重定向 Location 跟踪，自动判断 Profile 链接（调用 `/fetch_user_post_videos`）或单视频链接（调用免 Cookie 的 `iesdouyin` 安全接口）。
- 重构了音频下载与转换逻辑，支持通过系统 ffmpeg 自动在下载无水印 mp4 视频后提取音轨转为 mp3。
- 修复了 macOS 系统下的 ffmpeg homebrew 软链接损坏（通过重新安装完成修复）。
- 增加了 `agent-teams-evaluator.py` 在未找到 `rubric_notes.md` 时的降级读取 templates 模板的容错路径。
- 用真实链接 `https://v.douyin.com/wzGV6q53PEo/` 跑通了下载、ASR 和专家打分的全套真数据联调。
- 使用 Git 进行中文 Commit（`优化链接重定向解析逻辑，本地免API探查主页特征，打通真数据抓取，支持打分模板降级读取`）。

## 下一步具体操作
- 等待用户进一步的对标学习或写稿需求。

## 关键报错和技术决策
- **决策一：iesdouyin 安全接口防风控**。实证发现抖音对主站 `www.douyin.com` 的请求有强滑块盾拦截，但对分享子域名 `www.iesdouyin.com/share/video/{id}` 几乎零风控。以此建立本地免 Cookie 抓取机制，完全摆脱对不稳定的外部解析网关的依赖。
- **决策二：自适应音频转换提取**。当网页端解析出视频地址而无直接音频 CDN 链接时，自适应下载 mp4 视频，并调用 ffmpeg 命令行提取 `.mp3` 音频，然后再无缝删除临时视频，保障转录所需的输入格式。

