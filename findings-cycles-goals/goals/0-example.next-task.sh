#!/usr/bin/env bash
# goals/0-example.next-task.sh — advisory hint for the example goal.

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if bash "$ROOT/goals/0-example.gates.sh" >/dev/null 2>&1; then
  cat <<'MSG'
TASK: Goal 0-example is green.
  - This is a teaching example. Replace it with your real goal 0:
    author goals/0-<name>.{md,gates.sh,next-task.sh} from your spec,
    then delete the 0-example triplet.
  - Run: bash scripts/completion-check.sh
MSG
else
  cat <<'MSG'
TASK: Make goal 0-example green (RED first).
  - Add a #! shebang as line 1 of any runnable scripts/*.sh that lacks one.
  - Re-run: bash goals/0-example.gates.sh
MSG
fi
