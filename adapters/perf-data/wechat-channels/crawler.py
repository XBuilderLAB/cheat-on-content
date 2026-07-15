"""视频号助手创作者后台抓取。

使用 Playwright 持久化登录态，被动监听后台页面自行发出的 JSON 请求。
不伪造签名，不读取微信客户端数据。
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from typing import Any

from playwright.async_api import BrowserContext, Page, Response, async_playwright

from paths import auth_dir

PLATFORM_HOME = "https://channels.weixin.qq.com/platform/"
CONTENT_URLS = (
    "https://channels.weixin.qq.com/platform/post/list",
    "https://channels.weixin.qq.com/platform/content",
    PLATFORM_HOME,
)


class Session:
    def __init__(self, ctx: BrowserContext, pw: Any) -> None:
        self.ctx = ctx
        self.pw = pw

    @classmethod
    async def open(cls, headless: bool = False) -> "Session":
        pw = await async_playwright().start()
        auth = auth_dir()
        auth.mkdir(parents=True, exist_ok=True)
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(auth),
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


async def _logged_in(page: Page) -> bool:
    if "login" in page.url.lower():
        return False
    try:
        body = await page.locator("body").inner_text(timeout=3000)
    except Exception:
        return False
    login_markers = ("扫码登录", "微信扫码", "登录视频号助手")
    account_markers = ("内容管理", "互动管理", "收入与服务", "视频号ID")
    return not any(x in body for x in login_markers) and any(x in body for x in account_markers)


async def ensure_login(timeout_s: int = 300) -> bool:
    sess = await Session.open()
    try:
        page = sess.ctx.pages[0] if sess.ctx.pages else await sess.ctx.new_page()
        await page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=60000)
        print(f"[登录] 请在弹出的窗口扫码登录视频号助手，最多等待 {timeout_s} 秒。")
        for i in range(timeout_s):
            if await _logged_in(page):
                print(f"[登录] ✓ 已检测到视频号助手登录态（用时 {i}s）")
                await asyncio.sleep(2)
                return True
            await asyncio.sleep(1)
        print("[登录] 超时，未检测到登录态。")
        return False
    finally:
        await sess.close()


def _first(obj: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return default


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _looks_like_post(obj: dict) -> bool:
    keys = set(obj)
    has_id = bool(keys & {"object_id", "objectId", "feed_id", "feedId", "post_id", "postId", "id"})
    has_metrics = bool(
        keys
        & {
            "read_count",
            "readCount",
            "play_count",
            "playCount",
            "like_count",
            "likeCount",
            "comment_count",
            "commentCount",
            "forward_count",
            "forwardCount",
        }
    )
    return has_id and has_metrics


def _text_from_desc(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, dict):
        return ""
    for key in ("description", "title", "content"):
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    short_title = value.get("shortTitle")
    if isinstance(short_title, list):
        labels = [
            item.get("shortTitle", "").strip()
            for item in short_title
            if isinstance(item, dict) and isinstance(item.get("shortTitle"), str)
        ]
        if labels:
            return " ".join(labels)
    return ""


def _normalize_post(obj: dict) -> dict:
    post_id = str(
        _first(obj, "object_id", "objectId", "feed_id", "feedId", "post_id", "postId", "id", default="")
    )
    title = ""
    for key in ("title", "description", "content"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            title = value.strip()
            break
    if not title:
        title = _text_from_desc(obj.get("desc"))
    create_time = _first(
        obj,
        "create_time",
        "createTime",
        "publish_time",
        "publishTime",
        "post_time",
        "postTime",
        default=0,
    )
    return {
        "post_id": post_id,
        "title": title,
        "create_time": create_time,
        "view_count": _first(obj, "read_count", "readCount", "play_count", "playCount", "view_count", default=0),
        "like_count": _first(obj, "like_count", "likeCount", "like_num", "likeNum", default=0),
        "favorite_count": _first(
            obj, "favorite_count", "favoriteCount", "fav_count", "favCount", "collect_count", default=0
        ),
        "comment_count": _first(obj, "comment_count", "commentCount", "comment_num", default=0),
        "share_count": _first(
            obj, "forward_count", "forwardCount", "share_count", "shareCount", "export_count", default=0
        ),
        "full_play_rate": _first(obj, "fullPlayRate", "full_play_rate", default=None),
        "avg_play_time_sec": _first(obj, "avgPlayTimeSec", "avg_play_time_sec", default=None),
        "follow_count": _first(obj, "followCount", "follow_count", default=0),
        "fast_flip_rate": _first(obj, "fastFlipRate", "fast_flip_rate", default=None),
        "yesterday_view_count": _first(obj, "yesterdayReadCount", "yesterday_read_count", default=0),
        "comments": obj.get("commentList") if isinstance(obj.get("commentList"), list) else [],
    }


def _dedupe_posts(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        post_id = item.get("post_id")
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        result.append(item)
    return result


async def _capture_json(
    response: Response,
    captured: list[dict],
    *,
    include_request_metadata: bool = False,
) -> None:
    content_type = (response.headers.get("content-type") or "").lower()
    if "json" not in content_type and not any(k in response.url.lower() for k in ("post", "feed", "finder", "data")):
        return
    try:
        data = await response.json()
    except Exception:
        return
    packet = {"data": data}
    if include_request_metadata:
        # Needed only in memory to paginate the selected post's comments.
        # These values are never written to disk or included in report.md.
        packet.update({"url": response.url, "post_data": response.request.post_data})
    captured.append(packet)


async def _click_text(page: Page, label: str) -> bool:
    for frame in page.frames:
        try:
            locator = frame.get_by_text(label, exact=True)
            if await locator.count():
                await locator.first.click(timeout=5000)
                return True
        except Exception:
            continue
    return False


async def fetch_recent_posts(sess: Session, limit: int = 50) -> list[dict]:
    captured: list[dict] = []
    page = await sess.ctx.new_page()

    async def on_response(response: Response) -> None:
        await _capture_json(response, captured)

    page.on("response", on_response)
    try:
        await page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # The content app is loaded dynamically after expanding the sidebar.
        # Click across all frames because Tencent occasionally mounts it in an iframe.
        if not await _click_text(page, "内容管理"):
            print("[诊断] 未找到“内容管理”入口。")
        await asyncio.sleep(4)

        # Content Management may open its own route before rendering the submenu.
        clicked_video = await _click_text(page, "视频")
        if not clicked_video:
            for url in CONTENT_URLS[:-1]:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(4)
                    if await _click_text(page, "视频"):
                        clicked_video = True
                        break
                except Exception:
                    continue
        await asyncio.sleep(8)

        for _ in range(5):
            await page.mouse.wheel(0, 1400)
            await asyncio.sleep(2)

        posts: list[dict] = []
        for packet in captured:
            for obj in _walk(packet["data"]):
                if _looks_like_post(obj):
                    posts.append(_normalize_post(obj))
        posts = _dedupe_posts(posts)

        if not posts:
            print(f"[诊断] 暂未解析到作品；本次在内存中检查了 {len(captured)} 个 JSON 响应，未写入原始数据。")
        return posts[:limit]
    finally:
        await page.close()


async def capture_comment_management(sess: Session, title_hint: str = "") -> dict:
    captured: list[dict] = []
    page = await sess.ctx.new_page()

    async def on_response(response: Response) -> None:
        await _capture_json(response, captured)

    page.on("response", on_response)
    try:
        await page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        if not await _click_text(page, "互动管理"):
            print("[诊断] 未找到“互动管理”入口。")
        await asyncio.sleep(4)
        if not await _click_text(page, "评论"):
            print("[诊断] 未找到“评论”子菜单。")
        await asyncio.sleep(10)

        clicked_post = False
        if title_hint:
            for frame in page.frames:
                try:
                    candidates = frame.get_by_text(re.compile(re.escape(title_hint[:12])))
                    if await candidates.count():
                        await candidates.first.click(timeout=5000)
                        clicked_post = True
                        break
                except Exception:
                    continue
        if not clicked_post:
            # Calibration fallback: click the second visible video row. The first
            # row may have zero comments; selecting another row triggers the
            # comment detail endpoint needed for field discovery.
            await page.mouse.click(480, 435)
        await asyncio.sleep(10)

        for _ in range(8):
            for frame in page.frames:
                try:
                    await frame.locator("body").first.evaluate("el => el.scrollBy(0, 1200)")
                except Exception:
                    continue
            await page.mouse.wheel(0, 1200)
            await asyncio.sleep(2)

        print(f"[评论诊断] 本次在内存中检查了 {len(captured)} 个 JSON 响应，未写入原始数据。")
        return {"captured_count": len(captured)}
    finally:
        await page.close()


def _normalize_comment(obj: dict, parent_id: str = "") -> dict:
    text = str(_first(obj, "commentContent", "content", "text", default="")).strip()
    text = text.replace("/:strong", "👍").replace("/:heart", "❤️")
    return {
        "comment_id": str(_first(obj, "commentId", "comment_id", "id", default="")),
        "text": text,
        "create_time": _first(obj, "commentCreatetime", "createTime", "create_time", default=0),
        "like_count": _first(obj, "commentLikeCount", "likeCount", "like_count", default=0),
        "parent_id": parent_id,
        "is_reply": bool(parent_id or obj.get("replyCommentId")),
    }


def _comments_from_payload(payload: dict) -> list[dict]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    if not isinstance(data, dict):
        return []
    roots = data.get("comment")
    if not isinstance(roots, list):
        return []
    comments: list[dict] = []

    def add(item: dict, parent_id: str = "") -> None:
        normalized = _normalize_comment(item, parent_id=parent_id)
        if normalized["comment_id"] and normalized["text"]:
            comments.append(normalized)
        replies = item.get("levelTwoComment")
        if isinstance(replies, list):
            for reply in replies:
                if isinstance(reply, dict):
                    add(reply, normalized["comment_id"])

    for root in roots:
        if isinstance(root, dict):
            add(root)
    return comments


def _dedupe_comments(comments: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for comment in comments:
        comment_id = comment.get("comment_id")
        if comment_id:
            by_id[comment_id] = comment
    return sorted(
        by_id.values(),
        key=lambda item: (int(item.get("like_count") or 0), int(item.get("create_time") or 0)),
        reverse=True,
    )


async def fetch_comments_creator(
    sess: Session,
    post_id: str,
    title_hint: str = "",
    max_pages: int = 20,
) -> list[dict]:
    captured: list[dict] = []
    page = await sess.ctx.new_page()

    async def on_response(response: Response) -> None:
        await _capture_json(response, captured, include_request_metadata=True)

    page.on("response", on_response)
    try:
        await page.goto(PLATFORM_HOME, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        await _click_text(page, "互动管理")
        await asyncio.sleep(3)
        await _click_text(page, "评论")
        await asyncio.sleep(8)

        clicked = False
        hint = re.sub(r"\s+", " ", title_hint).strip()[:12]
        for _ in range(30):
            if hint:
                for frame in page.frames:
                    try:
                        locator = frame.get_by_text(re.compile(re.escape(hint)))
                        if await locator.count():
                            await locator.first.click(timeout=5000)
                            clicked = True
                            break
                    except Exception:
                        continue
            if clicked:
                break
            # Scroll every likely list container to load older posts.
            for frame in page.frames:
                try:
                    await frame.locator("div").evaluate_all(
                        "els => els.forEach(el => { if (el.scrollHeight > el.clientHeight + 100) el.scrollTop += 900; })"
                    )
                except Exception:
                    continue
            await asyncio.sleep(2)

        if not clicked:
            print(f"[评论] 未在评论管理列表中定位作品：{title_hint[:30]}")
            return []
        await asyncio.sleep(8)

        packet = next(
            (
                item
                for item in reversed(captured)
                if "comment/comment_list" in item.get("url", "")
                and isinstance(item.get("post_data"), str)
            ),
            None,
        )
        if not packet:
            print("[评论] 点选作品后未捕获 comment_list 接口。")
            return []

        try:
            request_body = json.loads(packet["post_data"])
        except (TypeError, json.JSONDecodeError):
            request_body = {}
        # Refuse accidental cross-post data: the request must match the target.
        if request_body.get("exportId") != post_id:
            print("[评论] 捕获到的作品 ID 与目标不一致，停止以避免串评论。")
            return []

        all_comments = _comments_from_payload(packet["data"])
        page_data = packet["data"].get("data") or {}
        page_count = 1
        while page_count < max_pages and int(page_data.get("downContinueFlag") or 0):
            request_body["lastBuff"] = page_data.get("lastBuff") or ""
            request_body["timestamp"] = str(int(time.time() * 1000))
            response = await sess.ctx.request.post(
                packet["url"],
                data=request_body,
                headers={"content-type": "application/json"},
            )
            if not response.ok:
                break
            payload = await response.json()
            all_comments.extend(_comments_from_payload(payload))
            page_data = payload.get("data") or {}
            page_count += 1

        comments = _dedupe_comments(all_comments)
        print(f"[评论] 抓到 {len(comments)} 条（{page_count} 页）")
        return comments
    finally:
        await page.close()


async def fetch_post(sess: Session, post_id: str) -> dict:
    posts = await fetch_recent_posts(sess, limit=200)
    for post in posts:
        if post["post_id"] == post_id:
            return post
    raise LookupError(
        f"未在视频号助手最近 200 条作品中找到 post_id={post_id}。"
        "为避免把未知作品误记为 0 播放，本次不生成 report.md。"
    )


async def fetch_all(post_id: str) -> dict:
    sess = await Session.open()
    try:
        post = await fetch_post(sess, post_id)
        comments = [
            normalized
            for item in post.get("comments") or []
            if isinstance(item, dict)
            for normalized in (_normalize_comment(item),)
            if normalized["comment_id"] and normalized["text"]
        ]
        if int(post.get("comment_count") or 0) > 0:
            fetched = await fetch_comments_creator(sess, post_id, title_hint=post.get("title") or "")
            if fetched:
                comments = fetched
        return {"post": post, "comments": comments}
    finally:
        await sess.close()


if __name__ == "__main__":
    try:
        asyncio.run(ensure_login())
    except LookupError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(3) from exc
