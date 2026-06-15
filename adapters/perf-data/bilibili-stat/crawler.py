"""B站视频数据 + 评论抓取（公开接口，无需登录、无需签名）。

与 douyin-session / xhs-explore 不同：B站的视频统计与评论都是**公开数据**——
`view` 接口不需要 wbi 签名，评论走 `x/v2/reply` 老接口（按热度）。因此本 adapter
是纯 httpx，零登录、零浏览器，clone 下来即可用。

接口：
- 视频数据：https://api.bilibili.com/x/web-interface/view?bvid=<BV号>
- 评论：    https://api.bilibili.com/x/v2/reply?type=1&oid=<aid>&sort=2 （sort=2 热度）
"""
from __future__ import annotations

import re
import sys
import time

import httpx

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
VIEW_API = "https://api.bilibili.com/x/web-interface/view"
REPLY_API = "https://api.bilibili.com/x/v2/reply"


def normalize_bvid(raw: str) -> str:
    """从 BV 号或 B站视频 URL（含 b23.tv 短链跳转后）里提取 BV 号。"""
    m = re.search(r"(BV[0-9A-Za-z]{10})", raw or "")
    return m.group(1) if m else (raw or "").strip()


def _client() -> httpx.Client:
    return httpx.Client(headers=HEADERS, timeout=20, follow_redirects=True)


def fetch_video(client: httpx.Client, bvid: str) -> dict:
    """拉视频信息 + 统计。返回归一化后的 dict。"""
    resp = client.get(VIEW_API, params={"bvid": bvid})
    resp.raise_for_status()
    j = resp.json()
    if j.get("code") != 0:
        raise RuntimeError(f"view 接口失败 code={j.get('code')} msg={j.get('message')}")
    d = j.get("data") or {}
    stat = d.get("stat") or {}
    return {
        "bvid": d.get("bvid") or bvid,
        "aid": d.get("aid"),
        "title": d.get("title") or "",
        "desc": d.get("desc") or "",
        "owner": (d.get("owner") or {}).get("name") or "",
        "pubdate": d.get("pubdate") or 0,
        "duration_s": d.get("duration") or 0,
        "play_count": stat.get("view") or 0,
        "like_count": stat.get("like") or 0,
        "coin_count": stat.get("coin") or 0,
        "favorite_count": stat.get("favorite") or 0,
        "share_count": stat.get("share") or 0,
        "comment_count": stat.get("reply") or 0,
        "danmaku_count": stat.get("danmaku") or 0,
        "raw": d,
    }


def fetch_comments(client: httpx.Client, aid: int, max_count: int = 50) -> list[dict]:
    """按热度（sort=2）翻页抓评论，最多 max_count 条。"""
    out: list[dict] = []
    seen: set[str] = set()
    pn = 1
    for _ in range(60):  # 翻页上限保护
        if len(out) >= max_count:
            break
        try:
            j = client.get(
                REPLY_API,
                params={"type": 1, "oid": aid, "sort": 2, "pn": pn, "ps": 20},
            ).json()
        except Exception as exc:
            print(f"[警告] 评论请求异常（停止）：{exc}")
            break
        if j.get("code") != 0:
            print(f"[警告] 评论接口 code={j.get('code')} msg={j.get('message')}（停止）")
            break
        reps = (j.get("data") or {}).get("replies") or []
        if not reps:
            break
        for c in reps:
            nc = _normalize_comment(c)
            if nc["cid"] in seen:
                continue
            seen.add(nc["cid"])
            out.append(nc)
        pn += 1
        time.sleep(0.4)
    out.sort(key=lambda x: x["digg_count"], reverse=True)
    return out[:max_count]


def _normalize_comment(c: dict) -> dict:
    member = c.get("member") or {}
    content = c.get("content") or {}
    loc = (c.get("reply_control") or {}).get("location") or ""
    return {
        "cid": str(c.get("rpid") or ""),
        "text": content.get("message") or "",
        "digg_count": c.get("like") or 0,
        "reply_comment_total": c.get("rcount") or 0,
        "create_time": c.get("ctime") or 0,
        "user_name": member.get("uname") or "",
        "ip_label": loc.replace("IP属地：", "").replace("IP属地:", "").strip() if loc else "",
    }


def fetch_all(bvid: str, max_comments: int = 50) -> dict:
    """一次拉完视频数据 + 热门评论。"""
    bvid = normalize_bvid(bvid)
    with _client() as client:
        print(f"  → 拉取视频数据 {bvid}")
        video = fetch_video(client, bvid)
        print(f"       ✓ {video['title'][:40]}（播放 {video['play_count']}）")
        print("  → 拉取热门评论")
        if video.get("aid") is None:
            print("[警告] 视频数据缺少 aid 字段，无法拉取评论")
            comments = []
        else:
            comments = fetch_comments(client, video["aid"], max_count=max_comments)
        print(f"       ✓ {len(comments)} 条评论")
    return {"video": video, "comments": comments}


if __name__ == "__main__":
    # 与 douyin-session / xhs-explore 的接口保持一致；B站公开数据无需登录。
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        print("[B站] 视频数据与评论均为公开接口，无需登录，直接 /cheat-retro 即可。")
