#!/usr/bin/env bash
#
# xhs-explore adapter wrapper（小红书）
#
# Called by /cheat-retro when state.data_collection=adapter and platform=xhs.
#
# Usage:
#   bash run.sh <note_id> <video_folder> [<script_path>]
#
# Example:
#   bash run.sh 66f1a2b3c4d5e6f700112233 ~/my-channel/videos/2026-05-04_abc123_标题
#
# Output: writes report.md INTO the video_folder.
# Exit codes:
#   0 = success (report.md written)
#   1 = login expired or required
#   2 = adapter dependency missing (playwright not installed)
#   3 = other failure (network, parse error, etc.)

set -uo pipefail

NOTE_ID="${1:-}"
VIDEO_FOLDER="${2:-}"
SCRIPT_PATH="${3:-}"

if [[ -z "$NOTE_ID" || -z "$VIDEO_FOLDER" ]]; then
  echo "Usage: bash run.sh <note_id> <video_folder> [<script_path>]" >&2
  exit 3
fi

ADAPTER_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Find Python — prefer venv in user's project root if exists
PYTHON=""
PROJECT_ROOT="$( dirname "$( dirname "$( realpath "$VIDEO_FOLDER" )" )" )"
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif [[ -x "$PROJECT_ROOT/.venv/Scripts/python.exe" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/Scripts/python.exe"   # Windows venv layout
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "❌ python not found — install Python 3.10+ first" >&2
  exit 2
fi

# Verify playwright is installed
if ! "$PYTHON" -c "import playwright" 2>/dev/null; then
  cat >&2 <<EOF
❌ playwright not installed.

Install in your project venv:
  cd "$PROJECT_ROOT"
  python3 -m venv .venv
  source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
  pip install -r "$ADAPTER_DIR/requirements.txt"
  playwright install chromium

Then re-run /cheat-retro.
EOF
  exit 2
fi

# Verify auth dir exists in project root (cookie persistence)
if [[ ! -d "$PROJECT_ROOT/.auth-xhs" ]]; then
  cat >&2 <<EOF
❌ Not logged in to 小红书 创作者中心.

First-time login (one-shot):
  cd "$PROJECT_ROOT"
  source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
  $PYTHON "$ADAPTER_DIR/crawler.py" login

A Chromium window will pop up — scan QR with your phone to log in.
Cookie will be saved to .auth-xhs/ for future runs.
EOF
  exit 1
fi

mkdir -p "$VIDEO_FOLDER"

SCRIPT_ARG=""
if [[ -n "$SCRIPT_PATH" && -f "$SCRIPT_PATH" ]]; then
  SCRIPT_ARG="$SCRIPT_PATH"
fi

# Run from PROJECT_ROOT so .auth-xhs/ is found and outputs go to expected paths
cd "$PROJECT_ROOT"
export CHEAT_PROJECT_ROOT="$PROJECT_ROOT"
export CHEAT_VIDEOS_DIR="$( dirname "$VIDEO_FOLDER" )"

echo "[xhs-explore] fetching note_id=$NOTE_ID into $VIDEO_FOLDER"
if [[ -n "$SCRIPT_ARG" ]]; then
  "$PYTHON" "$ADAPTER_DIR/review.py" note "$NOTE_ID" "$SCRIPT_ARG"
else
  "$PYTHON" "$ADAPTER_DIR/review.py" note "$NOTE_ID"
fi

# review.py writes to CHEAT_VIDEOS_DIR/<auto-named-folder>/report.md.
# Move the just-written report into our canonical video_folder if names differ.
LATEST_REPORT=$(find "$( dirname "$VIDEO_FOLDER" )" -name "report.md" -newer "$VIDEO_FOLDER" -type f 2>/dev/null | head -1)
if [[ -n "$LATEST_REPORT" && "$( dirname "$LATEST_REPORT" )" != "$VIDEO_FOLDER" ]]; then
  cp "$LATEST_REPORT" "$VIDEO_FOLDER/report.md"
  AUTO_DIR=$( dirname "$LATEST_REPORT" )
  if [[ -f "$AUTO_DIR/script.txt" ]]; then
    cp "$AUTO_DIR/script.txt" "$VIDEO_FOLDER/script.txt"
  fi
  echo "[xhs-explore] moved auto-named output to $VIDEO_FOLDER/"
fi

if [[ ! -f "$VIDEO_FOLDER/report.md" ]]; then
  echo "❌ report.md not produced — see review.py output above for details" >&2
  exit 3
fi

echo "✅ report.md written to $VIDEO_FOLDER/report.md"
exit 0
