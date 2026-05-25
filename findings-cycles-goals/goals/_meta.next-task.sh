#!/usr/bin/env bash
# goals/_meta.next-task.sh — invoked when _meta is the active failing goal.

set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cat <<'EOF'
# Goal _meta: cross-cutting invariants failed

A cross-cutting check (lint / typecheck / test+coverage / build) is red.
Re-run the meta suite to see which check failed and where its log is:

    bash goals/_meta.gates.sh

Fix the underlying code (do NOT weaken the check, disable a test, or lower
a coverage threshold). Once _meta passes, completion-check resumes the
numeric goal sweep.

If _meta says "no checks configured", wire your stack's commands into the
META_CHECKS array in goals/_meta.gates.sh first.
EOF
