#!/usr/bin/env bash
#
# cheat-on-content SessionStart hook
#
# Renders a 4-6 line status report at the start of every Claude Code session.
# Output is added to Claude's system context — Claude sees it before first reply.
#
# Silently exits if:
#   - Not in a cheat-on-content project (no .cheat-state.json)
#   - jq not available (status is markdown-readable; Claude can read state.json directly)
#
# Format:
#   📦 Buffer: N (color)
#   ⏰ 待复盘: N
#   🎯 候选 top 3: ...
#   📅 上次抓热点: N 天前
#   ⚠️ 待办: ...

set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
STATE_FILE="$PROJECT_DIR/.cheat-state.json"

# Silently skip if not a cheat-on-content project
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Skip if jq missing (Claude can still read state.json himself in conversation)
if ! command -v jq >/dev/null 2>&1; then
  cat <<'EOF'
[cheat-on-content] SessionStart: jq not installed — skipping auto status report.
Claude can still read .cheat-state.json directly. Say "状态" for full status.
EOF
  exit 0
fi

now_epoch=$(date +%s)
today_iso=$(date +%Y-%m-%d)

# --- Read state ---
state=$(cat "$STATE_FILE")
schema_version=$(echo "$state" | jq -r '.schema_version // "unknown"')
rubric_version=$(echo "$state" | jq -r '.rubric_version // "v0"')
calibration_samples=$(echo "$state" | jq -r '.calibration_samples // 0')
target_cadence=$(echo "$state" | jq -r '.target_publish_cadence_days // null')
buffer_count=$(echo "$state" | jq -r '.shoots // [] | length')
pending_retros_count=$(echo "$state" | jq -r '.pending_retros // [] | length')
last_trends_at=$(echo "$state" | jq -r '.last_trends_run_at // ""')
last_published_at=$(echo "$state" | jq -r '.last_published_at // ""')
hooks_installed=$(echo "$state" | jq -r '.hooks_installed // false')
form_severe_mismatch=$(echo "$state" | jq -r '.rubric_form_severe_mismatch // false')
last_prediction_self_scored=$(echo "$state" | jq -r '.last_prediction_self_scored // false')
last_self_scored_at=$(echo "$state" | jq -r '.last_self_scored_at // ""')

# --- Detect schema mismatch (read LATEST_SCHEMA from migrations/registry.md if reachable) ---
# Strategy: hardcode current LATEST_SCHEMA here (bumped by maintainer alongside cheat-init).
# If state.schema_version != LATEST_SCHEMA → suggest migrate (non-blocking).
LATEST_SCHEMA="1.4"
schema_mismatch=""
if [[ "$schema_version" != "$LATEST_SCHEMA" && "$schema_version" != "unknown" ]]; then
  schema_mismatch="⚠️  schema 版本不一致：state=${schema_version}, skill 期望=${LATEST_SCHEMA}。建议跑 /cheat-migrate（非阻塞，部分新功能可能在迁移前异常）。"
elif [[ "$schema_version" == "unknown" ]]; then
  schema_mismatch="⚠️  state.schema_version 字段缺失或损坏。建议跑 /cheat-status 检查文件，或备份后重 init。"
fi

# --- Detect blind-skip contamination (cheat-predict --skip-blind 或 Phase 2.5 选 b 触发) ---
self_scored_warning=""
if [[ "$last_prediction_self_scored" == "true" && -n "$last_self_scored_at" ]]; then
  # Parse timestamp; tolerate +08:00 or Z suffix
  self_scored_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${last_self_scored_at%%+*}" "+%s" 2>/dev/null || \
                      date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_self_scored_at" "+%s" 2>/dev/null || \
                      echo 0)
  if [[ $self_scored_epoch -gt 0 ]]; then
    days_since=$(( (now_epoch - self_scored_epoch) / 86400 ))
    if [[ $days_since -ge 7 ]]; then
      self_scored_warning="🚨 距上次 \`--skip-blind\` 自评预测已 ${days_since} 天——校准池累计的 contamination 风险在叠加。下次 /cheat-predict 走 sub-agent 即可清除此提示。"
    else
      self_scored_warning="⚠️  上次预测走了 \`--skip-blind\`（${days_since} 天前自评，未经 channel B 隔离）。下次 /cheat-predict 走默认即可清除。"
    fi
  fi
fi

# --- Derive confidence label (single source: state-management.md confidence 表) ---
if   [[ $calibration_samples -eq 0 ]]; then
  confidence="🔴 极低 (占星级别，纯纪律训练)"
elif [[ $calibration_samples -le 2 ]]; then
  confidence="🟠 低 (中枢 ±50%，方向感优于绝对数字)"
elif [[ $calibration_samples -le 5 ]]; then
  confidence="🟡 偏低 (中枢 ±40%，可作为参考之一)"
elif [[ $calibration_samples -le 10 ]]; then
  confidence="🟢 中 (中枢 ±25%，可参与决策)"
elif [[ $calibration_samples -le 20 ]]; then
  confidence="🟢 较高 (中枢 ±15%，rubric 形态稳定)"
else
  confidence="🔵 高 (中枢 ±10%，可数据驱动)"
fi

# --- Compute buffer color ---
buffer_label=""
buffer_warning=""
if [[ "$target_cadence" == "null" ]] || [[ -z "$target_cadence" ]]; then
  # Flexible cadence: no color, just count
  buffer_label="📦 Buffer: ${buffer_count} 篇 (灵活节奏，无警戒)"
else
  buffer_days=$(( buffer_count * target_cadence ))
  if   [[ $buffer_days -lt 1 ]]; then
    buffer_label="📦 Buffer: ${buffer_count} 篇 🔴 红 (按 cadence ${target_cadence}d = <1 天预备)"
    buffer_warning="🚨 buffer 警戒：下个发布日可能断更。今天必须拍 ≥1 条稳分。"
  elif [[ $buffer_days -le 2 ]]; then
    buffer_label="📦 Buffer: ${buffer_count} 篇 🟠 橙 (按 cadence ${target_cadence}d = ${buffer_days} 天预备)"
  elif [[ $buffer_days -le 5 ]]; then
    buffer_label="📦 Buffer: ${buffer_count} 篇 🟢 绿 (按 cadence ${target_cadence}d = ${buffer_days} 天预备)"
  else
    buffer_label="📦 Buffer: ${buffer_count} 篇 🔵 蓝 (按 cadence ${target_cadence}d = ${buffer_days} 天，积压)"
    buffer_warning="📦 buffer 积压：建议暂停拍摄，先发存货 + 复盘。"
  fi
fi

# --- Compute pending retros that are actually due ---
retro_window=3   # default RETRO_WINDOW_DAYS, hardcoded fallback (TODO: read from rubric_notes if present)
due_count=0
earliest_due=""
if [[ "$pending_retros_count" -gt 0 ]]; then
  # Walk pending_retros, check each prediction file's published_at
  while IFS= read -r pred_file; do
    pred_path="$PROJECT_DIR/$pred_file"
    if [[ -f "$pred_path" ]]; then
      pub_iso=$(grep -E '^\*\*Published at\*\*:' "$pred_path" 2>/dev/null | head -1 | sed -E 's/.*: *//')
      if [[ -n "$pub_iso" ]]; then
        pub_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${pub_iso%%+*}" "+%s" 2>/dev/null || echo 0)
        if [[ $pub_epoch -gt 0 ]]; then
          age_days=$(( (now_epoch - pub_epoch) / 86400 ))
          if [[ $age_days -ge $retro_window ]]; then
            due_count=$((due_count + 1))
            if [[ -z "$earliest_due" ]] || [[ "$pub_iso" < "$earliest_due" ]]; then
              earliest_due="$pub_iso"
            fi
          fi
        fi
      fi
    fi
  done < <(echo "$state" | jq -r '.pending_retros // [] | .[]')
fi

retro_label=""
if [[ $due_count -gt 0 ]]; then
  retro_label="⏰ 待复盘: ${due_count} 篇 (最早: ${earliest_due%%T*})"
elif [[ "$pending_retros_count" -gt 0 ]]; then
  retro_label="⏰ 待复盘: ${pending_retros_count} 篇 (未到 T+${retro_window}d)"
else
  retro_label="⏰ 待复盘: 无"
fi

# --- Top candidates (read first 3 H3 from candidates.md) ---
candidates_file="$PROJECT_DIR/candidates.md"
top_candidates=""
if [[ -f "$candidates_file" ]]; then
  # Extract first 3 H3 titles, format compactly
  top_candidates=$(grep -E '^### ' "$candidates_file" 2>/dev/null \
    | head -3 \
    | sed -E 's/^### \[[^]]+\] *//' \
    | tr '\n' '/' \
    | sed 's:/$::' \
    | sed 's:/: / :g')
fi
if [[ -z "$top_candidates" ]]; then
  candidates_label="🎯 候选: (空——说 '抓热点' 或 '找选题')"
else
  candidates_label="🎯 候选 top 3: ${top_candidates}"
fi

# --- Last trends run ---
trends_label=""
if [[ -n "$last_trends_at" ]]; then
  trends_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${last_trends_at%%+*}" "+%s" 2>/dev/null || echo 0)
  if [[ $trends_epoch -gt 0 ]]; then
    days_ago=$(( (now_epoch - trends_epoch) / 86400 ))
    trends_label="📅 上次抓热点: ${days_ago} 天前"
  fi
fi

# --- Build the report ---
echo ""
echo "[cheat-on-content / SessionStart 状态报告]"
echo ""
echo "$buffer_label"
echo "$retro_label"
echo "$candidates_label"
[[ -n "$trends_label" ]] && echo "$trends_label"

# Confidence indicator
echo "📈 校准样本: ${calibration_samples} | Confidence: ${confidence}"

# Warnings (high priority)
[[ -n "$buffer_warning" ]] && echo "" && echo "$buffer_warning"
[[ -n "$schema_mismatch" ]] && echo "" && echo "$schema_mismatch"
[[ -n "$self_scored_warning" ]] && echo "" && echo "$self_scored_warning"
if [[ "$form_severe_mismatch" == "true" ]]; then
  echo "❌ rubric 与你的内容形态严重不匹配——预测几乎无意义。"
fi
if [[ "$hooks_installed" != "true" ]]; then
  echo "⚠️  immutability hook 未装——你的盲预测保护是君子协定，不是物理强制。"
fi

echo ""
echo "（不要主动开始任何动作——等用户决定。说 \"状态\" 看完整看板。）"
echo ""

exit 0
