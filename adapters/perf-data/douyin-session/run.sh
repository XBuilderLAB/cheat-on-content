#!/usr/bin/env bash
#
# douyin-session adapter wrapper
#
# Called by /cheat-retro when state.data_collection=adapter and platform=douyin.
#
# Usage:
#   bash run.sh <aweme_id> <video_folder> [<script_path>]
#
# Example:
#   bash run.sh 7234567890123456789 ~/my-channel/videos/2026-05-04_abc123_停止期待
#
# Output: writes report.md INTO the video_folder.
# Exit codes:
#   0 = success (report.md written)
#   1 = login expired or required
#   2 = adapter dependency missing (playwright not installed)
#   3 = other failure (network, parse error, etc.)

set -uo pipefail

AWEME_ID="${1:-}"
VIDEO_FOLDER="${2:-}"
SCRIPT_PATH="${3:-}"

if [[ -z "$AWEME_ID" || -z "$VIDEO_FOLDER" ]]; then
  echo "Usage: bash run.sh <aweme_id> <video_folder> [<script_path>]" >&2
  exit 3
fi

# Resolve adapter source dir (where this script lives)
ADAPTER_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Find Python — prefer venv in user's project root if exists
PYTHON=""
PROJECT_ROOT="$( dirname "$( dirname "$( realpath "$VIDEO_FOLDER" )" )" )"
if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "❌ python3 not found — install Python 3.10+ first" >&2
  exit 2
fi

# Verify playwright is installed
if ! "$PYTHON" -c "import playwright" 2>/dev/null; then
  cat >&2 <<EOF
❌ playwright not installed.

Install in your project venv:
  cd "$PROJECT_ROOT"
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r "$ADAPTER_DIR/requirements.txt"
  playwright install chromium

Then re-run /cheat-retro.
EOF
  exit 2
fi

# Verify auth/ exists in project root (cookie persistence)
if [[ ! -d "$PROJECT_ROOT/.auth" ]]; then
  cat >&2 <<EOF
❌ Not logged in to 抖音 创作者中心.

First-time login (one-shot):
  cd "$PROJECT_ROOT"
  source .venv/bin/activate
  $PYTHON "$ADAPTER_DIR/crawler.py" login

A Chromium window will pop up — scan QR with your phone to log in.
Cookie will be saved to .auth/ for future runs.
EOF
  exit 1
fi

# Make sure video_folder exists
mkdir -p "$VIDEO_FOLDER"

# Resolve script path (optional — if given, copy to video_folder/script.txt for renderer)
SCRIPT_ARG=""
if [[ -n "$SCRIPT_PATH" && -f "$SCRIPT_PATH" ]]; then
  SCRIPT_ARG="$SCRIPT_PATH"
fi

# Run from PROJECT_ROOT so .auth/ is found and outputs go to expected paths
cd "$PROJECT_ROOT"
export CHEAT_PROJECT_ROOT="$PROJECT_ROOT"

# Override VIDEOS_DIR via env var so review.py writes to user's videos/ not its own
# (review.py uses ROOT/videos by default; we override to use user's project)
export CHEAT_VIDEOS_DIR="$( dirname "$VIDEO_FOLDER" )"  # = user's videos/

echo "[douyin-session] fetching aweme_id=$AWEME_ID into $VIDEO_FOLDER"
if [[ -n "$SCRIPT_ARG" ]]; then
  "$PYTHON" "$ADAPTER_DIR/review.py" video "$AWEME_ID" "$SCRIPT_ARG"
else
  "$PYTHON" "$ADAPTER_DIR/review.py" video "$AWEME_ID"
fi

# review.py writes to ROOT/videos/<auto-named-folder>/report.md.
# We need to find the just-written report.md and move it to our video_folder if names differ.
# (review.py uses video.title for folder name; ours uses <date>_<id>_<short>.)
LATEST_REPORT=$(find "$( dirname "$VIDEO_FOLDER" )" -name "report.md" -newer "$VIDEO_FOLDER" -type f 2>/dev/null | head -1)
if [[ -n "$LATEST_REPORT" && "$( dirname "$LATEST_REPORT" )" != "$VIDEO_FOLDER" ]]; then
  # Move the autonamed folder's report into our canonical folder
  cp "$LATEST_REPORT" "$VIDEO_FOLDER/report.md"
  # Optionally also copy script.txt if review.py wrote it
  AUTO_DIR=$( dirname "$LATEST_REPORT" )
  if [[ -f "$AUTO_DIR/script.txt" ]]; then
    cp "$AUTO_DIR/script.txt" "$VIDEO_FOLDER/script.txt"
  fi
  echo "[douyin-session] moved auto-named output to $VIDEO_FOLDER/"
fi

if [[ ! -f "$VIDEO_FOLDER/report.md" ]]; then
  echo "❌ report.md not produced — see review.py output above for details" >&2
  exit 3
fi

echo "✅ report.md written to $VIDEO_FOLDER/report.md"
exit 0
