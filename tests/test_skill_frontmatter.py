from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SkillFrontmatterTest(unittest.TestCase):
    def test_argument_hints_are_strings(self):
        paths = [ROOT / "SKILL.md", *sorted((ROOT / "skills").glob("*/SKILL.md"))]
        self.assertGreaterEqual(len(paths), 17)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            frontmatter = text.split("---", 2)[1]
            match = re.search(r"^argument-hint:\s*(.+)$", frontmatter, re.MULTILINE)
            if not match:
                continue
            value = match.group(1).strip()
            self.assertTrue(value.startswith(('"', "'")), f"{path}: argument-hint 必须是带引号的字符串")
            self.assertTrue(value.endswith(value[0]), f"{path}: argument-hint 引号不闭合")

    def test_customer_runtime_outputs_are_ignored(self):
        lines = (ROOT / "templates" / "gitignore.template").read_text(encoding="utf-8").splitlines()
        for required in (".auth/", ".auth-xhs/", ".auth-linkedin/", ".cheat-secrets.json", ".cheat-cache/", "deliverables/"):
            self.assertIn(required, lines)


if __name__ == "__main__":
    unittest.main()
