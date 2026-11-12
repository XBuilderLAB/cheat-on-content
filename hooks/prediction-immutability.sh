#!/usr/bin/env bash
#
# cheat-on-content / prediction-immutability hook
# PreToolUse(Edit|Write|MultiEdit)
#
# Locks the body of every predictions/*.md that has a '## 预测' / '## Prediction'
# section: everything from the first '## ' heading (输入快照, 预测 v1/v2, 推理因素,
# 锚点对比, 反事实场景, 关键校准假设) up to, but not including, '## 复盘' /
# '## Retrospective'.
#
# Previously this script only locked the '## 预测' heading's own section, and it
# exited 1. Claude Code treats any PreToolUse exit other than 2 as a non-blocking
# error and runs the edit anyway (https://code.claude.com/docs/en/hooks).
#
# Allows:
#   - creating a brand-new prediction file (Write to a path that does not exist yet)
#   - editing the metadata header (above the first '## ') — cheat-publish writes there
#   - inserting '## 预测 v2' by an Edit whose old_string starts at '## 复盘'
#   - appending inside / after '## 复盘' / '## Retrospective'
#   - files outside predictions/
# Blocks:
#   - any Edit / MultiEdit whose old_string overlaps the locked body
#   - Write that would overwrite an existing prediction file
#
# Exit codes (Claude Code PreToolUse):
#   0 = allow
#   2 = BLOCK — stderr is fed back to the model
#   1 = checker unavailable (no python and no jq). Non-blocking; the edit proceeds.
#
# Bypass (pure markdown-formatting fixes only, visible in git history):
#   CHEAT_BYPASS_IMMUTABILITY=1
#
# Needs python3/python (preferred, exact overlap) or jq + awk + grep (conservative fallback).

set -uo pipefail

if [[ "${CHEAT_BYPASS_IMMUTABILITY:-0}" == "1" ]]; then
  echo "[cheat-on-content] ⚠️  IMMUTABILITY BYPASS active (CHEAT_BYPASS_IMMUTABILITY=1) — formatting fixes only." >&2
  echo "[cheat-on-content] ⚠️  This should only be used for pure markdown-formatting fixes." >&2
  echo "[cheat-on-content] ⚠️  Bypass will be visible in git history." >&2
  exit 0
fi

input=$(cat)
[[ -z "$input" ]] && exit 0

block_msg() {
  cat >&2 <<EOF

[cheat-on-content] 🚫 BLOCKED: $1
  $2

This violates principle #1 of cheat-on-content: the prediction body is immutable.
Once written, nothing from the first '##' heading up to '## 复盘' can be modified —
including the input snapshot (the scores), the prediction, the reasoning, the
anchors, the counterfactuals, and the calibration hypothesis. Only '## 复盘' /
'## Retrospective' may be appended to.

What to do instead:
  • To redo the prediction with new info, create a NEW file:
      ${2%.md}_redo.md
    The original must be preserved.
  • If you noticed a factual mistake AFTER seeing data, document it in the
    '## 复盘' section: "Correction: original probability X% should have been Y%".
  • To insert '## 预测 v2', Edit with old_string starting at the '## 复盘' line.
  • For a pure markdown-formatting fix (no semantic change), bypass once with:
      CHEAT_BYPASS_IMMUTABILITY=1
    (logs to stderr, visible in git).

See: shared-references/blind-prediction-protocol.md
EOF
}

# ---------------------------------------------------------------- preferred path: Python
PY=""
for cand in python3 python; do
  # skip the Windows Store "python" stub (it can hang or open the Store)
  [[ "$(command -v "$cand" 2>/dev/null)" == *WindowsApps* ]] && continue
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done

payload=$(mktemp)
trap 'rm -f "$payload"' EXIT
printf '%s' "$input" > "$payload"

if [[ -n "$PY" ]]; then
  if ! verdict=$(CHEAT_HOOK_PAYLOAD="$payload" "$PY" - <<'PY'
import json, os, re, sys

payload = os.environ.get("CHEAT_HOOK_PAYLOAD") or ""
try:
    raw = open(payload, encoding="utf-8").read() if payload else ""
    data = json.loads(raw or "{}")
except (OSError, ValueError):
    print("allow"); sys.exit(0)
tool = data.get("tool_name") or ""
ti = data.get("tool_input") or {}
fp = (ti.get("file_path") or "").replace("\\", "/")
if tool not in ("Edit", "Write", "MultiEdit") or not re.search(r"(^|/)predictions/[^/]+\.md$", fp):
    print("allow"); sys.exit(0)
path = fp
if not os.path.isabs(path) and not re.match(r"^[A-Za-z]:/", path):
    path = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(), path)
if not os.path.isfile(path):
    print("allow"); sys.exit(0)          # creating a new prediction file
with open(path, encoding="utf-8", errors="replace") as f:
    text = f.read().replace("\r\n", "\n")

# Locked region = from the first '## ' heading up to '## 复盘' / '## Retrospective'
# (exclusive). The header above the first '## ' stays editable, and so does
# everything from '## 复盘' on.
retro_head = re.compile(r"^## (复盘|Retrospective)(?![A-Za-z])")
pred_head = re.compile(r"^## (预测|Prediction)(?![A-Za-z])")
first, retro, offset, has_pred = None, None, 0, False
for line in text.splitlines(keepends=True):
    if line.startswith("## "):
        if retro_head.match(line):
            retro = offset
            break
        if first is None:
            first = offset
        if pred_head.match(line):
            has_pred = True
    offset += len(line)
if first is None or not has_pred:
    print("allow"); sys.exit(0)          # not a prediction file
end = retro if retro is not None else len(text)
if tool == "Write":
    print("block-write"); print(fp); sys.exit(0)
olds = [ti.get("old_string")] if tool == "Edit" else [e.get("old_string") for e in (ti.get("edits") or [])]
for old in olds:
    if not old:
        continue
    old = old.replace("\r\n", "\n")
    i = text.find(old)
    while i >= 0:
        j = i + len(old)
        if i < end and j > first:
            print("block-edit"); print(fp); sys.exit(0)
        i = text.find(old, i + 1)
print("allow")
PY
  ); then
    echo "[cheat-on-content] prediction-immutability checker failed; blocking this edit." >&2
    exit 2
  fi
  verdict=${verdict//$'\r'/}
  kind=${verdict%%$'\n'*}
  file_path=${verdict#*$'\n'}
  case "$kind" in
    block-edit)
      block_msg "edit touches the locked prediction body of" "$file_path"
      exit 2 ;;
    block-write)
      block_msg "Write would overwrite an existing prediction file (use Edit to append to '## 复盘')" "$file_path"
      exit 2 ;;
    *) exit 0 ;;
  esac
fi

# ---------------------------------------------------------------- fallback: jq + awk + grep
if ! command -v jq >/dev/null 2>&1; then
  echo "[cheat-on-content] ⚠️  prediction-immutability hook cannot check this edit: no python3/python and no jq. The lock is NOT in effect." >&2
  exit 1   # non-blocking: surfaces the warning, Claude Code still runs the tool
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' | tr '\\' '/')
case "$tool_name" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac
case "$file_path" in */predictions/*.md|predictions/*.md) ;; *) exit 0 ;; esac
[[ -f "$file_path" ]] || exit 0

grep -qE '^## (预测|Prediction)' "$file_path" 2>/dev/null || exit 0
# locked region: first '## ' heading up to (not including) '## 复盘' / '## Retrospective'
section=$(awk '
  /^## (复盘|Retrospective)/ { exit }
  /^## / { inp=1 }
  inp { print }
' "$file_path" 2>/dev/null)
[[ -z "$section" ]] && exit 0

if [[ "$tool_name" == "Write" ]]; then
  block_msg "Write would overwrite an existing prediction file (use Edit to append to '## 复盘')" "$file_path"
  exit 2
fi

tmp_sec=$(mktemp); tmp_pat=$(mktemp)
trap 'rm -f "$payload" "$tmp_sec" "$tmp_pat"' EXIT
printf '%s\n' "$section" > "$tmp_sec"
# Conservative: block if any non-blank, non-heading line of any old_string
# appears inside the locked body. (An empty pattern would match every line.)
printf '%s' "$input" | jq -r '(.tool_input.old_string // empty), (.tool_input.edits // [] | .[].old_string)' \
  | grep -v '^[[:space:]]*$' | grep -v '^## ' > "$tmp_pat" || true
if [[ -s "$tmp_pat" ]] && grep -qF -f "$tmp_pat" "$tmp_sec"; then
  block_msg "edit touches the locked prediction body of (fallback check — install python for an exact check)" "$file_path"
  exit 2
fi
exit 0
