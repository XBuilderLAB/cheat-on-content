"""Tests for hooks/prediction-immutability.sh. Runs the real bash script.

Run:  python -m unittest test_hooks.py   (from hooks/)
Set CHEAT_BASH to a bash binary if `bash` on PATH is not a real bash.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def find_bash() -> str | None:
    if os.environ.get("CHEAT_BASH"):
        return os.environ["CHEAT_BASH"]
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    return None


BASH = find_bash()

PRED = """# 停止期待 — 预测日志

**Article ID**: abc
**Title**: 停止期待

---

## 输入快照

**分数 (v1)**: ER5 / HP4 → composite=**7.60**

## 预测 v1

**Bucket**: `30-100w`
**中枢**: 50w

## 推理因素

| ER=5 | 强 + |

## 锚点对比

本篇 vs 谁问你了 = 1.5x

## 反事实场景（复盘用）

**如果爆**: 说明 ER 被低估

## 关键校准假设

**我押**：本篇 vs 对照 = 1.5 倍

## 预测 v2 (replaces v1)

**中枢**: 40w

## 复盘

（待填——T+3 天后跑 /cheat-retro）
"""


@unittest.skipIf(BASH is None, "no usable bash found")
class TestImmutability(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)
        (self.proj / "predictions").mkdir()
        self.pred = self.proj / "predictions" / "2026-05-04_abc_停止期待.md"
        self.pred.write_text(PRED, encoding="utf-8", newline="\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_hook(self, payload: dict, env_extra: dict | None = None):
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.proj), **(env_extra or {}))
        completed = subprocess.run(
            [BASH, str(HERE / "prediction-immutability.sh")],
            input=json.dumps(payload).encode("utf-8"),
            capture_output=True,
            env=env,
            timeout=60,
        )
        return completed.returncode, completed.stderr.decode("utf-8", "replace")

    def edit(self, old, new="X", path=None, tool="Edit"):
        return {
            "tool_name": tool,
            "tool_input": {"file_path": str(path or self.pred), "old_string": old, "new_string": new},
        }

    def test_edit_prediction_blocked_with_exit_2(self):
        code, err = self.run_hook(self.edit("**中枢**: 50w"))
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", err)

    def test_reasoning_anchors_counterfactuals_and_scores_are_locked(self):
        for old in (
            "**分数 (v1)**: ER5 / HP4",
            "| ER=5 | 强 + |",
            "本篇 vs 谁问你了 = 1.5x",
            "**如果爆**: 说明 ER 被低估",
            "**我押**：本篇 vs 对照 = 1.5 倍",
            "**中枢**: 40w",
        ):
            self.assertEqual(self.run_hook(self.edit(old))[0], 2, old)

    def test_header_edit_allowed(self):
        self.assertEqual(self.run_hook(self.edit("**Title**: 停止期待"))[0], 0)

    def test_retro_append_allowed(self):
        self.assertEqual(self.run_hook(self.edit("（待填——T+3 天后跑 /cheat-retro）"))[0], 0)

    def test_edit_spanning_into_prediction_blocked(self):
        old = "**中枢**: 40w\n\n## 复盘"
        self.assertEqual(self.run_hook(self.edit(old))[0], 2)

    def test_v2_insert_before_retro_allowed(self):
        old = "## 复盘\n"
        new = "## 预测 v3 (replaces v1)\n\n**中枢**: 45w\n\n## 复盘\n"
        self.assertEqual(self.run_hook(self.edit(old, new))[0], 0)

    def test_non_prediction_file_in_predictions_dir_allowed(self):
        other = self.proj / "predictions" / "README.md"
        other.write_text("# notes\n\n## 说明\n\nfoo\n", encoding="utf-8", newline="\n")
        self.assertEqual(self.run_hook(self.edit("foo", path=other))[0], 0)

    def test_write_existing_blocked_new_allowed(self):
        overwrite = {"tool_name": "Write", "tool_input": {"file_path": str(self.pred), "content": "x"}}
        self.assertEqual(self.run_hook(overwrite)[0], 2)
        create = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(self.proj / "predictions" / "new.md"), "content": "x"},
        }
        self.assertEqual(self.run_hook(create)[0], 0)

    def test_outside_predictions_allowed(self):
        other = self.proj / "notes.md"
        other.write_text(PRED, encoding="utf-8", newline="\n")
        self.assertEqual(self.run_hook(self.edit("**中枢**: 50w", path=other))[0], 0)

    def test_multiedit_blocked_when_any_edit_hits_the_body(self):
        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": str(self.pred),
                "edits": [
                    {"old_string": "**Title**: 停止期待", "new_string": "a"},
                    {"old_string": "**Bucket**: `30-100w`", "new_string": "b"},
                ],
            },
        }
        self.assertEqual(self.run_hook(payload)[0], 2)

    def test_windows_backslash_path(self):
        payload = self.edit("**中枢**: 50w", path=str(self.pred).replace("/", "\\"))
        self.assertEqual(self.run_hook(payload)[0], 2)

    def test_bypass(self):
        code, _err = self.run_hook(self.edit("**中枢**: 50w"), {"CHEAT_BYPASS_IMMUTABILITY": "1"})
        self.assertEqual(code, 0)


class TestSkillFrontmatter(unittest.TestCase):
    """An unquoted argument-hint that contains ': ' is a YAML mapping, so the skill fails to load."""

    def test_argument_hints_with_colons_are_quoted(self):
        files = [ROOT / "SKILL.md", *sorted((ROOT / "skills").glob("*/SKILL.md"))]
        self.assertGreaterEqual(len(files), 15)
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---"), path.name)
            frontmatter = text.split("---", 2)[1]
            for line in frontmatter.splitlines():
                if not line.startswith("argument-hint:"):
                    continue
                value = line.split(":", 1)[1].strip()
                if value[:1] in ("'", '"', "|", ">"):
                    continue
                self.assertNotIn(": ", value, f"{path} has an unquoted argument-hint containing ': '")


if __name__ == "__main__":
    unittest.main()
