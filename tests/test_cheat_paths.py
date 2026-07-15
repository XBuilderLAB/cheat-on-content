from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from cheat_paths import ConfigError, resolve_data_dir, write_pointer


class CheatPathsTest(unittest.TestCase):
    def test_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pointer(root, "pointer-data")
            self.assertEqual(resolve_data_dir(root), (root / "pointer-data").resolve())
            self.assertEqual(resolve_data_dir(root, env={"CHEAT_DATA_DIR": "env-data"}), (root / "env-data").resolve())
            self.assertEqual(resolve_data_dir(root, explicit="explicit-data", env={"CHEAT_DATA_DIR": "env-data"}), (root / "explicit-data").resolve())

    def test_legacy_layout_stays_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cheat-state.json").write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_data_dir(root, env={}), root.resolve())

    def test_invalid_pointer_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cheat-content.json").write_text(json.dumps({"schema_version": 9, "data_dir": "x"}), encoding="utf-8")
            with self.assertRaises(ConfigError):
                resolve_data_dir(root, env={})

    def test_pointer_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_pointer(root, "one")
            with self.assertRaises(ConfigError):
                write_pointer(root, "two")


if __name__ == "__main__":
    unittest.main()
