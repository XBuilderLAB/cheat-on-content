from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ("xhs-explore", "douyin-session", "bilibili-stat", "linkedin-session")


def load_paths(name: str):
    path = ROOT / "adapters" / "perf-data" / name / "paths.py"
    spec = importlib.util.spec_from_file_location(f"{name}_paths", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class AdapterPathsTest(unittest.TestCase):
    def test_all_adapters_follow_pointer_and_env_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cheat-content.json").write_text(
                json.dumps({"schema_version": 1, "data_dir": "pointer-data"}),
                encoding="utf-8",
            )
            for name in ADAPTERS:
                module = load_paths(name)
                with self.subTest(adapter=name, source="pointer"):
                    actual = module.runtime_project_root(env={"CHEAT_PROJECT_ROOT": str(root)}, cwd=ROOT)
                    self.assertEqual(actual, (root / "pointer-data").resolve())
                with self.subTest(adapter=name, source="env"):
                    actual = module.runtime_project_root(
                        env={"CHEAT_PROJECT_ROOT": str(root), "CHEAT_DATA_DIR": "env-data"},
                        cwd=ROOT,
                    )
                    self.assertEqual(actual, (root / "env-data").resolve())


if __name__ == "__main__":
    unittest.main()
