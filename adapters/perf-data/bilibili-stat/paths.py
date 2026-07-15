from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Mapping


def runtime_project_root(
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    active_env = env if env is not None else os.environ
    base = Path(active_env.get("CHEAT_PROJECT_ROOT") or (cwd if cwd is not None else Path.cwd())).expanduser().resolve()
    if active_env.get("CHEAT_DATA_DIR"):
        candidate = Path(active_env["CHEAT_DATA_DIR"]).expanduser()
        return (candidate if candidate.is_absolute() else base / candidate).resolve()
    pointer = base / ".cheat-content.json"
    if pointer.exists():
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        candidate = Path(payload["data_dir"]).expanduser()
        return (candidate if candidate.is_absolute() else base / candidate).resolve()
    return base


def debug_dir(
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    return runtime_project_root(env=env, cwd=cwd) / ".cheat-cache" / "bilibili-stat-debug"


def videos_dir(
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    active_env = env if env is not None else os.environ
    if active_env.get("CHEAT_VIDEOS_DIR"):
        return Path(active_env["CHEAT_VIDEOS_DIR"]).expanduser().resolve()
    return runtime_project_root(env=env, cwd=cwd) / "videos"
