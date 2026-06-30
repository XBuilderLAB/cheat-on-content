#!/usr/bin/env bash
#
# One-shot package verification for cheat-on-content maintainers.
# It is intentionally local-only: no network calls and no user project writes.

set -uo pipefail

ROOT="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )"
FAILURES=0

fail() {
  echo "❌ $*"
  FAILURES=$((FAILURES + 1))
}

pass() {
  echo "✓ $*"
}

check_cmd() {
  local label="$1"
  shift
  if "$@" >/tmp/cheat-verify.$$.out 2>/tmp/cheat-verify.$$.err; then
    pass "$label"
  else
    fail "$label"
    sed 's/^/    /' /tmp/cheat-verify.$$.err
  fi
  rm -f /tmp/cheat-verify.$$.out /tmp/cheat-verify.$$.err
}

echo "== cheat-on-content package verification =="
echo "root: $ROOT"
echo

echo "== install list =="
skills=()
while IFS= read -r skill_name; do
  skills+=("$skill_name")
done < <(
  awk '
    /^SUB_SKILLS=\(/ { inside=1; next }
    inside && /^\)/ { exit }
    inside {
      sub(/#.*/, "")
      gsub(/[[:space:]]/, "")
      if (length($0) > 0) print $0
    }
  ' "$ROOT/install.sh"
)

if [[ "${#skills[@]}" -eq 15 ]]; then
  pass "install.sh declares 15 sub-skills"
else
  fail "install.sh declares ${#skills[@]} sub-skills, expected 15"
fi

for skill in "${skills[@]}"; do
  if [[ -f "$ROOT/skills/$skill/SKILL.md" ]]; then
    pass "skill exists: $skill"
  else
    fail "missing skill: skills/$skill/SKILL.md"
  fi
done

echo
echo "== package structure =="
if find "$ROOT/skills" -type l | grep -q .; then
  fail "skills/ contains symlinks:"
  find "$ROOT/skills" -type l -print | sed 's/^/    /'
else
  pass "skills/ contains no symlinks"
fi

GIT_TOP=$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null || true)
if [[ -n "$GIT_TOP" && "$ROOT" == "$GIT_TOP"* ]]; then
  rel_root="${ROOT#"$GIT_TOP"/}"
  if [[ "$rel_root" == "$ROOT" ]]; then
    rel_root="."
  fi
  gitlinks=$(git -C "$GIT_TOP" ls-files --stage -- "$rel_root/skills" 2>/dev/null | awk '$1 == "160000" { print $4 }')
  active_gitlinks=""
  if [[ -n "$gitlinks" ]]; then
    while IFS= read -r gitlink_path; do
      [[ -z "$gitlink_path" ]] && continue
      # During a conversion, the index may still remember a deleted gitlink until
      # the maintainer stages the delete/add. Treat deleted gitlinks as pending
      # conversion, but fail if the gitlink still exists in the working tree.
      if [[ -e "$GIT_TOP/$gitlink_path" || -L "$GIT_TOP/$gitlink_path" ]]; then
        active_gitlinks="${active_gitlinks}${gitlink_path}"$'\n'
      fi
    done <<< "$gitlinks"
  fi
  if [[ -n "$active_gitlinks" ]]; then
    fail "skills/ contains active gitlinks:"
    echo "$active_gitlinks" | sed '/^$/d; s/^/    /'
  else
    pass "skills/ contains no active gitlinks"
  fi

  if [[ "$ROOT" != "$GIT_TOP" ]]; then
    flat_found=0
    for dirname in adapters skills hooks migrations shared-references templates tools; do
      if [[ -e "$GIT_TOP/$dirname" ]]; then
        echo "    $GIT_TOP/$dirname"
        flat_found=1
      fi
    done
    if [[ "$flat_found" -eq 0 ]]; then
      pass "no upstream-flattened package dirs at repository root"
    else
      fail "found package dirs at repository root; keep them under cheat-on-content/"
    fi
  fi
fi

echo
echo "== shell syntax =="
while IFS= read -r sh_file; do
  check_cmd "bash -n ${sh_file#$ROOT/}" bash -n "$sh_file"
done < <(
  find "$ROOT" \
    \( -path "$ROOT/install.sh" -o -path "$ROOT/uninstall.sh" -o -path "$ROOT/hooks/*.sh" -o -path "$ROOT/adapters/perf-data/*/run.sh" -o -path "$ROOT/adapters/script-extraction/*/run.sh" -o -path "$ROOT/tools/*.sh" \) \
    -type f | sort
)

echo
echo "== python syntax =="
while IFS= read -r py_file; do
  check_cmd "py_compile ${py_file#$ROOT/}" python3 -m py_compile "$py_file"
done < <(
  find "$ROOT/tools" "$ROOT/adapters/perf-data" "$ROOT/skills" -name '*.py' -type f | sort
)

echo
echo "== focused tests =="
if [[ -x "$ROOT/tools/diff_pct_test.sh" || -f "$ROOT/tools/diff_pct_test.sh" ]]; then
  check_cmd "diff_pct_test.sh" bash "$ROOT/tools/diff_pct_test.sh"
else
  fail "missing tools/diff_pct_test.sh"
fi

echo
echo "== xhs writing rules =="
python3 - "$ROOT" <<'PY'
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = {
    "starter-rubrics/xhs-post.md": root / "starter-rubrics" / "xhs-post.md",
    "starter-rubrics/xhs-post-zero.md": root / "starter-rubrics" / "xhs-post-zero.md",
    "skills/cheat-seed/SKILL.md": root / "skills" / "cheat-seed" / "SKILL.md",
    "templates/xhs-post.template.md": root / "templates" / "xhs-post.template.md",
}
combined = "\n".join(path.read_text() for path in files.values())
required = [
    "≤20",
    "600-900",
    "前 2 行",
    "清单体",
    "教程体",
    "故事体",
    "对比体",
    "测评体",
    "每段 2-4 句",
]
missing = [item for item in required if item not in combined]
missing_files = [name for name, path in files.items() if not path.exists()]
if missing_files or missing:
    if missing_files:
        print("missing files:", ", ".join(missing_files), file=sys.stderr)
    if missing:
        print("missing rules:", ", ".join(missing), file=sys.stderr)
    raise SystemExit(1)
PY
if [[ "$?" -eq 0 ]]; then
  pass "xhs title/body/layout rules present"
else
  fail "xhs title/body/layout rules missing"
fi

echo
echo "== install help =="
if bash "$ROOT/install.sh" --help | grep -q "15 sub-skills"; then
  pass "install.sh --help reports 15 sub-skills"
else
  fail "install.sh --help does not report 15 sub-skills"
fi

echo
if [[ "$FAILURES" -eq 0 ]]; then
  echo "✅ verify-package passed"
  exit 0
else
  echo "❌ verify-package failed: $FAILURES issue(s)"
  exit 1
fi
