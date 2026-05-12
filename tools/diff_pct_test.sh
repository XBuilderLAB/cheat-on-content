#!/usr/bin/env bash
#
# diff_pct_test.sh — regression test for tools/diff_pct.py
#
# Validates 3 fixture cases that the legacy line-level diff failed:
#   case 1: long markdown lines vs spoken-transcript short lines, same content
#           → expected diff_pct < 30 (was ~198% under legacy)
#   case 2: completely different topic
#           → expected diff_pct ≥ 60
#   case 3: orig + ~20% new content appended
#           → expected diff_pct 10-30
#
# Usage:
#   bash tools/diff_pct_test.sh
# Exit:
#   0 = all pass
#   1 = ≥1 failure
#
# Runs against whichever backend is installed (rapidfuzz preferred, difflib
# fallback). Both should pass these ranges — they're chosen to be wide
# enough to absorb backend-algorithm differences.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DIFF_PCT="$SCRIPT_DIR/diff_pct.py"

if [[ ! -f "$DIFF_PCT" ]]; then
  echo "❌ diff_pct.py not found at $DIFF_PCT" >&2
  exit 1
fi

TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

PASS=0
FAIL=0

run_case() {
  local label="$1"
  local orig="$2"
  local new="$3"
  local min="$4"
  local max="$5"

  local stderr_out
  stderr_out=$(mktemp)
  local actual
  actual=$(python3 "$DIFF_PCT" "$orig" "$new" 2>"$stderr_out")
  local backend
  backend=$(grep -oE 'backend=[a-z]+' "$stderr_out" | head -1 || echo "backend=?")
  rm -f "$stderr_out"

  if (( actual >= min && actual <= max )); then
    echo "  ✓ $label: diff_pct=$actual ∈ [$min, $max]  ($backend)"
    PASS=$((PASS+1))
  else
    echo "  ✗ $label: diff_pct=$actual NOT in [$min, $max]  ($backend)"
    FAIL=$((FAIL+1))
  fi
}

echo ""
echo "=== Case 1: long markdown line vs spoken-transcript short lines, same content ==="

cat > "$TMP/case1_orig.md" <<'EOF'
# 视频草稿 — 评审会复盘

「最近发现一个现象」——所有审稿人都在说一样的话：你的研究太老套了。

但你仔细看，他们引用的全是 5 年前的反应。AI 不是新东西。新的是这次大家集体觉醒了。

**升维点**：当所有人都在追新概念的时候，先看穿规律的人已经在用工具赚钱了。
EOF

cat > "$TMP/case1_shot.md" <<'EOF'
最近发现一个现象
所有审稿人都在说一样的话
你的研究太老套了
但你仔细看
他们引用的全是
5 年前的反应
AI 不是新东西
新的是这次
大家集体觉醒了
当所有人都在追新概念的时候
先看穿规律的人
已经在用工具赚钱了
EOF

run_case "spoken-style line breaks, content preserved" \
  "$TMP/case1_orig.md" "$TMP/case1_shot.md" 0 30

echo ""
echo "=== Case 2: completely different topic ==="

cat > "$TMP/case2_orig.md" <<'EOF'
# AI 焦虑

最近 AI 大模型发布得太快了，每周一个新工具。
你刚学会一个，下周它就被淘汰了。
这种焦虑本质上是工具焦虑，不是能力焦虑。
真正不变的是你解决问题的范式——选好题、定好评估、跑通闭环。
EOF

cat > "$TMP/case2_shot.md" <<'EOF'
今天聊聊我家的猫
它叫橘子 是一只英短
最喜欢窝在窗台上晒太阳
我每天下班回家
看到它就忘了所有烦恼
它今天还偷吃了我的牛奶
被我发现了 装作没事
猫真是世界上最神奇的生物
EOF

run_case "completely different topic" \
  "$TMP/case2_orig.md" "$TMP/case2_shot.md" 60 100

echo ""
echo "=== Case 3: orig + ~20% appended (outro / CTA scenario) ==="

# Realistic 创作者 scenario: 拍前稿 ~150 字, 拍时加一句 30 字 outro
# 增量 / 原稿 ≈ 20%, Levenshtein/max(orig,new) ≈ 16-20%
cat > "$TMP/case3_orig.md" <<'EOF'
# 视频 — 关于宿命论

我以前不信宿命论。直到我跑了这个工具——它让我拍了一条视频，预测了流量。
我想证明它是错的，告诉了观众希望集体观测让数据偏移。结果数据是准的。
我没逃出宿命论。我只是从一阶跳到二阶——AI 在观测观测者。
EOF

cat > "$TMP/case3_shot.md" <<'EOF'
我以前不信宿命论。直到我跑了这个工具——它让我拍了一条视频，预测了流量。
我想证明它是错的，告诉了观众希望集体观测让数据偏移。结果数据是准的。
我没逃出宿命论。我只是从一阶跳到二阶——AI 在观测观测者。
此时此刻看到这条的你——是出于好奇，还是在完成算法的最后一次落位？
EOF

run_case "~20% appended outro" \
  "$TMP/case3_orig.md" "$TMP/case3_shot.md" 10 30

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [[ $FAIL -eq 0 ]]; then
  exit 0
else
  exit 1
fi
