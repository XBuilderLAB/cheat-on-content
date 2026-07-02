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
    if isinstance(n, str):
        try:
            n = int(float(n))
        except ValueError:
            return n
    if n >= 10000:
        return f"{n/10000:.1f}w"
    return str(n)


def _fmt_float(v, digits: int = 2) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_percent(v) -> str:
    if v is None:
        return "-"
    try:
        return f"{float(v) * 100:.2f}%"
    except (TypeError, ValueError):
        return str(v)


def _fmt_duration(ms: int) -> str:
    if not ms:
        return "-"
    s = ms // 1000
    return f"{s//60}:{s%60:02d}" if s >= 60 else f"{s}s"


def _first_metrics(detail_captured: list[dict] | None) -> dict:
    if not detail_captured:
        return {}
    for item in detail_captured:
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        items = data.get("items")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            metrics = items[0].get("metrics")
            if isinstance(metrics, dict):
                return metrics
        item_data = data.get("item")
        if isinstance(item_data, dict) and isinstance(item_data.get("metrics"), dict):
            return item_data["metrics"]
    return {}


def _detail_sample_items(detail_captured: list[dict]) -> list[dict]:
    samples = detail_captured[:3]
    sample_urls = {item.get("url") for item in samples}
    for item in detail_captured[3:]:
        url = item.get("url") or ""
        if item.get("url") in sample_urls:
            continue
        if any(k in url for k in ("comment", "keyword", "hot_word", "hotword")):
            samples.append(item)
            break
    return samples


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

    metrics = _first_metrics(detail_captured)
    if metrics:
        lines.append("### 详细指标（来自创作者中心）")
        lines.append("")
        detail_rows = [
            ("播放", _fmt_num(metrics.get("view_count"))),
            ("完播率", _fmt_percent(metrics.get("completion_rate"))),
            ("5s 完播率", _fmt_percent(metrics.get("completion_rate_5s"))),
            ("2s 划走率", _fmt_percent(metrics.get("bounce_rate_2s"))),
            (
                "平均观看时长",
                f"{_fmt_float(metrics.get('avg_view_second'))}s"
                if metrics.get("avg_view_second") is not None
                else "-",
            ),
            ("文案展开率", _fmt_percent(metrics.get("description_spread_rate"))),
            ("文案读完率", _fmt_percent(metrics.get("description_completion_rate"))),
            ("平均浏览图片数", _fmt_float(metrics.get("image_avg_view_count"))),
            ("粉丝播放占比", _fmt_percent(metrics.get("fan_view_proportion"))),
            ("主页访问", _fmt_num(metrics.get("homepage_visit_count"))),
            ("涨粉", _fmt_num(metrics.get("subscribe_count"))),
            ("脱粉", _fmt_num(metrics.get("unsubscribe_count"))),
        ]
        for label, value in detail_rows:
            if value != "-":
                lines.append(f"- {label}：{value}")
        lines.append("")

    if detail_captured:
        lines.append("### 详细接口原始样例")
        lines.append("")
        lines.append("```json")
        import json
        for item in _detail_sample_items(detail_captured):
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
