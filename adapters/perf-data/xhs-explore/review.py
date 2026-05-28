"""发完笔记后跑一次：抓数据 + 评论 → 生成 report.md。

用法：
    python review.py                       # 交互式选笔记
    python review.py login                 # 仅登录（首次扫码）
    python review.py list                  # 列最近笔记（验证登录态）
    python review.py note <note_id> [script.txt]   # 直接指定笔记
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import crawler
import renderer
from paths import videos_dir


def _parse_note_arg(arg: str) -> tuple[str, str | None]:
    """接受 note_id 或完整笔记 URL（含 xsec_token）。返回 (note_id, note_url|None)。"""
    arg = arg.strip().strip("'").strip('"')
    if arg.startswith("http"):
        m = re.search(r"/(?:explore|discovery/item)/([0-9a-zA-Z]+)", arg)
        note_id = m.group(1) if m else arg
        return note_id, arg
    return arg, None


def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except EOFError:
        return ""


def _pick_note(notes: list[dict]) -> dict | None:
    if not notes:
        print("未抓到笔记列表。请确认创作者中心已登录，或页面结构已变，需要更新 crawler。")
        return None
    print("\n最近笔记：")
    for i, n in enumerate(notes):
        t = renderer._fmt_time(n.get("create_time", 0))
        title = (n.get("title") or "").replace("\n", " ")[:40]
        print(f"  [{i}] {t} | 曝光 {renderer._fmt_num(n.get('view_count'))} | {title}")
    choice = _prompt("\n选择序号（回车取消）：")
    if not choice.isdigit():
        return None
    idx = int(choice)
    if 0 <= idx < len(notes):
        return notes[idx]
    return None


async def run() -> None:
    active_videos_dir = videos_dir()
    active_videos_dir.mkdir(parents=True, exist_ok=True)

    print("[选笔记] 打开创作者中心拉列表……")
    sess = await crawler.Session.open()
    try:
        notes = await crawler.fetch_recent_notes(sess, limit=10)
    finally:
        await sess.close()
    note = _pick_note(notes)
    if not note:
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

    await run_with_id(note["note_id"], script_path)


async def run_with_id(note_arg: str, script_path: str | None) -> None:
    active_videos_dir = videos_dir()
    active_videos_dir.mkdir(parents=True, exist_ok=True)

    note_id, note_url = _parse_note_arg(note_arg)

    script = ""
    if script_path:
        p = Path(script_path).expanduser()
        if p.is_file():
            script = p.read_text(encoding="utf-8", errors="ignore")
            print(f"稿子：{p.name}（{len(script)} 字符）")
        else:
            print(f"[警告] 找不到稿子 {p}")

    print(f"[抓取] 笔记 {note_id}" + ("（带 token URL）" if note_url else ""))
    result = await crawler.fetch_all(note_id, note_url=note_url)
    note = result["note"]
    comments = result["comments"]

    out_dir = renderer.output_dir_for(note, active_videos_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if script:
        (out_dir / "script.txt").write_text(script, encoding="utf-8")
    md = renderer.render_report(note, script, comments)
    report = out_dir / "report.md"
    report.write_text(md, encoding="utf-8")
    print(f"\n✓ {report}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        asyncio.run(crawler.ensure_login())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "note":
        note_id = sys.argv[2]
        script_path = sys.argv[3] if len(sys.argv) > 3 else None
        asyncio.run(run_with_id(note_id, script_path))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        async def _list() -> None:
            sess = await crawler.Session.open()
            try:
                notes = await crawler.fetch_recent_notes(sess, limit=20)
            finally:
                await sess.close()
            for i, n in enumerate(notes):
                t = renderer._fmt_time(n.get("create_time", 0))
                title = (n.get("title") or "").replace("\n", " ")[:50]
                print(f"[{i}] {n['note_id']}  {t}  曝光{renderer._fmt_num(n.get('view_count'))}  {title}")
        asyncio.run(_list())
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
