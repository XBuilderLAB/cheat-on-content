"""Resolve cheat-on-content's data directory consistently across runtimes."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping


POINTER_FILE = ".cheat-content.json"
POINTER_SCHEMA = 1


class ConfigError(ValueError):
    """Raised when the workspace pointer file is invalid."""


def _resolve(base: Path, value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve()


def resolve_data_dir(
    project_root: Path | str | None = None,
    explicit: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    """Resolve data root using the documented precedence.

    Precedence: explicit --dir > CHEAT_DATA_DIR > pointer file > legacy cwd.
    A workspace without a pointer remains a legacy-layout workspace.
    """

    root = Path(project_root or Path.cwd()).expanduser().resolve()
    active_env = env if env is not None else os.environ

    if explicit is not None and str(explicit).strip():
        return _resolve(root, explicit)

    env_dir = active_env.get("CHEAT_DATA_DIR", "").strip()
    if env_dir:
        return _resolve(root, env_dir)

    pointer = root / POINTER_FILE
    if pointer.exists():
        try:
            payload = json.loads(pointer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"无法读取 {pointer}: {exc}") from exc
        if payload.get("schema_version") != POINTER_SCHEMA:
            raise ConfigError(
                f"{pointer} schema_version 必须是 {POINTER_SCHEMA}"
            )
        data_dir = payload.get("data_dir")
        if not isinstance(data_dir, str) or not data_dir.strip():
            raise ConfigError(f"{pointer} 缺少非空 data_dir")
        return _resolve(root, data_dir)

    return root


def write_pointer(project_root: Path | str, data_dir: Path | str) -> Path:
    """Write a minimal workspace pointer without overwriting an existing file."""

    root = Path(project_root).expanduser().resolve()
    resolved = _resolve(root, data_dir)
    pointer = root / POINTER_FILE
    if pointer.exists():
        existing = resolve_data_dir(root)
        if existing != resolved:
            raise ConfigError(f"{pointer} 已指向 {existing}，拒绝覆盖")
        return pointer

    try:
        display = str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        display = str(resolved)
    payload = {"schema_version": POINTER_SCHEMA, "data_dir": display or "."}
    pointer.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return pointer


def state_path(data_dir: Path | str) -> Path:
    return Path(data_dir).expanduser().resolve() / ".cheat-state.json"
