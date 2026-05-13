"""发完视频后跑一次：抓评论/数据 → 生成 NotebookLM 友好的 md。

用法：
    python review.py                          # 交互式选视频
    python review.py login                    # 仅登录（首次）
    python review.py video <aweme_id> [script.txt]   # 直接指定视频
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import crawler
import renderer
from paths import videos_dir


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError:
        return ""


def _pick_video(videos: list[dict]) -> dict | None:
    if not videos:
        print("未抓到视频列表。请确认创作者中心已登录，或页面结构已变，需要更新 crawler。")
        return None
    print("\n最近视频：")
    for i, v in enumerate(videos):
        t = renderer._fmt_time(v.get("create_time", 0))
        desc = (v.get("desc") or "").replace("\n", " ")[:40]
        print(f"  [{i}] {t} | 播放 {renderer._fmt_num(v.get('play_count'))} | {desc}")
    choice = _prompt("\n选择序号（回车取消）：")
    if not choice.isdigit():
        return None
    idx = int(choice)
    if 0 <= idx < len(videos):
        return videos[idx]
    return None


def _resolve_script(raw: str) -> str:
    """允许直接拖拽文件到终端；兼容 macOS 转义空格。"""
    p = raw.strip().strip("'").strip('"').replace("\\ ", " ")
    if not p:
        return ""
    path = Path(p).expanduser()
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    print(f"[警告] 找不到文件 {path}，稿子留空。")
    return ""


async def run() -> None:
    """交互式：先列最近 10 条，用户选一个，再让用户拖稿子，最后抓取。

    注意：会打开两次 Chromium（一次选视频，一次抓全量）。
    """
    active_videos_dir = videos_dir()
    active_videos_dir.mkdir(parents=True, exist_ok=True)

    print("[选视频] 打开创作者中心拉列表……")
    sess = await crawler.Session.open()
    try:
        videos = await crawler.fetch_recent_videos(sess, limit=10)
    finally:
        await sess.close()
    video = _pick_video(videos)
    if not video:
        print("已取消。")
        return

    script_raw = _prompt("把稿子 txt 拖进来（或回车跳过）：")
    script_path: str | None = None
    if script_raw.strip():
        p = Path(script_raw.strip().strip("'").strip('"').replace("\\ ", " ")).expanduser()
        if p.is_file():
            script_path = str(p)
        else:
            print(f"[警告] 找不到 {p}，稿子留空。")

    await run_with_id(video["aweme_id"], script_path)


async def run_with_id(aweme_id: str, script_path: str | None) -> None:
    active_videos_dir = videos_dir()
    active_videos_dir.mkdir(parents=True, exist_ok=True)

    script = ""
    if script_path:
        p = Path(script_path).expanduser()
        if p.is_file():
            script = p.read_text(encoding="utf-8", errors="ignore")
            print(f"稿子：{p.name}（{len(script)} 字符）")
        else:
            print(f"[警告] 找不到稿子 {p}")

    print(f"[抓取] 视频 {aweme_id}")
    result = await crawler.fetch_all(aweme_id)
    video = result["video"]
    detail = result["detail"]
    comments = result["comments"]

    out_dir = renderer.output_dir_for(video, active_videos_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if script:
        (out_dir / "script.txt").write_text(script, encoding="utf-8")
    md = renderer.render_report(video, script, comments, detail.get("captured"))
    report = out_dir / "report.md"
    report.write_text(md, encoding="utf-8")
    print(f"\n✓ {report}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        asyncio.run(crawler.ensure_login())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "video":
        aweme_id = sys.argv[2]
        script_path = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(run_with_id(aweme_id, script_path))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        async def _list() -> None:
            sess = await crawler.Session.open()
            try:
                videos = await crawler.fetch_recent_videos(sess, limit=20)
            finally:
                await sess.close()
            for i, v in enumerate(videos):
                t = renderer._fmt_time(v.get("create_time", 0))
                desc = (v.get("desc") or "").replace("\n", " ")[:50]
                print(f"[{i}] {v['aweme_id']}  {t}  播放{renderer._fmt_num(v.get('play_count'))}  {desc}")
        asyncio.run(_list())
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
