#!/usr/bin/env bash
#
# cheat-on-content / uninstall.sh
#
# Removes the 14 cheat-on-content skills from Claude Code and/or Codex skill dirs.
#
# Does NOT touch any content project's data (.cheat-state.json, predictions/,
# rubric_notes.md, candidates.md, etc.) — those live in your content directories
# and uninstalling the skill leaves your work intact.
#
# Usage:
#   bash uninstall.sh          # remove Claude Code install (default)
#   bash uninstall.sh --codex  # remove Codex install
#   bash uninstall.sh --all    # remove both
#
# To re-install: bash install.sh

set -euo pipefail

SUB_SKILLS=(
  cheat-init
  cheat-learn-from
  cheat-seed
  cheat-score
  cheat-score-blind
  cheat-predict
  cheat-shoot
  cheat-publish
  cheat-retro
  cheat-bump
  cheat-recommend
  cheat-trends
  cheat-status
  cheat-migrate
)

CLAUDE_SKILLS=("${SUB_SKILLS[@]}")
CODEX_SKILLS=(cheat-on-content "${SUB_SKILLS[@]}")

TARGET_AGENT="claude"
for arg in "$@"; do
  case "$arg" in
    --claude)
      TARGET_AGENT="claude"
      ;;
    --codex)
      TARGET_AGENT="codex"
      ;;
    --all)
      TARGET_AGENT="all"
      ;;
    --help|-h)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $arg"
      echo "   Usage: bash uninstall.sh [--claude|--codex|--all]"
      exit 1
      ;;
  esac
done

REMOVED=0

remove_skills() {
  local label="$1"
  local target_dir="$2"
  shift 2

  echo ""
  echo "Removing cheat-on-content from $label:"
  echo "  target: $target_dir/"
  echo ""

  for s in "$@"; do
    local target="$target_dir/$s"
    if [[ -L "$target" ]]; then
      rm "$target"
      echo "  ✓ removed symlink:   $s"
      REMOVED=$((REMOVED + 1))
    elif [[ -d "$target" ]]; then
      rm -rf "$target"
      echo "  ✓ removed directory: $s"
      REMOVED=$((REMOVED + 1))
    else
      echo "  · not found:         $s (skipped)"
    fi
  done
}

if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  remove_skills "Claude Code" "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}"
fi

if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  remove_skills "Codex" "$HOME/.codex/skills" "${CODEX_SKILLS[@]}"
fi

echo ""
if [[ $REMOVED -gt 0 ]]; then
  echo "✅ Uninstalled $REMOVED skill(s)."
else
  echo "ℹ️  Nothing to uninstall."
fi
echo ""
echo "Note: your content projects' data (predictions/, rubric_notes.md, .cheat-state.json,"
echo "      .cheat-hooks/, candidates.md, etc.) are NOT touched. They live in each content"
echo "      project directory. To clean a specific content project, delete those files manually."
echo ""
echo "To re-install: bash install.sh [--codex|--all] (from cheat-on-content source root)"
echo ""
