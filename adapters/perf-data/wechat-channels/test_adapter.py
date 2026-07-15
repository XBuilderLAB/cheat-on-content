from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ADAPTER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ADAPTER_DIR))

import paths  # noqa: E402
import renderer  # noqa: E402


class PrivacyBoundaryTests(unittest.TestCase):
    def test_report_excludes_raw_and_comment_identity_fields(self) -> None:
        post = {
            "post_id": "own-post-123",
            "title": "自己的作品",
            "view_count": 10,
            "raw": {"signed_url": "https://media.example/video?signature=secret"},
        }
        comments = [
            {
                "comment_id": "internal-comment-id",
                "nickname": "internal-user-name",
                "text": "有帮助",
                "like_count": 2,
            }
        ]

        report = renderer.render_report(post, "稿子", comments)

        self.assertIn("有帮助", report)
        self.assertNotIn("internal-comment-id", report)
        self.assertNotIn("internal-user-name", report)
        self.assertNotIn("signature=secret", report)

    def test_crawler_does_not_persist_raw_browser_artifacts(self) -> None:
        source = (ADAPTER_DIR / "crawler.py").read_text(encoding="utf-8")

        self.assertNotIn(".write_text(", source)
        self.assertNotIn(".screenshot(", source)
        self.assertNotIn("debug_dir", source)


class RuntimePathTests(unittest.TestCase):
    def test_explicit_project_root_wins_over_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as cwd:
            result = paths.runtime_project_root(
                env={"CHEAT_PROJECT_ROOT": project},
                cwd=Path(cwd),
            )

        self.assertEqual(result, Path(project).resolve())


if __name__ == "__main__":
    unittest.main()
