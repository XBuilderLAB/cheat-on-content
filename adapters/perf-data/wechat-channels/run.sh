#!/usr/bin/env bash
set -euo pipefail

POST_ID="${1:-}"
VIDEO_FOLDER="${2:-}"
SCRIPT_PATH="${3:-}"

if [[ -z "$POST_ID" || -z "$VIDEO_FOLDER" ]]; then
  echo "Usage: bash run.sh <post_id> <video_folder> [script_path]" >&2
  exit 3
fi

ADAPTER_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
mkdir -p "$VIDEO_FOLDER"
VIDEO_FOLDER_REAL="$( cd "$VIDEO_FOLDER" && pwd )"

find_project_root() {
  local dir
  dir="$( dirname "$VIDEO_FOLDER_REAL" )"
  while [[ "$dir" != "/" && -n "$dir" ]]; do
    if [[ -f "$dir/.cheat-state.json" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
    dir="$( dirname "$dir" )"
  done
  return 1
}

if ! PROJECT_ROOT="$(find_project_root)"; then
  echo "Could not find .cheat-state.json above $VIDEO_FOLDER" >&2
  exit 3
fi

REPORT_PATH="$VIDEO_FOLDER_REAL/report.md"
rm -f "$REPORT_PATH"
cleanup_report_on_failure() {
  local status=$?
  if [[ "$status" -ne 0 ]]; then
    rm -f "$REPORT_PATH"
  fi
}
trap cleanup_report_on_failure EXIT

if [[ -n "${CHEAT_PYTHON:-}" ]]; then
  PYTHON="$CHEAT_PYTHON"
elif [[ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/Scripts/python.exe"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "python not found" >&2
  exit 2
fi

if ! "$PYTHON" -c "import playwright" 2>/dev/null; then
  echo "playwright not installed in project venv" >&2
  exit 2
fi
if [[ ! -d "$PROJECT_ROOT/.auth-wechat-channels" ]]; then
  echo "视频号助手未登录，请先运行: $PYTHON \"$ADAPTER_DIR/review.py\" login" >&2
  exit 1
fi

cd "$PROJECT_ROOT"
export CHEAT_PROJECT_ROOT="$PROJECT_ROOT"
export CHEAT_VIDEOS_DIR="$( dirname "$VIDEO_FOLDER_REAL" )"
export CHEAT_OUTPUT_DIR="$VIDEO_FOLDER_REAL"
export PYTHONUTF8=1

if [[ -n "$SCRIPT_PATH" && -f "$SCRIPT_PATH" ]]; then
  "$PYTHON" "$ADAPTER_DIR/review.py" post "$POST_ID" "$SCRIPT_PATH"
else
  "$PYTHON" "$ADAPTER_DIR/review.py" post "$POST_ID"
fi

[[ -f "$REPORT_PATH" ]] || exit 3
echo "report.md written to $REPORT_PATH"
