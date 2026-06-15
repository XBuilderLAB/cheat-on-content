"""发完笔记后跑一次：抓数据 + 评论 → 生成 report.md。

用法：
    python review.py                       # 交互式选笔记
    python review.py login                 # 仅登录（首次扫码）
    python review.py list                  # 列最近笔记（验证登录态）
    python review.py note <note_id> [script.txt]   # 直接指定笔记
    python review.py archive <notes.json> [output_root] [limit]   # 批量归档正文+图片
    python review.py summarize [out_dir]   # 账号级汇总（基于最近 50 条）

archive / summarize 能力来自 xhs-analytics 的公开页解析，可无登录抓取正文与图片。
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import crawler
import renderer
from paths import runtime_project_root, videos_dir


LOG_FILE: io.TextIOWrapper | None = None


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line)
    except Exception:
        pass
    if LOG_FILE is not None:
        try:
            LOG_FILE.write(line + "\n")
            LOG_FILE.flush()
        except Exception:
            pass


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

    # 可选：下载图片到本地（默认关闭；通过环境变量 XHS_DOWNLOAD_IMAGES=1 开启）
    if os.environ.get("XHS_DOWNLOAD_IMAGES", "").lower() in ("1", "true", "yes"):
        img_dir = out_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        paths: list[str] = []
        for i, url in enumerate(note.get("images", []), 1):
            dest = img_dir / f"{i:02d}"
            if await crawler.download_image(url, dest):
                # download_image 会根据 Content-Type 修正扩展名，这里找回真实文件名
                actual = next(dest.parent.glob(f"{dest.name}.*"), dest)
                paths.append(str(actual.relative_to(out_dir)).replace("\\", "/"))
        if paths:
            note["image_paths"] = paths

    md = renderer.render_report(note, script, comments)
    report = out_dir / "report.md"
    report.write_text(md, encoding="utf-8")
    print(f"\n✓ {report}")


# ---------------------------------------------------------------------------
# archive: 批量归档已发布笔记的正文、图片、标签（公开页解析，无登录）
# ---------------------------------------------------------------------------

async def run_archive(input_path: Path, output_root: Path, limit: int | None = None,
                      max_comments: int = 0) -> None:
    global LOG_FILE
    output_root.mkdir(parents=True, exist_ok=True)
    log_path = output_root / f"archive_{time.strftime('%Y%m%d_%H%M%S')}.log"
    LOG_FILE = open(log_path, "w", encoding="utf-8", errors="replace")
    try:
        _log(f"启动归档: input={input_path}, output={output_root}")

        notes = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(notes, list):
            raise ValueError("输入 JSON 必须是笔记列表")

        notes = sorted(notes, key=lambda x: x.get("time", ""), reverse=True)
        if limit:
            notes = notes[:limit]

        results: list[dict] = []
        for i, note in enumerate(notes, 1):
            note_id = note.get("id") or note.get("note_id")
            xsec = note.get("xsecToken") or note.get("xsec_token", "")
            title = note.get("title", "")
            if not note_id or not xsec:
                results.append({
                    "success": False,
                    "note_id": note_id,
                    "error": "缺少 note_id 或 xsec_token",
                })
                continue

            out_dir = output_root / note_id
            _log(f"({i}/{len(notes)}) 归档 {note_id} {title[:30]}...")
            try:
                public = await asyncio.to_thread(crawler.fetch_public_note, note_id, xsec)
                if not public.get("success"):
                    err = public.get("error", "公开页解析失败")
                    _log(f"  -> 失败: {err}")
                    results.append({"success": False, "note_id": note_id, "error": err})
                    continue

                if max_comments > 0:
                    comments = await asyncio.to_thread(
                        crawler.fetch_public_comments, note_id, xsec, max_comments
                    )
                    public["comments"] = comments
                    public["comments_fetched"] = len(comments)

                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "note_detail.json").write_text(
                    json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8"
                )

                img_dir = out_dir / "images"
                img_dir.mkdir(parents=True, exist_ok=True)
                img_count = 0
                for idx, url in enumerate(public.get("images", []), 1):
                    if await crawler.download_image(url, img_dir / f"{idx:02d}"):
                        img_count += 1

                summary = {
                    "success": True,
                    "note_id": note_id,
                    "output_dir": str(out_dir),
                    "image_count": img_count,
                    "comment_count": public.get("comments_fetched", 0),
                }
                _log(f"  -> 完成: 图片 {img_count} 张")
                results.append(summary)
            except Exception as e:
                _log(f"  -> 异常: {e}")
                results.append({"success": False, "note_id": note_id, "error": str(e)})

            if i < len(notes):
                await asyncio.sleep(0.5)

        summary_path = output_root / f"archive_summary_{time.strftime('%Y%m%d_%H%M%S')}.json"
        summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        success = sum(1 for r in results if r.get("success"))
        _log(f"完成: 成功 {success}, 失败 {len(results) - success}, 总计 {len(results)}")
        _log(f"汇总: {summary_path}")
    finally:
        if LOG_FILE is not None:
            LOG_FILE.close()
            LOG_FILE = None


# ---------------------------------------------------------------------------
# summarize: 账号级汇总（基于创作者中心最近笔记 + 公开页标签）
# ---------------------------------------------------------------------------

def _series_of(note: dict) -> str:
    """按标签/标题关键字给笔记归系列，简单兜底。"""
    tags = note.get("tags") or []
    if tags:
        return tags[0]
    title = note.get("title", "")
    # 常见系列关键字（可扩展）
    for kw in ("Agent", "RAG", "CS336", "Lec", "MCP", "LLM"):
        if kw.lower() in title.lower():
            return kw
    return "其他"


def _summarize(notes: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# xhs-explore 账号汇总\n")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"样本数：{len(notes)} 篇\n")

    total_view = sum(n.get("view_count", 0) or 0 for n in notes)
    total_like = sum(n.get("like_count", 0) or 0 for n in notes)
    total_collect = sum(n.get("collect_count", 0) or 0 for n in notes)
    total_comment = sum(n.get("comment_count", 0) or 0 for n in notes)
    lines.append("## 整体数据\n")
    lines.append(f"- 总浏览：{total_view:,}")
    lines.append(f"- 总点赞：{total_like:,}")
    lines.append(f"- 总收藏：{total_collect:,}")
    lines.append(f"- 总评论：{total_comment:,}")
    if total_view:
        lines.append(f"- 平均赞阅比：{total_like / total_view * 100:.2f}%")
        lines.append(f"- 平均藏阅比：{total_collect / total_view * 100:.2f}%")
    lines.append("")

    # 按浏览 Top 10
    sorted_notes = sorted(notes, key=lambda x: x.get("view_count", 0) or 0, reverse=True)[:10]
    lines.append("## 浏览量 Top 10\n")
    lines.append("| 排名 | 标题 | 浏览 | 点赞 | 收藏 | 评论 |")
    lines.append("|------|------|------|------|------|------|")
    for idx, n in enumerate(sorted_notes, 1):
        title = (n.get("title") or "")[:30]
        lines.append(
            f"| {idx} | {title} | {n.get('view_count', 0):,} | "
            f"{n.get('like_count', 0)} | {n.get('collect_count', 0)} | {n.get('comment_count', 0)} |"
        )
    lines.append("")

    # 系列汇总
    series: dict[str, list[dict]] = defaultdict(list)
    for n in notes:
        series[_series_of(n)].append(n)
    lines.append("## 系列汇总（按首标签/标题关键字）\n")
    lines.append("| 系列 | 篇数 | 总浏览 | 均浏览 | 赞阅比 | 藏阅比 | 评阅比 |")
    lines.append("|------|------|--------|--------|--------|--------|--------|")
    for name, items in sorted(series.items(), key=lambda x: sum(i.get("view_count", 0) or 0 for i in x[1]), reverse=True):
        views = sum(i.get("view_count", 0) or 0 for i in items)
        likes = sum(i.get("like_count", 0) or 0 for i in items)
        collects = sum(i.get("collect_count", 0) or 0 for i in items)
        comments = sum(i.get("comment_count", 0) or 0 for i in items)
        avg_view = views / len(items) if items else 0
        like_rate = likes / views * 100 if views else 0
        collect_rate = collects / views * 100 if views else 0
        comment_rate = comments / views * 100 if views else 0
        lines.append(
            f"| {name} | {len(items)} | {views:,} | {avg_view:.0f} | "
            f"{like_rate:.2f}% | {collect_rate:.2f}% | {comment_rate:.2f}% |"
        )
    lines.append("")

    lines.append(
        "> 提示：系列判定优先取公开页标签，无标签时按标题关键字兜底。"
        "可通过 `review.py archive` 批量归档后人工校准。\n"
    )
    return "\n".join(lines)


async def run_summarize(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    print("[summarize] 拉取创作者中心最近 50 条笔记……")
    # summarize 是批量后台命令，用 headless 避免弹窗打扰
    sess = await crawler.Session.open(headless=True)
    try:
        notes = await crawler.fetch_recent_notes(sess, limit=50)
    finally:
        await sess.close()

    # 用公开页补全标签/正文/图片（失败也不阻塞）
    for n in notes:
        xsec = n.get("xsec_token") or ""
        if not xsec:
            continue
        try:
            public = await asyncio.to_thread(crawler.fetch_public_note, n["note_id"], xsec)
            crawler._merge_public_note(n, public)
        except Exception:
            pass

    md = _summarize(notes)
    out_path = out_dir / f"xhs_summary_{time.strftime('%Y%m%d_%H%M%S')}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"\n✓ {out_path}")


def _usage() -> str:
    return """
用法:
  python review.py                       交互式选笔记
  python review.py login                 扫码登录
  python review.py list                  列最近笔记
  python review.py note <note_id> [script.txt]
  python review.py archive <notes.json> [output_root] [limit]
  python review.py summarize [out_dir]
""".strip()


def main() -> None:
    # Windows Git Bash 等默认 GBK 控制台，emoji/中文 print 会崩溃，强制 UTF-8 输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    if len(sys.argv) > 1 and sys.argv[1] == "login":
        asyncio.run(crawler.ensure_login())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "note":
        if len(sys.argv) < 3:
            print("用法：python review.py note <note_id> [script.txt]")
            sys.exit(2)
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
    if len(sys.argv) > 1 and sys.argv[1] == "archive":
        if len(sys.argv) < 3:
            print(_usage())
            sys.exit(2)
        input_path = Path(sys.argv[2].strip('"').strip("'")).expanduser().resolve()
        output_root = Path(sys.argv[3]).expanduser().resolve() if len(sys.argv) > 3 else runtime_project_root() / "data" / "raw" / "notes" / "archive"
        limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
        asyncio.run(run_archive(input_path, output_root, limit=limit))
        return
    if len(sys.argv) > 1 and sys.argv[1] == "summarize":
        out_dir = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) > 2 else runtime_project_root() / "reports"
        asyncio.run(run_summarize(out_dir))
        return
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(_usage())
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
