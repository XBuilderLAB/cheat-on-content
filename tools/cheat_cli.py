"""Cross-platform maintenance CLI for cheat-on-content (stdlib only)."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from cheat_audit import build_audit, write_audit
from cheat_paths import ConfigError, resolve_data_dir, state_path, write_pointer


ROOT = Path(__file__).resolve().parents[1]
LATEST_SCHEMA = "1.5"
SKILL_VERSION = "0.2.0"


def _copy_if_missing(source: Path, destination: Path) -> None:
    if not destination.exists() and source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _merge_gitignore(destination: Path) -> None:
    required = (ROOT / "templates" / "gitignore.template").read_text(encoding="utf-8").splitlines()
    existing = destination.read_text(encoding="utf-8").splitlines() if destination.exists() else []
    missing = [line for line in required if line and line not in existing]
    if not destination.exists():
        destination.write_text("\n".join(required) + "\n", encoding="utf-8")
    elif missing:
        with destination.open("a", encoding="utf-8") as handle:
            handle.write("\n# cheat-on-content credentials and runtime cache\n")
            handle.write("\n".join(missing) + "\n")


def _default_state(agent: str) -> dict:
    # The CLI can copy scaffolding but cannot prove that an agent harness executes hooks.
    # Only cheat-init's live Phase 4 interception test may flip hooks_enforced to true.
    enforced = False
    return {
        "schema_version": LATEST_SCHEMA,
        "skill_version": SKILL_VERSION,
        "rubric_version": "v0",
        "content_form": "opinion-video",
        "typical_duration_seconds": 240,
        "target_publish_cadence_days": 2,
        "rubric_form_mismatch": False,
        "benchmark_status": "none",
        "benchmark_name": None,
        "benchmark_sample_count": 0,
        "baseline_plays": None,
        "calibration_samples": 0,
        "calibration_samples_at_last_bump": 0,
        "data_collection": "manual",
        "pool_status": "none",
        "data_layer": "markdown",
        "guard_scripts_installed": False,
        "hooks_backend": "none",
        "hooks_enforced": enforced,
        "enabled_trend_sources": ["manual-paste"],
        "enabled_perf_adapters": [],
        "last_bump_at": None,
        "last_bump_self_audited": False,
        "last_published_at": None,
        "last_published_file": None,
        "last_retro_at": None,
        "last_trends_run_at": None,
        "last_trends_added_count": 0,
        "last_prediction_self_scored": False,
        "last_self_scored_at": None,
        "consecutive_directional_errors": [],
        "pending_retros": [],
        "shoots": [],
        "in_progress_session": None,
        "initialized_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def cmd_init(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    data_dir = resolve_data_dir(project, explicit=args.dir)
    project.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    if data_dir != project:
        write_pointer(project, data_dir)
    _merge_gitignore(project / ".gitignore")
    for name in ("scripts", "predictions", "videos", "samples", "deliverables"):
        folder = data_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / ".gitkeep").touch(exist_ok=True)
    copies = {
        ROOT / "starter-rubrics" / "opinion-video-zero.md": data_dir / "rubric_notes.md",
        ROOT / "templates" / "rubric-memo.template.md": data_dir / "rubric-memo.md",
        ROOT / "templates" / "script_patterns.template.md": data_dir / "script_patterns.md",
        ROOT / "templates" / "audience.template.md": data_dir / "audience.md",
        ROOT / "templates" / "workflow.template.md": data_dir / "WORKFLOW.md",
        ROOT / "templates" / "status.template.md": data_dir / "STATUS.md",
    }
    for source, destination in copies.items():
        _copy_if_missing(source, destination)
    state = state_path(data_dir)
    if state.exists() and not args.force:
        raise ConfigError(f"{state} 已存在；拒绝覆盖。需要重建时显式传 --force")
    state.write_text(json.dumps(_default_state(args.agent), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"initialized: {data_dir}")
    print(f"guard: {args.agent} CLI 未执行 harness 拦截测试；hooks_enforced=false（君子协定）")
    return 0


def _load_state(data_dir: Path) -> dict:
    path = state_path(data_dir)
    if not path.exists():
        raise ConfigError(f"找不到 {path}；先运行 init")
    return json.loads(path.read_text(encoding="utf-8"))


def cmd_status(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args.project, explicit=args.dir)
    state = _load_state(data_dir)
    print(f"data_dir: {data_dir}")
    print(f"schema: {state.get('schema_version', 'unknown')}")
    print(f"calibration_samples: {state.get('calibration_samples', 0)}")
    print(f"pending_retros: {len(state.get('pending_retros', []))}")
    print(f"shoot_buffer: {len(state.get('shoots', []))}")
    if state.get("hooks_enforced"):
        print(f"prediction_guard: enforced ({state.get('hooks_backend')})")
    else:
        print("prediction_guard: honor-system (未由 harness 强制)")
    return 0


def migrate_state(payload: dict, agent: str) -> dict:
    version = str(payload.get("schema_version", ""))
    if version == LATEST_SCHEMA:
        return payload.copy()
    if version != "1.4":
        raise ConfigError(f"本 CLI 只执行 1.4 → 1.5；当前是 {version or 'unknown'}，请先按迁移链升级到 1.4")
    migrated = payload.copy()
    legacy = bool(migrated.pop("hooks_installed", False))
    migrated.update({
        "schema_version": LATEST_SCHEMA,
        "skill_version": SKILL_VERSION,
        "guard_scripts_installed": legacy,
        "hooks_backend": "none",
        "hooks_enforced": False,
    })
    return migrated


def cmd_migrate(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args.project, explicit=args.dir)
    path = state_path(data_dir)
    before = _load_state(data_dir)
    after = migrate_state(before, args.agent)
    if args.dry_run:
        print(json.dumps(after, ensure_ascii=False, indent=2))
        return 0
    if before == after:
        print(f"already current: {LATEST_SCHEMA}")
        return 0
    backup = path.with_name(f"{path.name}.{before.get('schema_version', 'unknown')}.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"migrated: {before.get('schema_version')} -> {LATEST_SCHEMA}")
    print(f"backup: {backup}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    data_dir = resolve_data_dir(args.project, explicit=args.dir)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    audit = build_audit(payload, account_name=args.account_name, platform=args.platform, generated_at=args.as_of)
    output = args.output_dir or (data_dir / "deliverables" / "account-audit")
    paths = write_audit(audit, output)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cheat", description="cheat-on-content cross-platform CLI")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--dir", help="数据目录；优先级高于 CHEAT_DATA_DIR 与指针文件")
    parser.add_argument("--version", action="version", version=SKILL_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--agent", choices=("codex", "claude-code", "other"), default="other")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status")
    status.set_defaults(func=cmd_status)

    migrate = sub.add_parser("migrate")
    migrate.add_argument("--agent", choices=("codex", "claude-code", "other"), default="other")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.set_defaults(func=cmd_migrate)

    audit = sub.add_parser("audit")
    audit.add_argument("--input", required=True, type=Path)
    audit.add_argument("--output-dir", type=Path)
    audit.add_argument("--account-name", default="未命名账号")
    audit.add_argument("--platform", default="xiaohongshu")
    audit.add_argument("--as-of")
    audit.set_defaults(func=cmd_audit)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.project = args.project.expanduser().resolve()
    try:
        return args.func(args)
    except (ConfigError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
