#!/usr/bin/env bash
# active-check.sh — Per-iteration gate check.
#
# Runs only the *active* goal's gates plus the orchestrator-owned rigor
# sweep. Prior-goal regression is deliberately NOT checked here — that
# work is delegated to scripts/completion-check.sh, which runs:
#   1. when the active goal turns green (this script exec's into it to
#      advance the active-goal pointer and catch any silent prior
#      regression at the goal boundary),
#   2. before push when scripts/hooks/pre-push is installed or a manual
#      full verify is run, and
#   3. in CI on every PR.
#
# Cost: ~5–30 s depending on which goal is active, vs. 1–3 min for the
# full sweep. Use this for the inner TDD loop; let completion-check
# handle the boundaries.
#
# Usage:
#   bash scripts/active-check.sh
#
# Exit codes:
#   0 — rigor green AND (active goal green → orchestrator advanced)
#       OR (no active goal → orchestrator bootstrapped)
#   1 — rigor failed, or active goal still has failing gates

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p "$ROOT/.state"
ACTIVE_FILE="$ROOT/.state/active-goal"

# Per-iteration runs default to skipping external-system gates so the
# inner TDD loop stays deterministic.
export GATES_SKIP_DEEP="${GATES_SKIP_DEEP:-1}"

echo "=== ACTIVE-GOAL CHECK ==="
echo

# Rigor sweep — cheap, every iter. Catches .md ↔ .gates.sh drift the
# moment it happens, regardless of which goal is active.
echo "--- Meta: gate rigor sweep (every .md ↔ .gates.sh) ---"
if bash "$ROOT/scripts/check-gate-rigor.sh" --all; then
  echo "    ✓ rigor green"
else
  echo "    ✗ rigor failed — fix .md or .gates.sh above before continuing"
  exit 1
fi
echo

# Resolve active goal. If unknown / stale, defer to the full orchestrator
# to bootstrap.
ACTIVE=""
if [ -f "$ACTIVE_FILE" ]; then
  ACTIVE=$(cat "$ACTIVE_FILE")
fi

if [ -z "$ACTIVE" ]; then
  echo "--- No active-goal recorded — bootstrapping via completion-check ---"
  exec bash "$ROOT/scripts/completion-check.sh"
fi

if [ "$ACTIVE" = "ALL_DONE" ]; then
  cat <<'EOF'
🎉 active-goal = ALL_DONE.
   Nothing to do at the iteration level.
   To re-verify the full chain: bash scripts/completion-check.sh
EOF
  exit 0
fi

if [ ! -f "$ACTIVE" ]; then
  echo "--- Active-goal points at $ACTIVE which no longer exists — re-bootstrapping ---"
  exec bash "$ROOT/scripts/completion-check.sh"
fi

goal_name=$(basename "$ACTIVE" .md)
gate_script="goals/${goal_name}.gates.sh"

if [ ! -f "$gate_script" ]; then
  echo "✗ missing gate script: $gate_script"
  exit 1
fi

echo "--- Active goal: $goal_name ---"
if bash "$gate_script"; then
  echo
  echo "    ✓ active goal $goal_name turned green."
  echo "    → running full completion-check to (a) advance pointer and"
  echo "      (b) catch any silent prior-goal regression at this boundary."
  echo
  exec bash "$ROOT/scripts/completion-check.sh"
fi

echo
cat <<EOF
    ✗ active goal $goal_name still has failing gates.
      Prior-goal regression is NOT checked at the iteration level —
      staged impact is caught at commit time; the full sweep is caught
      at pre-push/CI/manual verify. To verify the full chain right now:
        bash scripts/completion-check.sh
EOF
exit 1
