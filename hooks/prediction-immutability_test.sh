#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." &>/dev/null && pwd)"
HOOK="$SCRIPT_DIR/prediction-immutability.sh"
TEST_TMP=$(mktemp -d "${TMPDIR:-/tmp}/cheat-immutability-test.XXXXXX")
trap 'rm -rf "$TEST_TMP"' EXIT

mkdir -p "$TEST_TMP/predictions"
PREDICTION_FILE="$TEST_TMP/predictions/sample.md"
cp "$REPO_DIR/templates/prediction.template.md" "$PREDICTION_FILE"

hook_output=""
hook_exit=0
test_count=0

run_edit() {
  local old_string="$1"
  local new_string="$2"
  local replace_all="${3:-false}"

  set +e
  hook_output=$(
    jq -n \
      --arg file "$PREDICTION_FILE" \
      --arg old "$old_string" \
      --arg new "$new_string" \
      --argjson replace_all "$replace_all" \
      '{
        tool_name: "Edit",
        tool_input: {
          file_path: $file,
          old_string: $old,
          new_string: $new,
          replace_all: $replace_all
        }
      }' |
      "$HOOK" 2>&1
  )
  hook_exit=$?
  set -e
}

assert_allowed() {
  local label="$1"
  shift

  run_edit "$@"
  if [[ "$hook_exit" -ne 0 ]]; then
    printf 'not ok - %s\n%s\n' "$label" "$hook_output"
    exit 1
  fi
  test_count=$((test_count + 1))
  printf 'ok - %s\n' "$label"
}

assert_blocked() {
  local label="$1"
  shift

  run_edit "$@"
  if [[ "$hook_exit" -eq 0 ]]; then
    printf 'not ok - %s\n' "$label"
    exit 1
  fi
  test_count=$((test_count + 1))
  printf 'ok - %s\n' "$label"
}

metadata_old="**Title**: \`<完整标题>\`"
metadata_new="**Title**: \`A calibrated experiment\`"
assert_allowed "allows metadata edits" "$metadata_old" "$metadata_new"

retro_old=$(awk '
  /^## 复盘$/ { capture=1 }
  capture {
    print
    count++
    if (count == 6) exit
  }
' "$PREDICTION_FILE")
retro_placeholder="（待填——T+RETRO_WINDOW_DAYS 天后跑 \`/cheat-retro <对应 video folder>\`）"
retro_result="**Actual plays**: \`1000\`"
retro_new=${retro_old/"$retro_placeholder"/"$retro_result"}
assert_allowed \
  "allows multiline retrospective edits with blank lines" \
  "$retro_old" \
  "$retro_new"

whole_file_old=$(<"$PREDICTION_FILE")
whole_file_metadata_new=${whole_file_old/"$metadata_old"/"$metadata_new"}
assert_allowed \
  "allows broad edits when the prediction stays unchanged" \
  "$whole_file_old" \
  "$whole_file_metadata_new"

prediction_old="**Bucket**: \`<X-Yw>\`  ← e.g. \`30-100w\`"
prediction_new="**Bucket**: \`100w+\`"
assert_blocked \
  "blocks direct prediction edits" \
  "$prediction_old" \
  "$prediction_new"

retro_heading="## 复盘
"
v2_append="## 预测 v2

**Bucket**: \`30-100w\`

## 复盘
"
assert_allowed \
  "allows a new versioned prediction" \
  "$retro_heading" \
  "$v2_append"

whole_file_prediction_new=${whole_file_old/"$prediction_old"/"$prediction_new"}
assert_blocked \
  "blocks broad edits that change the prediction" \
  "$whole_file_old" \
  "$whole_file_prediction_new"

assert_blocked \
  "blocks replace-all edits that change the prediction" \
  "Confidence" \
  "Certainty" \
  true

printf '\n%s prediction immutability tests passed\n' "$test_count"
