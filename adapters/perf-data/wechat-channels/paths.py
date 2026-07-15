from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


def runtime_project_root(
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> Path:
    active_env = env if env is not None else os.environ
    if active_env.get("CHEAT_PROJECT_ROOT"):
        return Path(active_env["CHEAT_PROJECT_ROOT"]).expanduser().resolve()
    return (cwd or Path.cwd()).expanduser().resolve()


def auth_dir() -> Path:
    return runtime_project_root() / ".auth-wechat-channels"


def videos_dir() -> Path:
    override = os.environ.get("CHEAT_VIDEOS_DIR")
    return Path(override).expanduser().resolve() if override else runtime_project_root() / "videos"
