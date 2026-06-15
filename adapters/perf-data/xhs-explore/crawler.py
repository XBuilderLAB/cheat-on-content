"""小红书创作者中心 + 前台评论抓取。

登录一次后，Cookie 持久化在 .auth-xhs/，之后直接复用。
一次抓取共享一个 Chromium 会话，稳定性优于每步一个进程。

设计原则（和 douyin-session 一致）：
- 不逆向 x-s / x-t 签名、不伪造请求——用登录态浏览器，让页面自己发带签名的请求，
  我们只被动拦截返回的 JSON。
- 创作者**自己的**笔记数据走 galaxy 接口（不需要 xsec_token），是最稳的主路。
- 评论走前台 web API（需要 xsec_token），让页面自己导航触发带 token 的请求；
  拿不到就优雅降级（report.md 标 comments_unavailable，cheat-retro 回落到 manual 粘评论）。

本文件新增的能力（来自 xhs-analytics 的公开页解析）：
- fetch_public_note: 无登录解析 explore 页面 __INITIAL_STATE__，拿正文 / 图片 / 标签。
- fetch_public_comments: 公开页兜底 top 评论。
- download_image: 下载笔记图片到本地。
"""
from __future__ import annotations

import asyncio
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

import requests
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

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


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
        common_kwargs = {
            "user_data_dir": str(auth_path),
            "headless": headless,
            "viewport": {"width": 1440, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        try:
            ctx = await pw.chromium.launch_persistent_context(**common_kwargs)
        except Exception as exc:
            # 部分环境只装了系统 Chrome，没下载 Playwright Chromium，fallback 到 channel=chrome
            try:
                ctx = await pw.chromium.launch_persistent_context(
                    **common_kwargs, channel="chrome"
                )
            except Exception:
                raise exc
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


async def ensure_login(timeout_s: int = 180, max_refresh: int = 5) -> bool:
    """扫码登录创作者中心；检测到创作者登录态后顺便换取 web_session，然后自动关闭。

    二维码本身会过期，所以用 timeout_s 作为单次等待上限，超时后自动刷新页面重新出码，
    最多刷新 max_refresh 次。用户有充足时间扫码。
    """
    sess = await Session.open()
    try:
        page = await sess.ctx.new_page()
        await page.goto(CREATOR_HOME)
        print(f"[登录] 在弹出的 Chromium 窗口里扫码登录小红书创作者中心。每次二维码有效期约 {timeout_s} 秒，超时自动刷新。")

        for refresh in range(max_refresh + 1):
            for i in range(timeout_s):
                try:
                    if await _creator_logged_in(sess.ctx) and "login" not in page.url:
                        print(f"[登录] ✓ 创作者中心登录态已确认（总用时 {refresh * timeout_s + i}s）")
                        await _acquire_web_session(page)
                        await asyncio.sleep(1)
                        return True
                except Exception:
                    pass

                # 每 30 秒提醒一次，避免用户以为卡死
                if i > 0 and i % 30 == 0:
                    print(f"[登录] 已等待 {i} 秒，请用小红书 App 扫码（或等待自动刷新二维码）……")

                await asyncio.sleep(1)

            if refresh < max_refresh:
                print(f"[登录] 本次二维码未扫码或已过期，正在刷新页面重新出码（第 {refresh + 1}/{max_refresh} 次刷新）……")
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    await page.goto(CREATOR_HOME)

        print("[登录] 超过最大刷新次数仍未检测到登录态，已停止。如需继续请重新运行本命令。")
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
        # cookie 过期时会被 302 到登录页
        if "login" in page.url or "redirectReason=401" in page.url:
            print("[登录] 创作者中心已跳转登录页，cookie 可能已过期。请运行：python crawler.py login")
            return []
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
        if k in d and d[k] is not None and d[k] != "":
            return d[k]
    for k in keys:
        if k in d and d[k] is not None:
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


# ---------------------------------------------------------------------------
# 公开页解析（来自 xhs-analytics 的核心能力）：无登录拿正文、图片、标签、评论兜底
# ---------------------------------------------------------------------------

def _extract_initial_state(html: str) -> dict | None:
    """从小红书 explore 页面 HTML 中解析 window.__INITIAL_STATE__。"""
    marker = "window.__INITIAL_STATE__="
    start = html.find(marker)
    if start == -1:
        return None
    script_start = html.rfind("<script", 0, start)
    script_end = html.find("</script>", start)
    if script_start == -1 or script_end == -1:
        return None
    script = html[script_start:script_end]
    assign_start = script.find(marker) + len(marker)
    json_str = script[assign_start:]
    json_str = re.sub(r":\s*undefined\s*([,}\]])", r":null\1", json_str)
    json_str = json_str.rstrip().rstrip(';').rstrip()
    try:
        return json.loads(json_str)
    except Exception:
        return None


def _image_url(img: dict) -> str:
    """从 imageList 元素中提取可用的图片 URL。"""
    if not isinstance(img, dict):
        return ""
    for key in ("urlDefault", "url"):
        if img.get(key):
            return img[key]
    for info in img.get("infoList", []) or []:
        if isinstance(info, dict) and info.get("imageScene") == "WB_DFT" and info.get("url"):
            return info["url"]
    for info in img.get("infoList", []) or []:
        if isinstance(info, dict) and info.get("url"):
            return info["url"]
    return ""


def _xsec_token_from_url(url: str | None) -> str:
    """从笔记 URL 的 query 中拆出 xsec_token（保留原编码）。"""
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.unquote(urllib.parse.parse_qs(parsed.query).get("xsec_token", [""])[0])


def fetch_public_note(note_id: str, xsec_token: str) -> dict:
    """无登录抓取 explore 公开页，解析 __INITIAL_STATE__。

    返回 dict：success, note_id, title, desc/body, images, tags, time, counts, raw。
    """
    token = urllib.parse.unquote(xsec_token)
    url = (
        f"https://www.xiaohongshu.com/explore/{note_id}"
        f"?xsec_token={urllib.parse.quote(token)}"
        f"&xsec_source=pc_creatormng"
    )
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()

    state = _extract_initial_state(r.text)
    if not state:
        raise ValueError("无法解析页面初始状态")

    note_detail_map = state.get("note", {}).get("noteDetailMap", {})
    if note_id not in note_detail_map:
        raise ValueError("页面未返回该笔记数据")

    raw = note_detail_map[note_id]
    note = raw.get("note", {})
    interact = note.get("interactInfo", {})

    return {
        "success": True,
        "note_id": note_id,
        "title": note.get("title", ""),
        "desc": note.get("desc", ""),
        "body": note.get("desc", ""),
        "type": note.get("type", ""),
        "time": note.get("time", 0),
        "images": [_image_url(img) for img in note.get("imageList", [])],
        "tags": [tag.get("name", "") for tag in note.get("tagList", []) if tag.get("name")],
        "counts": {
            "liked": _to_int(interact.get("likedCount")),
            "collected": _to_int(interact.get("collectedCount")),
            "comment": _to_int(interact.get("commentCount")),
            "shared": _to_int(interact.get("shareCount")),
        },
        "raw": raw,
    }


def _normalize_public_comment(c: dict) -> dict:
    """把 __INITIAL_STATE__ / edith 接口里的评论字段统一成 adapter 格式。"""
    user = c.get("user_info") or c.get("userInfo") or {}
    like_count = c.get("like_count") or c.get("likeCount") or 0
    sub_count = c.get("sub_comment_count") or c.get("subCommentCount") or 0
    return {
        "cid": str(c.get("id") or c.get("comment_id") or ""),
        "text": c.get("content") or "",
        "like_count": _to_int(like_count),
        "sub_comment_count": _to_int(sub_count),
        "create_time": c.get("create_time") or c.get("createTime") or 0,
        "user_name": user.get("nickname") or "",
        "ip_label": c.get("ip_location") or c.get("ipLocation") or "",
    }


def fetch_public_comments(note_id: str, xsec_token: str, max_comments: int = 20) -> list[dict]:
    """公开页 __INITIAL_STATE__ 兜底 top 评论（通常 ~10 条）。"""
    token = urllib.parse.unquote(xsec_token)
    url = (
        f"https://www.xiaohongshu.com/explore/{note_id}"
        f"?xsec_token={urllib.parse.quote(token)}"
        f"&xsec_source=pc_creatormng"
    )
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    state = _extract_initial_state(r.text)
    if not state:
        return []

    raw = state.get("note", {}).get("noteDetailMap", {}).get(note_id, {})
    comments = []
    # __INITIAL_STATE__ 里的评论路径可能是 comments.list 或 commentsList
    for key in ("comments", "commentsList"):
        container = raw.get(key) if isinstance(raw, dict) else None
        if isinstance(container, dict):
            arr = container.get("list") or container.get("comments") or []
            if isinstance(arr, list):
                comments.extend([_normalize_public_comment(c) for c in arr])
        elif isinstance(container, list):
            comments.extend([_normalize_public_comment(c) for c in container])

    seen = set()
    dedup = []
    for c in comments:
        if not c["cid"] or c["cid"] in seen:
            continue
        seen.add(c["cid"])
        dedup.append(c)
    dedup.sort(key=lambda x: x["like_count"], reverse=True)
    return dedup[:max_comments]


async def download_image(url: str, dest: Path, timeout: int = 30) -> bool:
    """下载单张图片到 dest（会根据 Content-Type 修正扩展名）。异步封装。"""
    if not url:
        return False
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def _download() -> bool:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        }
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)
        r.raise_for_status()

        parsed = urllib.parse.urlparse(url)
        path = urllib.parse.unquote(parsed.path)
        ext = Path(path).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
            ct = r.headers.get("Content-Type", "").lower()
            if "webp" in ct:
                ext = ".webp"
            elif "png" in ct:
                ext = ".png"
            elif "gif" in ct:
                ext = ".gif"
            else:
                ext = ".jpg"
        dest_final = dest.with_suffix(ext)

        with open(dest_final, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True

    try:
        return await asyncio.to_thread(_download)
    except Exception as exc:
        print(f"[下载图片] 失败 {url}: {exc}")
        return False


async def fetch_note_frontend(
    sess: Session,
    note_id: str,
    note_url: str | None = None,
    xsec_token: str | None = None,
) -> dict:
    """打开前台笔记页 → 拦截 feed（interact_info 确认字段）+ comment/page。

    前台需要 xsec_token + 登录态（web_session）。
    - 若传入 note_url（含 xsec_token，如从创作者后台复制的 ?xsec_token=...&xsec_source=pc_creatormng）
      → 直接用它导航，最稳。
    - 否则退回裸 explore URL（仅对已登录账号访问自己笔记可能可行）。
    token 缺失 / 未登录 → dump 并降级（评论留给 manual）。

    拦截不到评论时，会用公开页 __INITIAL_STATE__ 里的 top 评论兜底。
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

        # 兜底：公开页 __INITIAL_STATE__ 里的 top 评论
        if not comments:
            xsec = xsec_token or _xsec_token_from_url(note_url)
            if xsec:
                try:
                    public_comments = await asyncio.to_thread(
                        fetch_public_comments, note_id, xsec, max_comments=20
                    )
                    if public_comments:
                        comments = public_comments
                        print(f"       公开页兜底 {len(comments)} 条评论")
                except Exception as exc:
                    print(f"[诊断] 公开页评论兜底失败：{exc}")

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


def _merge_public_note(note: dict, public: dict) -> None:
    """用公开页数据补全 note（不覆盖已有的 galaxy 运营数据）。"""
    if not public.get("success"):
        return
    for key in ("title", "desc", "body", "type", "images", "tags"):
        if public.get(key) and not note.get(key):
            note[key] = public[key]
    if public.get("time") and not note.get("create_time"):
        note["create_time"] = _to_int(public["time"])
    counts = public.get("counts") or {}
    mapping = {
        "like_count": counts.get("liked"),
        "collect_count": counts.get("collected"),
        "comment_count": counts.get("comment"),
        "share_count": counts.get("shared"),
    }
    for k, v in mapping.items():
        if v and not note.get(k):
            note[k] = _to_int(v)


async def fetch_all(note_id: str, note_url: str | None = None) -> dict:
    """一个会话跑完笔记列表（含 galaxy 指标）+ 前台 interact + 评论 + 公开页正文/图片兜底。"""
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

        xsec = _xsec_token_from_url(front_url) or note.get("xsec_token", "")

        # 先用公开页补正文/图片/标签（无登录、低成本），不覆盖 galaxy 已确认的计数
        if xsec:
            try:
                public = await asyncio.to_thread(fetch_public_note, note_id, xsec)
                _merge_public_note(note, public)
                print("       ✓ 公开页正文/图片/标签已补全")
            except Exception as exc:
                print(f"[诊断] 公开页兜底失败：{exc}")

        print("  → 打开前台笔记页抓 interact + 评论")
        front = await fetch_note_frontend(sess, note_id, note_url=front_url, xsec_token=xsec)
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
