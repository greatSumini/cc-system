#!/usr/bin/env bash
# next-task.sh — Dispatch to the active goal's per-goal task hint script.
#
# Reads .state/active-goal (written by completion-check.sh). If absent,
# falls back to the lowest-numbered goal in goals/. The hint is advisory:
# it channels the next action but does not gate anything.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ACTIVE_FILE="$ROOT/.state/active-goal"

if [ -f "$ACTIVE_FILE" ]; then
  ACTIVE=$(cat "$ACTIVE_FILE")
else
  ACTIVE=""
fi

if [ "$ACTIVE" = "ALL_DONE" ]; then
  cat <<'EOF'
TASK: All goals complete.
  - Every gate of every goal in goals/ passes.
  - Either add a new goals/<n>-<name>.md (+ .gates.sh + .next-task.sh),
    open a new cycle (see cycles/AGENTS.md), or stop.
EOF
  exit 0
fi

# Fallback: pick the lowest-numbered goal when the pointer is unset/stale.
if [ -z "$ACTIVE" ] || [ ! -f "$ACTIVE" ]; then
  ACTIVE=$(find goals -maxdepth 1 -type f \( -name '[0-9]*.md' -o -name '_meta.md' \) 2>/dev/null | sort -V | head -1)
fi

if [ -z "$ACTIVE" ] || [ ! -f "$ACTIVE" ]; then
  echo "TASK: No goal files found under goals/."
  echo "  - Create goals/0-init.md (mission), goals/0-init.gates.sh (gates),"
  echo "    goals/0-init.next-task.sh (next-task hints)."
  exit 0
fi

goal_name=$(basename "$ACTIVE" .md)
task_script="goals/${goal_name}.next-task.sh"

if [ ! -f "$task_script" ]; then
  cat <<EOF
TASK: Active goal '$goal_name' has no next-task script.
  - Run: bash goals/${goal_name}.gates.sh   # see which gate is failing
  - Then address it directly per goals/${goal_name}.md.
EOF
  exit 0
fi

exec bash "$task_script"
