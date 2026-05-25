#!/usr/bin/env bash
# diagnose.sh — Tell the agent what state the repo is in. Read-only,
# idempotent, stack-neutral. Run this first, every iteration.
#
# Project-specific signals (test matrix, coverage, scaffolding presence)
# are intentionally omitted from this generic version — add your own
# sections below the "Project signals" marker if useful.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== DEVELOPMENT STATE ==="
echo "Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "=== Iteration / Commits ==="
if git rev-parse --git-dir >/dev/null 2>&1; then
  COMMITS=$(git log --oneline 2>/dev/null | wc -l | tr -d ' ')
  echo "Total commits: $COMMITS"
  echo ""
  echo "Last 10:"
  git log --oneline -10 2>/dev/null || echo "  (no commits yet)"
else
  echo "  (not a git repo)"
fi
echo ""

echo "=== Active Goal ==="
ACTIVE_FILE="$ROOT/.state/active-goal"
if [ -f "$ACTIVE_FILE" ]; then
  ACTIVE=$(cat "$ACTIVE_FILE")
else
  ACTIVE="(unknown — run scripts/completion-check.sh first)"
fi
echo "  $ACTIVE"
if [ -d goals ]; then
  echo "  All goals:"
  seen_active=false
  for f in $(find goals -maxdepth 1 -type f \( -name '[0-9]*.md' -o -name '_meta.md' \) 2>/dev/null | sort -V); do
    name=$(basename "$f" .md)
    gate="goals/${name}.gates.sh"
    if [ -f "$gate" ]; then
      status="(not yet checked)"
      if [ -f "$ACTIVE_FILE" ]; then
        if [ "$(cat "$ACTIVE_FILE")" = "ALL_DONE" ]; then
          status="✓ passed"
        elif [ "$ACTIVE" = "$f" ]; then
          status="⚙ active (failing)"
          seen_active=true
        else
          # A goal preceding the active one was confirmed passing by
          # the last completion-check run.
          if [ "$seen_active" = false ]; then
            status="✓ passed"
          else
            status="(deferred — earlier goal is active)"
          fi
        fi
      fi
      echo "    - $f $status"
    else
      echo "    - $f (no gate script)"
    fi
  done
fi
echo ""

echo "=== Open Findings (docs/findings/) ==="
if [ -d docs/findings ]; then
  OPEN=0
  for f in $(find docs/findings -maxdepth 1 -name '*.md' -type f 2>/dev/null | sort); do
    base=$(basename "$f")
    case "$base" in AGENTS.md|README.md|CLAUDE.md|EXAMPLE.md) continue ;; esac
    # Read the `resolved:` field from the first frontmatter block.
    res=$(awk '/^---[[:space:]]*$/{c++; next} c==1 && /^resolved:/{sub(/^resolved:[[:space:]]*/,""); print; exit}' "$f")
    case "$res" in
      true) : ;;
      *) OPEN=$((OPEN+1)); echo "    - $base (resolved: ${res:-?})" ;;
    esac
  done
  [ "$OPEN" -eq 0 ] && echo "    (none open)"
else
  echo "    (no docs/findings/ directory)"
fi
echo ""

# ─── Project signals (add stack-specific sections here) ─────────────────
# Examples you might add:
#   - test pass/fail summary from your runner
#   - enumeration coverage of a source of truth (models / routes / specs)
#   - scaffolding presence checks
# Keep it read-only.

echo "=== Blockers ==="
if [ -s docs/state/blockers.md ]; then
  grep -vE '^(#|$)' docs/state/blockers.md | head -10 | sed 's/^/  /'
else
  echo "  (none)"
fi
echo ""

echo "=== Uncommitted Changes ==="
git status --short 2>/dev/null | head -20 | sed 's/^/  /' || echo "  (clean)"
echo ""

echo "=== Recommended Next Action ==="
bash "$ROOT/scripts/next-task.sh"
