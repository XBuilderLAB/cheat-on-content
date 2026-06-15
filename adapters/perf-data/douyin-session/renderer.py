"""把抓到的数据渲染成 NotebookLM 友好的 Markdown。"""
from __future__ import annotations

import datetime as dt
from pathlib import Path


def _fmt_time(ts: int) -> str:
    if not ts:
        return "未知"
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _fmt_num(n: int | None) -> str:
    if n is None:
        return "-"
    if n >= 10000:
        return f"{n/10000:.1f}w"
    return str(n)


def _fmt_duration(ms: int) -> str:
    if not ms:
        return "-"
    s = ms // 1000
    return f"{s//60}:{s%60:02d}" if s >= 60 else f"{s}s"


def render_report(
    video: dict,
    script: str,
    comments: list[dict],
    detail_captured: list[dict] | None = None,
) -> str:
    lines: list[str] = []
    desc = video.get("desc") or "(无标题)"
    aweme_id = video["aweme_id"]

    lines.append(f"# {desc}")
    lines.append("")
    lines.append(f"- 视频 ID：`{aweme_id}`")
    lines.append(f"- 发布时间：{_fmt_time(video.get('create_time', 0))}")
    lines.append(f"- 时长：{_fmt_duration(video.get('duration_ms', 0))}")
    lines.append(f"- 链接：https://www.douyin.com/video/{aweme_id}")
    lines.append(f"- 抓取时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    lines.append("## 播放数据")
    lines.append("")
    lines.append(f"- 播放：{_fmt_num(video.get('play_count'))}")
    lines.append(f"- 点赞：{_fmt_num(video.get('digg_count'))}")
    lines.append(f"- 评论：{_fmt_num(video.get('comment_count'))}")
    lines.append(f"- 收藏：{_fmt_num(video.get('collect_count'))}")
    lines.append(f"- 分享：{_fmt_num(video.get('share_count'))}")
    lines.append("")

    if detail_captured:
        lines.append("### 详细指标（来自创作者中心）")
        lines.append("")
        lines.append("```json")
        import json
        for item in detail_captured[:3]:
            full = json.dumps(item["data"], ensure_ascii=False, indent=2)
            truncated = full[:2000]
            if len(full) > 2000:
                truncated += "\n... (truncated)"
            lines.append(truncated)
        lines.append("```")
        lines.append("")

    lines.append("## 原始稿子")
    lines.append("")
    lines.append(script.strip() if script.strip() else "（未提供）")
    lines.append("")

    lines.append(f"## 评论（按点赞降序，共 {len(comments)} 条）")
    lines.append("")
    if not comments:
        lines.append("（未抓到评论，可能评论区被折叠或账号未登录）")
    else:
        for c in comments:
            text = c["text"].replace("\n", " ").strip()
            reply = f" 💬{c['reply_comment_total']}" if c.get("reply_comment_total") else ""
            lines.append(f"- [👍{c['digg_count']}{reply}] {text}")
    lines.append("")

    return "\n".join(lines)


def slugify(text: str, max_len: int = 30) -> str:
    """生成文件夹友好的短标题。"""
    bad = '<>:"/\\|?*\n\r\t'
    out = "".join("_" if ch in bad else ch for ch in text).strip()
    return out[:max_len] or "untitled"


def output_dir_for(video: dict, root: Path) -> Path:
    date = _fmt_time(video.get("create_time", 0))[:10].replace("未知", "nodate")
    slug = slugify(video.get("desc") or video["aweme_id"])
    return root / f"{date}_{slug}"
