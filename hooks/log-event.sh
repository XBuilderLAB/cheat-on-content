#!/usr/bin/env bash
#
# cheat-on-content / meta-logging hook
#
# Passive event recorder. Writes one JSON line per event to
# .cheat-cache/usage.jsonl in the project root. Never blocks (async fire-and-forget).
#
# Used by /cheat-status to compute:
#   - "distance since last bump" (count of cheat-predict invocations after last_bump_at)
#   - skill invocation frequency
#   - tool failure patterns
#
# Usage: log-event.sh <event_type>
#   <event_type> ∈ {tool_use, user_prompt, session_start, session_end}
#
# Reads from stdin: Claude Code's hook payload JSON
# Output: appends one line to .cheat-cache/usage.jsonl

set -uo pipefail

event_type="${1:-unknown}"
cache_dir="${CLAUDE_PROJECT_DIR:-.}/.cheat-cache"
log_file="${cache_dir}/usage.jsonl"

mkdir -p "$cache_dir" 2>/dev/null || exit 0  # never block on permission errors

# Read hook payload
input=$(cat 2>/dev/null || echo "{}")

# Build a compact event record. Best-effort jq parse — if it fails we still log a minimal record.
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if command -v jq >/dev/null 2>&1; then
  # Extract a few standard fields if present
  event_json=$(printf '%s' "$input" | jq -c --arg ts "$ts" --arg type "$event_type" '
    {
      ts: $ts,
      event: $type,
      tool: (.tool_name // null),
      file: (.tool_input.file_path // null),
      success: (.tool_response.success // null),
      prompt_present: ((.user_prompt // null) != null),
      prompt_chars: ((.user_prompt // "" | tostring) | length)
    }
  ' 2>/dev/null || echo "")
  if [[ -z "$event_json" ]]; then
    event_json=$(printf '{"ts":"%s","event":"%s"}' "$ts" "$event_type")
  fi
else
  # No jq — minimal record
  event_json=$(printf '{"ts":"%s","event":"%s"}' "$ts" "$event_type")
fi

# Append (locking is platform-specific; for typical single-user setups append is atomic enough on macOS)
printf '%s\n' "$event_json" >> "$log_file" 2>/dev/null || true

exit 0
