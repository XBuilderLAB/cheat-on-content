from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from cheat_audit import build_audit, normalize_notes, render_markdown, write_audit


class CheatAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads((ROOT / "tests" / "fixtures" / "account_notes.json").read_text(encoding="utf-8"))

    def test_normalizes_deduplicates_and_chinese_numbers(self):
        notes, _ = normalize_notes(self.payload)
        self.assertEqual(len(notes), 8)
        by_id = {n["note_id"]: n for n in notes}
        self.assertEqual(by_id["n07"]["views"], 15000)
        self.assertEqual(by_id["n08"]["title"], "重复项以后者为准")

    def test_audit_never_claims_blind_calibration(self):
        audit = build_audit(self.payload, account_name="测试", generated_at="2026-07-15T00:00:00+00:00")
        self.assertEqual(audit["source_classification"], "reconstructed")
        self.assertEqual(audit["calibration_samples_increment"], 0)
        self.assertEqual(len(audit["hypotheses"]), 3)
        self.assertEqual({x["label"] for x in audit["engagement_drivers"]}, {"收藏", "评论"})
        self.assertTrue(audit["structure_patterns"])
        self.assertEqual(audit["data_quality"]["partial_fetch_failures"], 1)
        self.assertFalse(
            {x["note_id"] for x in audit["top_content"]}
            & {x["note_id"] for x in audit["bottom_content"]}
        )
        for hypothesis in audit["hypotheses"]:
            if hypothesis["confidence"] != "low":
                self.assertGreaterEqual(len(hypothesis["evidence"]), 2)
        self.assertIn("样本少于 20", " ".join(audit["data_quality"]["limitations"]))

    def test_report_is_traceable_and_repeatable(self):
        kwargs = {"account_name": "测试", "generated_at": "2026-07-15T00:00:00+00:00"}
        first = build_audit(self.payload, **kwargs)
        second = build_audit(self.payload, **kwargs)
        self.assertEqual(first, second)
        markdown = render_markdown(first)
        self.assertIn("`n07`", markdown)
        self.assertIn("这是决策校准，不是爆款保证", markdown)
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_audit(first, tmp)
            self.assertEqual(set(paths), {"json", "markdown", "experiments"})
            self.assertTrue(all(path.exists() for path in paths.values()))


if __name__ == "__main__":
    unittest.main()
