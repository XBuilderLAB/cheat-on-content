"""把抓到的小红书数据渲染成 report.md（cheat-retro 读这个文件）。"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


def _fmt_time(ts) -> str:
    if not ts:
        return "未知"
    try:
        ts = int(ts)
        # 小红书部分接口用毫秒时间戳
        if ts > 1e12:
            ts //= 1000
        return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return str(ts)


def _fmt_num(n) -> str:
    if n is None:
        return "-"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return str(n)
    if n >= 10000:
        return f"{n/10000:.1f}w"
    return str(n)


def _ratio(num, denom) -> str:
    try:
        num, denom = int(num), int(denom)
    except (ValueError, TypeError):
        return "-"
    if denom <= 0:
        return "-"
    return f"{num/denom*100:.2f}%"


def render_report(note: dict, script: str, comments: list[dict]) -> str:
    lines: list[str] = []
    title = note.get("title") or "(无标题)"
    note_id = note["note_id"]
    view = note.get("view_count") or 0

    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- 笔记 ID：`{note_id}`")
    lines.append(f"- 发布时间：{note.get('post_time_str') or _fmt_time(note.get('create_time', 0))}")
    lines.append(f"- 链接：https://www.xiaohongshu.com/explore/{note_id}")
    lines.append(f"- 抓取时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    if note.get("ip_location"):
        lines.append(f"- IP 归属：{note['ip_location']}")
    lines.append("")

    lines.append("## 数据快照")
    lines.append("")
    lines.append(f"- 曝光/浏览：{_fmt_num(view)}")
    lines.append(f"- 点赞：{_fmt_num(note.get('like_count'))}（赞曝比 {_ratio(note.get('like_count'), view)}）")
    lines.append(f"- 收藏：{_fmt_num(note.get('collect_count'))}（藏曝比 {_ratio(note.get('collect_count'), view)}）")
    lines.append(f"- 评论：{_fmt_num(note.get('comment_count'))}（评曝比 {_ratio(note.get('comment_count'), view)}）")
    lines.append(f"- 分享：{_fmt_num(note.get('share_count'))}（分曝比 {_ratio(note.get('share_count'), view)}）")
    if note.get("fans_inc"):
        lines.append(f"- 涨粉：{_fmt_num(note.get('fans_inc'))}")
    lines.append("")

    # galaxy 原始 JSON——首跑时用来确认曝光字段的真实 key 名
    raw = note.get("raw")
    if raw:
        lines.append("### galaxy 原始字段（首跑校准用，确认曝光字段 key 后可忽略）")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(raw, ensure_ascii=False, indent=2)[:2500])
        lines.append("```")
        lines.append("")

    lines.append("## 原始稿子")
    lines.append("")
    lines.append(script.strip() if script.strip() else "（未提供）")
    lines.append("")

    lines.append(f"## 评论（按点赞降序，共 {len(comments)} 条）")
    lines.append("")
    if not comments:
        lines.append("（未抓到评论——可能 xsec_token 缺失、评论被关或需手动粘贴）")
    else:
        for c in comments:
            reply = f" 💬{c['sub_comment_count']}" if c.get("sub_comment_count") else ""
            ip = f" [{c['ip_label']}]" if c.get("ip_label") else ""
            text = (c.get("text") or "").replace("\n", " ").strip()
            lines.append(f"- [👍{c['like_count']}{reply}]{ip} {text}")
    lines.append("")

    return "\n".join(lines)


def slugify(text: str, max_len: int = 30) -> str:
    bad = '<>:"/\\|?*\n\r\t'
    out = "".join("_" if ch in bad else ch for ch in text).strip()
    return out[:max_len] or "untitled"


def output_dir_for(note: dict, root: Path) -> Path:
    date = (note.get("post_time_str") or _fmt_time(note.get("create_time", 0)))[:10].replace("未知", "nodate")
    slug = slugify(note.get("title") or note["note_id"])
    return root / f"{date}_{slug}"
