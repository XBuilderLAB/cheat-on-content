"""小红书创作者中心 + 前台评论抓取。

登录一次后，Cookie 持久化在 .auth-xhs/，之后直接复用。
一次抓取共享一个 Chromium 会话，稳定性优于每步一个进程。

设计原则（和 douyin-session 一致）：
- 不逆向 x-s / x-t 签名、不伪造请求——用登录态浏览器，让页面自己发带签名的请求，
  我们只被动拦截返回的 JSON。
- 创作者**自己的**笔记数据走 galaxy 接口（不需要 xsec_token），是最稳的主路。
- 评论走前台 web API（需要 xsec_token），让页面自己导航触发带 token 的请求；
  拿不到就优雅降级（report.md 标 comments_unavailable，cheat-retro 回落到 manual 粘评论）。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, Page, Response, async_playwright
from paths import auth_dir, debug_dir

CREATOR_HOME = "https://creator.xiaohongshu.com/new/home"
CREATOR_NOTE_MANAGER = "https://creator.xiaohongshu.com/new/note-manager"
# galaxy 接口路径片段——宽松匹配，接口偶有版本号变化
GALAXY_NOTE_LIST_KEYS = (
    # 松匹配后缀，兼容 /api/galaxy/creator/... 与 /api/galaxy/v2/creator/...（实测是 v2）
    "/creator/note/user/posted",
)
GALAXY_NOTE_STATS_KEYS = (
    "/api/galaxy/creator/data/note_stats",
    "/api/galaxy/creator/data/note_detail",
)
# 前台 web API
FEED_KEY = "/api/sns/web/v1/feed"
COMMENT_KEY = "/api/sns/web/v2/comment/page"


class Session:
    """单浏览器会话，按顺序跑多步抓取。"""

    def __init__(self, ctx: BrowserContext, pw: Any) -> None:
        self.ctx = ctx
        self.pw = pw

    @classmethod
    async def open(cls, headless: bool = False) -> "Session":
        pw = await async_playwright().start()
        auth_path = auth_dir()
        auth_path.mkdir(parents=True, exist_ok=True)
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(auth_path),
            headless=headless,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        return cls(ctx, pw)

    async def close(self) -> None:
        try:
            await self.ctx.close()
        finally:
            await self.pw.stop()


# 创作者中心登录凭证——扫码登 creator.xiaohongshu.com 产生的就是这些（galaxy 主路只需它们）。
# 注意：创作者中心登录 *不* 产生 web_session（那是主站 www 前台 cookie），早期版本只认
# web_session 是个 bug，会导致登录成功却一直检测不到、白等超时。
CREATOR_LOGIN_COOKIES = (
    "access-token-creator.xiaohongshu.com",
    "galaxy_creator_session_id",
    "customer-sso-sid",
)
# 主站前台凭证——feed / 评论 web API 需要；只在登录后访问过 www 才会下发。
WEB_LOGIN_COOKIE = "web_session"


async def _cookie_map(ctx: BrowserContext, host: str) -> dict[str, str]:
    try:
        return {c["name"]: c.get("value", "") for c in await ctx.cookies(host)}
    except Exception:
        return {}


async def _creator_logged_in(ctx: BrowserContext) -> bool:
    names = await _cookie_map(ctx, "https://creator.xiaohongshu.com")
    return any(names.get(n) for n in CREATOR_LOGIN_COOKIES)


async def _has_web_session(ctx: BrowserContext) -> bool:
    for host in ("https://www.xiaohongshu.com", "https://creator.xiaohongshu.com"):
        if (await _cookie_map(ctx, host)).get(WEB_LOGIN_COOKIE):
            return True
    return False


async def _acquire_web_session(page: Page) -> None:
    """创作者中心登录后，访问主站让 SSO 下发 web_session（前台 feed/评论需要）。best-effort。"""
    try:
        await page.goto("https://www.xiaohongshu.com/explore",
                        wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        if await _has_web_session(page.context):
            print("[登录] ✓ 已获取主站 web_session（前台评论/互动可用）")
        else:
            print("[登录] 注意：未拿到 web_session，前台评论可能要 manual；galaxy 主路不受影响。")
    except Exception:
        pass


async def ensure_login(timeout_s: int = 300) -> bool:
    """扫码登录创作者中心；检测到创作者登录态后顺便换取 web_session，然后自动关闭。"""
    sess = await Session.open()
    try:
        page = await sess.ctx.new_page()
        await page.goto(CREATOR_HOME)
        print(f"[登录] 在弹出的 Chromium 窗口里扫码登录小红书创作者中心。最多等 {timeout_s} 秒……")
        for i in range(timeout_s):
            try:
                if await _creator_logged_in(sess.ctx) and "login" not in page.url:
                    print(f"[登录] ✓ 创作者中心登录态已确认（用时 {i}s）")
                    await _acquire_web_session(page)
                    await asyncio.sleep(1)
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        print("[登录] 超时未检测到登录态。")
        return False
    finally:
        await sess.close()


async def fetch_recent_notes(sess: Session, limit: int = 50) -> list[dict]:
    """创作者中心笔记管理页 → 拦截 galaxy 笔记列表 + 单篇运营数据（含曝光/浏览）。"""
    captured: list[dict] = []
    all_urls: list[str] = []

    page = await sess.ctx.new_page()

    async def on_response(resp: Response) -> None:
        all_urls.append(resp.url)
        if any(k in resp.url for k in GALAXY_NOTE_LIST_KEYS + GALAXY_NOTE_STATS_KEYS):
            try:
                data = await resp.json()
                captured.append({"url": resp.url, "data": data})
                if len(captured) == 1 and isinstance(data, dict):
                    print(f"[诊断] galaxy 接口 keys: {list(data.keys())[:8]}")
            except Exception:
                pass

    page.on("response", on_response)
    try:
        await page.goto(CREATOR_NOTE_MANAGER, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(8)
        for _ in range(4):
            await page.evaluate("window.scrollBy(0, 1200)")
            await asyncio.sleep(1.5)
        notes = _parse_note_list(captured, limit)
        if not notes:
            _dump(all_urls, "creator_urls.txt", captured, "creator_captured.json")
            print(f"[诊断] 笔记列表为空，{len(all_urls)} 个请求已 dump 到 .cheat-cache/xhs-explore-debug/。")
        return notes
    finally:
        await page.close()


def _iter_candidates(data: Any) -> list:
    """从任意 galaxy response 里挖出"笔记数组"。结构多变，宽松找。"""
    out: list = []
    if isinstance(data, dict):
        # 常见包装：{data: {...}} / {data: [...]} / 顶层直接 list 字段
        inner = data.get("data") if isinstance(data.get("data"), (dict, list)) else data
        targets = [inner] if not isinstance(inner, list) else []
        if isinstance(inner, list):
            out.extend(inner)
        for t in targets:
            if isinstance(t, dict):
                for key in ("notes", "note_list", "list", "items", "note_stats", "result"):
                    val = t.get(key)
                    if isinstance(val, list):
                        out.extend(val)
    return out


def _parse_note_list(captured: list[dict], limit: int) -> list[dict]:
    by_id: dict[str, dict] = {}
    for item in captured:
        for raw in _iter_candidates(item["data"]):
            if not isinstance(raw, dict):
                continue
            note = _normalize_note(raw)
            if not note["note_id"]:
                continue
            # 同一 note 可能在 list 接口和 stats 接口各出现一次——合并，非空字段优先
            existing = by_id.get(note["note_id"])
            if existing:
                for k, v in note.items():
                    if v and not existing.get(k):
                        existing[k] = v
            else:
                by_id[note["note_id"]] = note
    return list(by_id.values())[:limit]


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", 0):
            return v
    # 再扫一遍允许 0（区分"字段不存在"和"值为 0"）
    for k in keys:
        if k in d:
            return d[k]
    return 0


def _normalize_note(v: dict) -> dict:
    note_id = v.get("note_id") or v.get("id") or v.get("noteId") or ""
    # 字段名已用真实返回校准（2026-05 /api/galaxy/v2/creator/note/user/posted）：
    #   观看 view_count | 点赞 likes | 收藏 collected_count | 评论 comments_count
    #   分享 shared_count | 发布时间 visible_time(unix秒) | 单篇 token xsec_token
    # 确认名放首位，旧候选留作兜底以防接口再次改版。
    return {
        "note_id": str(note_id),
        "title": v.get("display_title") or v.get("title") or v.get("desc") or v.get("name") or "",
        "create_time": _to_int(_first(v, "visible_time", "create_time", "post_time", "publish_time")),
        "view_count": _to_int(_first(v, "view_count", "view", "imp", "impression", "read_count", "pv")),
        "like_count": _to_int(_first(v, "likes", "like_count", "liked_count", "like")),
        "collect_count": _to_int(_first(v, "collected_count", "collect_count", "collect", "fav_count")),
        "comment_count": _to_int(_first(v, "comments_count", "comment_count", "comment", "cmt_count")),
        "share_count": _to_int(_first(v, "shared_count", "share_count", "share")),
        "fans_inc": _to_int(_first(v, "fans", "fans_inc", "new_fans", "follow_count")),
        "post_time_str": v.get("time") or "",  # galaxy 自带本地时间串，比 epoch 省去时区换算
        "xsec_token": v.get("xsec_token") or "",
        "note_type": v.get("type") or "",
        "raw": v,
    }


def _to_int(x: Any) -> int:
    try:
        if isinstance(x, str):
            x = x.replace(",", "").strip()
        return int(float(x))
    except (ValueError, TypeError):
        return 0


async def fetch_note_frontend(sess: Session, note_id: str, note_url: str | None = None) -> dict:
    """打开前台笔记页 → 拦截 feed（interact_info 确认字段）+ comment/page。

    前台需要 xsec_token + 登录态（web_session）。
    - 若传入 note_url（含 xsec_token，如从创作者后台复制的 ?xsec_token=...&xsec_source=pc_creatormng）
      → 直接用它导航，最稳。
    - 否则退回裸 explore URL（仅对已登录账号访问自己笔记可能可行）。
    token 缺失 / 未登录 → dump 并降级（评论留给 manual）。
    """
    feed: dict = {}
    comments: list[dict] = []
    all_urls: list[str] = []

    page = await sess.ctx.new_page()

    async def on_response(resp: Response) -> None:
        all_urls.append(resp.url)
        if FEED_KEY in resp.url:
            try:
                data = await resp.json()
                ii = _extract_interact(data)
                if ii:
                    feed.update(ii)
            except Exception:
                pass
        elif COMMENT_KEY in resp.url:
            try:
                data = await resp.json()
                for c in _extract_comments(data):
                    comments.append(c)
            except Exception:
                pass

    page.on("response", on_response)
    try:
        url = note_url or f"https://www.xiaohongshu.com/explore/{note_id}"
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[警告] 笔记页加载异常：{e}")
        await asyncio.sleep(5)
        if "website-login/error" in page.url or "登录" in (await page.title()):
            print("[警告] 触发登录墙（安全限制）——cookie 未登录或已过期。先跑 crawler.py login 扫码。")

        # 滚动评论区触发分页懒加载
        last = 0
        stagnant = 0
        for _ in range(40):
            await page.evaluate("window.scrollBy(0, 1400)")
            await asyncio.sleep(1.8)
            cur = len({c["cid"] for c in comments})
            if cur == last:
                stagnant += 1
                if stagnant >= 5:
                    break
            else:
                stagnant = 0
                last = cur

        if not comments:
            dbg = debug_dir()
            dbg.mkdir(parents=True, exist_ok=True)
            try:
                await page.screenshot(path=str(dbg / f"note_{note_id}.png"))
            except Exception:
                pass
            (dbg / "frontend_urls.txt").write_text("\n".join(all_urls), encoding="utf-8")
            print("[诊断] 前台未拦到评论（可能 xsec_token 缺失或评论被关），已 dump URL。")

        # 去重 + 按赞降序
        seen = set()
        dedup = []
        for c in comments:
            if c["cid"] in seen:
                continue
            seen.add(c["cid"])
            dedup.append(c)
        dedup.sort(key=lambda x: x["like_count"], reverse=True)
        print(f"       前台共 {len(dedup)} 条评论")
        return {"interact": feed, "comments": dedup}
    finally:
        await page.close()


def _extract_interact(data: Any) -> dict:
    """从 feed response 里挖 interact_info（确认字段）。"""
    if not isinstance(data, dict):
        return {}
    items = []
    d = data.get("data", data)
    if isinstance(d, dict):
        items = d.get("items") or d.get("note_list") or []
    for it in items if isinstance(items, list) else []:
        node = it.get("note_card") or it.get("note") or it
        ii = node.get("interact_info") if isinstance(node, dict) else None
        if isinstance(ii, dict):
            return {
                "like_count": _to_int(ii.get("liked_count")),
                "collect_count": _to_int(ii.get("collected_count")),
                "comment_count": _to_int(ii.get("comment_count")),
                "share_count": _to_int(ii.get("share_count")),
                "ip_location": node.get("ip_location") or "",
            }
    return {}


def _extract_comments(data: Any) -> list[dict]:
    """comment/page response → 评论列表（确认字段）。"""
    out: list[dict] = []
    if not isinstance(data, dict):
        return out
    d = data.get("data", data)
    arr = d.get("comments") if isinstance(d, dict) else None
    for c in arr or []:
        if not isinstance(c, dict):
            continue
        user = c.get("user_info") or {}
        out.append({
            "cid": str(c.get("id") or c.get("comment_id") or ""),
            "text": c.get("content") or "",
            "like_count": _to_int(c.get("like_count")),
            "sub_comment_count": _to_int(c.get("sub_comment_count")),
            "create_time": c.get("create_time") or 0,
            "user_name": user.get("nickname") or "",
            "ip_label": c.get("ip_location") or "",
        })
    return out


def _dump(urls: list[str], url_file: str, captured: list[dict], cap_file: str) -> None:
    dbg = debug_dir()
    dbg.mkdir(parents=True, exist_ok=True)
    (dbg / url_file).write_text("\n".join(urls), encoding="utf-8")
    try:
        (dbg / cap_file).write_text(
            json.dumps([c["data"] for c in captured][:5], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


async def fetch_all(note_id: str, note_url: str | None = None) -> dict:
    """一个会话跑完笔记列表（含 galaxy 指标）+ 前台 interact + 评论。"""
    sess = await Session.open()
    try:
        print("  → 打开创作者中心，拉笔记列表 + 运营数据")
        notes = await fetch_recent_notes(sess, limit=50)
        note = next((n for n in notes if n["note_id"] == note_id), None)
        if not note:
            print(f"       未在最近 {len(notes)} 条里找到 {note_id}，用最小元数据继续。")
            note = _normalize_note({"note_id": note_id})
        else:
            print(f"       ✓ {(note.get('title') or '')[:40]}（曝光 {note.get('view_count')}）")

        # 抓自己的笔记时，galaxy 列表已带每条的 xsec_token——自动拼前台 URL，免得手动粘 token 链接
        front_url = note_url
        if not front_url and note.get("xsec_token"):
            front_url = (f"https://www.xiaohongshu.com/explore/{note_id}"
                         f"?xsec_token={note['xsec_token']}&xsec_source=pc_creatormng")

        print("  → 打开前台笔记页抓 interact + 评论")
        front = await fetch_note_frontend(sess, note_id, note_url=front_url)
        # 前台 interact 字段是确认的——用它补全/覆盖 galaxy 里可能缺的计数
        for k in ("like_count", "collect_count", "comment_count", "share_count"):
            if front["interact"].get(k):
                note[k] = front["interact"][k]
        if front["interact"].get("ip_location"):
            note["ip_location"] = front["interact"]["ip_location"]

        return {"note": note, "comments": front["comments"]}
    finally:
        await sess.close()


if __name__ == "__main__":
    asyncio.run(ensure_login())
