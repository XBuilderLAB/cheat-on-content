#!/usr/bin/env bash
#
# whisper adapter wrapper
#
# Called by /cheat-learn-from when user provides video file (Way b).
# Transcribes video → transcript.md (paragraph format, no timestamps).
#
# Usage:
#   bash run.sh <video_path> <output_dir> [--lang <code>] [--model <name>]
#
# Defaults:
#   --lang zh
#   --model medium (whisper-cpp) or medium (openai-whisper)
#
# Output: writes transcript.md INTO output_dir.
# Exit codes:
#   0 = success
#   1 = whisper not installed
#   2 = ffmpeg not installed
#   3 = video file not found / unreadable
#   4 = transcription failed

set -uo pipefail

VIDEO="${1:-}"
OUTPUT_DIR="${2:-}"
LANG="zh"
MODEL="medium"

# Parse optional flags
shift 2 2>/dev/null || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang) LANG="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 4 ;;
  esac
done

if [[ -z "$VIDEO" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: bash run.sh <video_path> <output_dir> [--lang zh|en|...] [--model tiny|base|small|medium|large-v3]" >&2
  exit 4
fi

if [[ ! -f "$VIDEO" ]]; then
  echo "❌ Video file not found: $VIDEO" >&2
  exit 3
fi

mkdir -p "$OUTPUT_DIR"

# Detect available whisper engine
ENGINE=""
if command -v whisper-cpp >/dev/null 2>&1; then
  ENGINE="whisper-cpp"
elif command -v whisper >/dev/null 2>&1; then
  ENGINE="openai-whisper"
else
  cat >&2 <<EOF
❌ Neither whisper-cpp nor openai-whisper installed.

Install one:
  Option A (recommended, fast): brew install whisper-cpp
  Option B (Python, slower):    pip install openai-whisper

Then re-run /cheat-learn-from.

See adapters/script-extraction/whisper/README.md for details.
EOF
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "❌ ffmpeg not installed. Run: brew install ffmpeg" >&2
  exit 2
fi

echo "[whisper] engine: $ENGINE | model: $MODEL | lang: $LANG"
echo "[whisper] transcribing: $VIDEO"

TMP_OUT=$(mktemp -d)
trap 'rm -rf "$TMP_OUT"' EXIT

# Transcribe — get raw text output
if [[ "$ENGINE" == "whisper-cpp" ]]; then
  # whisper-cpp needs WAV input, convert via ffmpeg
  AUDIO="$TMP_OUT/audio.wav"
  ffmpeg -y -loglevel error -i "$VIDEO" -ar 16000 -ac 1 -f wav "$AUDIO" 2>&1 || {
    echo "❌ ffmpeg failed to extract audio" >&2; exit 4;
  }
  whisper-cpp -m "$HOME/.whisper-cpp/models/ggml-${MODEL}.bin" -l "$LANG" -otxt -of "$TMP_OUT/out" "$AUDIO" >/dev/null 2>&1 || {
    echo "❌ whisper-cpp failed (model file might be missing — check ~/.whisper-cpp/models/)" >&2; exit 4;
  }
  RAW_TXT="$TMP_OUT/out.txt"
else
  # openai-whisper
  whisper "$VIDEO" --language "$LANG" --model "$MODEL" --output_format txt --output_dir "$TMP_OUT" >/dev/null 2>&1 || {
    echo "❌ openai-whisper failed" >&2; exit 4;
  }
  # openai-whisper names output as <video-basename>.txt
  BASENAME=$(basename "$VIDEO" | sed 's/\.[^.]*$//')
  RAW_TXT="$TMP_OUT/${BASENAME}.txt"
fi

if [[ ! -f "$RAW_TXT" ]]; then
  echo "❌ No transcript produced" >&2
  exit 4
fi

# Get video metadata for header
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO" 2>/dev/null | awk '{printf "%d:%02d", $1/60, $1%60}')
[[ -z "$DURATION" ]] && DURATION="unknown"

# Build output transcript.md
TRANSCRIPT_OUT="$OUTPUT_DIR/transcript.md"
{
  echo "# Transcript: $(basename "$VIDEO")"
  echo ""
  echo "**Source**: $VIDEO"
  echo "**Transcribed at**: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "**Engine**: $ENGINE / $MODEL"
  echo "**Language**: $LANG"
  echo "**Duration**: $DURATION"
  echo ""
  echo "---"
  echo ""
  # Raw text — whisper outputs one sentence per line; merge into paragraphs
  # Heuristic: collapse to single paragraph (Claude can re-paragraph if needed)
  awk 'BEGIN{ORS=""} {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0); if($0!=""){print $0; if(NR%5==0)print "\n\n"; else print " "}} END{print "\n"}' "$RAW_TXT"
} > "$TRANSCRIPT_OUT"

echo "✅ transcript.md written → $TRANSCRIPT_OUT"
exit 0
