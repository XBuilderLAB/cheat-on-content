from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from cheat_cli import main, migrate_state


class CheatCliTest(unittest.TestCase):
    def test_windows_friendly_init_status_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "client"
            self.assertEqual(main(["--project", str(project), "--dir", "cheat-content", "init", "--agent", "codex"]), 0)
            pointer = json.loads((project / ".cheat-content.json").read_text(encoding="utf-8"))
            self.assertEqual(pointer["data_dir"], "cheat-content")
            state = json.loads((project / "cheat-content" / ".cheat-state.json").read_text(encoding="utf-8"))
            self.assertFalse(state["hooks_enforced"])
            self.assertEqual(state["hooks_backend"], "none")
            self.assertEqual(main(["--project", str(project), "status"]), 0)
            fixture = ROOT / "tests" / "fixtures" / "account_notes.json"
            self.assertEqual(main(["--project", str(project), "audit", "--input", str(fixture), "--as-of", "2026-07-15T00:00:00+00:00"]), 0)
            self.assertTrue((project / "cheat-content" / "deliverables" / "account-audit" / "account-audit.md").exists())

    def test_migration_does_not_claim_codex_hooks(self):
        legacy = {"schema_version": "1.4", "skill_version": "1.0.0", "hooks_installed": True}
        migrated = migrate_state(legacy, "codex")
        self.assertEqual(migrated["schema_version"], "1.5")
        self.assertTrue(migrated["guard_scripts_installed"])
        self.assertFalse(migrated["hooks_enforced"])
        self.assertEqual(migrated["hooks_backend"], "none")
        self.assertNotIn("hooks_installed", migrated)


if __name__ == "__main__":
    unittest.main()
