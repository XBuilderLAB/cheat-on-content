from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import crawler
import renderer
from paths import videos_dir


async def list_posts() -> list[dict]:
    sess = await crawler.Session.open()
    try:
        return await crawler.fetch_recent_posts(sess, limit=50)
    finally:
        await sess.close()


async def run_with_id(post_id: str, script_path: str | None = None) -> None:
    script = ""
    if script_path:
        path = Path(script_path).expanduser()
        if path.is_file():
            script = path.read_text(encoding="utf-8", errors="ignore")

    result = await crawler.fetch_all(post_id)
    post = result["post"]
    root = videos_dir()
    root.mkdir(parents=True, exist_ok=True)
    output_override = os.environ.get("CHEAT_OUTPUT_DIR")
    out_dir = Path(output_override).expanduser().resolve() if output_override else renderer.output_dir_for(post, root)
    out_dir.mkdir(parents=True, exist_ok=True)
    if script:
        (out_dir / "script.txt").write_text(script, encoding="utf-8")
    report = out_dir / "report.md"
    report.write_text(renderer.render_report(post, script, result["comments"]), encoding="utf-8")
    print(f"✓ {report}")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    if command == "login":
        asyncio.run(crawler.ensure_login())
    elif command == "list":
        posts = asyncio.run(list_posts())
        for i, post in enumerate(posts):
            title = (post.get("title") or "").replace("\n", " ")[:50]
            print(
                f"[{i}] {post['post_id']}  {renderer._fmt_time(post.get('create_time'))}  "
                f"播放{renderer._fmt_num(post.get('view_count'))}  {title}"
            )
    elif command == "capture-comments":
        async def _capture() -> None:
            sess = await crawler.Session.open()
            try:
                hint = sys.argv[2] if len(sys.argv) > 2 else ""
                await crawler.capture_comment_management(sess, title_hint=hint)
            finally:
                await sess.close()
        asyncio.run(_capture())
    elif command in ("post", "video"):
        if len(sys.argv) < 3:
            raise SystemExit("Usage: review.py post <post_id> [script_path]")
        asyncio.run(run_with_id(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
    else:
        raise SystemExit("Usage: review.py login|list|capture-comments|post <post_id> [script_path]")


if __name__ == "__main__":
    try:
        main()
    except LookupError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(3) from exc
