from __future__ import annotations

import datetime as dt
from pathlib import Path


def _fmt_time(value) -> str:
    if not value:
        return "未知"
    try:
        ts = int(value)
        if ts > 1_000_000_000_000:
            ts //= 1000
        return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return str(value)


def _fmt_num(value) -> str:
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return str(value)
    return f"{n / 10000:.1f}w" if n >= 10000 else str(n)


def _ratio(num, denom) -> str:
    try:
        a, b = int(num or 0), int(denom or 0)
        return "-" if b <= 0 else f"{a / b * 100:.2f}%"
    except (TypeError, ValueError):
        return "-"


def _percent(value) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "-"
    if n <= 1:
        n *= 100
    return f"{n:.2f}%"


def slugify(text: str, max_len: int = 30) -> str:
    bad = '<>:"/\\|?*\n\r\t'
    return ("".join("_" if ch in bad else ch for ch in text).strip()[:max_len] or "untitled")


def output_dir_for(post: dict, root: Path) -> Path:
    date = _fmt_time(post.get("create_time"))[:10].replace("未知", "nodate")
    return root / f"{date}_{slugify(post.get('title') or post['post_id'])}"


def render_report(post: dict, script: str, comments: list[dict]) -> str:
    title = post.get("title") or "(无标题)"
    views = post.get("view_count") or 0
    lines = [
        f"# {title}",
        "",
        f"- 视频号作品 ID：`{post['post_id']}`",
        f"- 发布时间：{_fmt_time(post.get('create_time'))}",
        f"- 抓取时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 数据快照",
        "",
        f"- 播放/浏览：{_fmt_num(views)}",
        f"- 点赞：{_fmt_num(post.get('like_count'))}（赞播比 {_ratio(post.get('like_count'), views)}）",
        f"- 爱心/收藏：{_fmt_num(post.get('favorite_count'))}（藏播比 {_ratio(post.get('favorite_count'), views)}）",
        f"- 评论：{_fmt_num(post.get('comment_count'))}（评播比 {_ratio(post.get('comment_count'), views)}）",
        f"- 分享/转发：{_fmt_num(post.get('share_count'))}（分播比 {_ratio(post.get('share_count'), views)}）",
    ]
    if post.get("full_play_rate") is not None:
        lines.append(f"- 完播率：{_percent(post.get('full_play_rate'))}")
    if post.get("avg_play_time_sec") is not None:
        lines.append(f"- 平均播放时长：{float(post.get('avg_play_time_sec')):.1f} 秒")
    if post.get("fast_flip_rate") is not None:
        lines.append(f"- 快速划走率：{_percent(post.get('fast_flip_rate'))}")
    if post.get("follow_count"):
        lines.append(f"- 带来关注：{_fmt_num(post.get('follow_count'))}")
    if post.get("yesterday_view_count"):
        lines.append(f"- 昨日新增播放：{_fmt_num(post.get('yesterday_view_count'))}")
    lines.append("")
    lines.extend(["## 原始稿子", "", script.strip() or "（未提供）", "", "## 评论", ""])
    if comments:
        for comment in comments[:20]:
            if not isinstance(comment, dict):
                continue
            text = comment.get("text") or comment.get("content") or comment.get("comment") or ""
            likes = comment.get("like_count") or comment.get("likeCount") or 0
            reply = "（回复）" if comment.get("is_reply") else ""
            if text:
                lines.append(f"- [👍{likes}] {reply}{str(text).replace(chr(10), ' ').strip()}")
    else:
        lines.append("（作品列表接口未返回评论文本；需要在评论管理页进一步捕获。）")
    lines.append("")
    return "\n".join(lines)
