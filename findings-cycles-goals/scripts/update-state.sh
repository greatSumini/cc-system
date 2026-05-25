#!/usr/bin/env bash
# update-state.sh — Refresh docs/state/* from git + goal status.
# Stack-neutral: it records commit count, the active goal, the goal chain,
# and the current next-task hint. Extend the progress block with your own
# project matrices (test status, coverage, enumeration counts) as needed.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STATE="$ROOT/docs/state"
mkdir -p "$STATE"

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
COMMITS=$(git log --oneline 2>/dev/null | wc -l | tr -d ' ')
LAST=$(git log -1 --pretty='%h %s' 2>/dev/null || echo '(none)')

ACTIVE_GOAL="(unknown — run scripts/completion-check.sh)"
if [ -f "$ROOT/.state/active-goal" ]; then
  ACTIVE_GOAL=$(cat "$ROOT/.state/active-goal")
fi

{
  echo "# Progress"
  echo ""
  echo "_Last updated: ${NOW}_"
  echo ""
  echo "## Overall"
  echo ""
  echo "- Commits: $COMMITS"
  echo "- Last commit: $LAST"
  echo "- Active goal: $ACTIVE_GOAL"
  echo ""
  echo "## Goal chain"
  echo ""
  echo "| Goal | Gate script | Next-task hint |"
  echo "| --- | --- | --- |"
  for f in $(find goals -maxdepth 1 -type f \( -name '[0-9]*.md' -o -name '_meta.md' \) 2>/dev/null | sort -V); do
    name=$(basename "$f" .md)
    g="goals/${name}.gates.sh"; [ -f "$g" ] && g="✓" || g="✗ missing"
    t="goals/${name}.next-task.sh"; [ -f "$t" ] && t="✓" || t="—"
    echo "| $name | $g | $t |"
  done
} > "$STATE/progress.md"

# Regenerate next-task.md by piping next-task.sh output.
{
  echo "# Next Task"
  echo ""
  echo "_Auto-generated $NOW. Do not hand-edit; use blockers.md for overrides._"
  echo ""
  echo '```'
  bash "$ROOT/scripts/next-task.sh"
  echo '```'
} > "$STATE/next-task.md"

# Ensure the append-only state files exist.
[ -f "$STATE/blockers.md" ] || cat > "$STATE/blockers.md" <<'EOF'
# Blockers

_Append-only. Mark resolved with ~~strikethrough~~ rather than deleting._

EOF

[ -f "$STATE/learnings.md" ] || cat > "$STATE/learnings.md" <<'EOF'
# Learnings

_Append-only. One bullet per learning. Keep it terse._

EOF

echo "✓ update-state: refreshed progress.md and next-task.md."
