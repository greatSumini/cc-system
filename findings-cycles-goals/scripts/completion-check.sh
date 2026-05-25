#!/usr/bin/env bash
# completion-check.sh — Parallel orchestrator for all goal gate suites.
#
# Discovers every goals/<n>-<name>.md, launches each matching
# <n>-<name>.gates.sh as a background worker (bounded by
# $GATES_CONCURRENCY, default 4), then aggregates per-goal stdout in
# numeric order. Writes the first numerically-failing goal's path to
# .state/active-goal so diagnose.sh / next-task.sh route correctly. Exit
# 0 only when every gate of every goal passes.
#
# This script is the only owner of the "no prior-goal regression"
# semantics: per-goal scripts do not chain into earlier goals. Running a
# single `bash goals/<n>-*.gates.sh` checks that goal's surface only —
# run this orchestrator for the full chain.
#
# Env:
#   GATES_CONCURRENCY  default 4; cap on parallel workers (0 → serial)
#   GATES_SKIP_DEEP    default 1 (skip external-system gates like Docker
#                      spin-up, deploy state). Set to 0 explicitly to run
#                      the full world-state suite (release check / job).
#   GATES_NO_CACHE     propagated to workers; bypasses the gate cache
#   GATES_SKIP_META    skip the cross-cutting goals/_meta gate suite (CI
#                      often runs lint/typecheck/test/build as explicit
#                      steps, so it sets this to avoid duplicating work)

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p "$ROOT/.state"
ACTIVE_FILE="$ROOT/.state/active-goal"

CONCURRENCY="${GATES_CONCURRENCY:-4}"
case "$CONCURRENCY" in
  ''|*[!0-9]*) CONCURRENCY=2 ;;
  0) CONCURRENCY=1 ;;
esac

# Default to skipping external-system gates. The chain is meant to verify
# the *code contract* deterministically; deploy/Docker state is checked by
# a separate cadence. Callers that need full world verification (release
# checklists, a scheduled job) override with GATES_SKIP_DEEP=0.
export GATES_SKIP_DEEP="${GATES_SKIP_DEEP:-1}"

GOALS=()
META_MD=""
while IFS= read -r f; do
  if [ "$(basename "$f")" = "_meta.md" ]; then
    META_MD="$f"
  else
    GOALS+=("$f")
  fi
done < <(find goals -maxdepth 1 -type f \( -name '[0-9]*.md' -o -name '_meta.md' \) 2>/dev/null | sort -V)

# Meta is launched first so its slot in the parallel pool starts at t=0.
# When GATES_CONCURRENCY is low and _meta dominates wall-clock (lint+tsc+
# test+builds), this overlaps meta work with the lightest numeric goals
# instead of leaving meta as a serial tail.
#
# CI workflows that already run lint/typecheck/test/build as explicit
# steps (for per-step visibility in the Actions UI) set GATES_SKIP_META=1
# to avoid duplicating that work here. The meta claims are still enforced
# — by the workflow itself.
if [ -n "$META_MD" ] && [ "${GATES_SKIP_META:-}" != "1" ]; then
  GOALS=("$META_MD" "${GOALS[@]}")
fi

if [ "${#GOALS[@]}" -eq 0 ]; then
  echo "✗ completion-check: no goals/*.md found."
  echo "(none)" > "$ACTIVE_FILE"
  exit 1
fi

STAGE_DIR=$(mktemp -d)
trap 'rm -rf "$STAGE_DIR"' EXIT

# Parallel arrays indexed by goal position.
GOAL_NAMES=()
GOAL_OUT_FILES=()
GOAL_PIDS=()
GOAL_LAUNCH_FAILED=()

launch_goal() {
  local idx="$1"
  local goal_md="$2"
  local goal_name
  goal_name=$(basename "$goal_md" .md)
  local gate_script="goals/${goal_name}.gates.sh"
  local out_file="$STAGE_DIR/${goal_name}.out"

  GOAL_NAMES[$idx]="$goal_name"
  GOAL_OUT_FILES[$idx]="$out_file"

  if [ ! -f "$gate_script" ] && [ ! -x "$gate_script" ]; then
    printf '✗ missing gate script: %s\n' "$gate_script" > "$out_file"
    GOAL_PIDS[$idx]=0
    GOAL_LAUNCH_FAILED[$idx]=1
    return
  fi

  GOAL_LAUNCH_FAILED[$idx]=0
  bash "$gate_script" >"$out_file" 2>&1 &
  GOAL_PIDS[$idx]=$!
  printf '▷ %s (pid %s)\n' "$goal_name" "${GOAL_PIDS[$idx]}"
}

wait_for_slot() {
  while :; do
    local running
    running=$(jobs -rp 2>/dev/null | wc -l | tr -d ' ')
    if [ "$running" -lt "$CONCURRENCY" ]; then
      return 0
    fi
    sleep 0.2
  done
}

echo "=== COMPLETION CHECK (parallel, concurrency=$CONCURRENCY) ==="
echo

OVERALL_PASS=true
FIRST_FAIL_MD=""

# Meta: orchestrator-owned rigor sweep. Closes the leak where a prior
# goal's .md is not in its own GATE_INPUTS — direct edits to those .md
# files would otherwise sit behind a stale cache. Cheap, runs before the
# parallel goal workers so doc/gate drift fails fast.
echo "--- Meta: gate rigor sweep (every .md ↔ .gates.sh) ---"

RIGOR_CACHE_DIR="$ROOT/.state/gate-cache"
RIGOR_CACHE_FILE="$RIGOR_CACHE_DIR/_meta-rigor"

rigor_inputs() {
  find goals -maxdepth 1 -type f \
    \( -name '[0-9]*.md' -o -name '_meta.md' -o -name '[0-9]*.gates.sh' -o -name '_meta.gates.sh' \) \
    2>/dev/null | sort -V
}

rigor_fingerprint() {
  local files=()
  while IFS= read -r f; do
    files+=("$f")
  done < <(rigor_inputs)
  if [ "${#files[@]}" -eq 0 ]; then
    echo ""
    return
  fi
  cat "${files[@]}" 2>/dev/null | shasum -a 256 2>/dev/null | awk '{print $1}'
}

rigor_cache_fresh() {
  [ -f "$RIGOR_CACHE_FILE" ] || return 1
  local cached current
  cached=$(cat "$RIGOR_CACHE_FILE" 2>/dev/null || true)
  current=$(rigor_fingerprint)
  [ -n "$cached" ] && [ "$cached" = "$current" ] || return 1
  # Defensive: cache file mtime must be newer than every input.
  while IFS= read -r f; do
    if [ "$f" -nt "$RIGOR_CACHE_FILE" ]; then
      return 1
    fi
  done < <(rigor_inputs)
  return 0
}

if ! bash "$ROOT/scripts/check-gate-rigor.sh" --self-test >/dev/null 2>&1; then
  echo "    ✗ rigor self-test failed — UNIVERSAL_RE may be broken"
  OVERALL_PASS=false
fi

if rigor_cache_fresh; then
  echo "    ✓ cache hit — rigor sweep skipped (fingerprint unchanged)"
else
  if bash "$ROOT/scripts/check-gate-rigor.sh" --all; then
    echo "    ✓ every goal's universal claims match an iterating gate"
    mkdir -p "$RIGOR_CACHE_DIR"
    rigor_fingerprint > "$RIGOR_CACHE_FILE"
  else
    echo "    ✗ rigor mismatch — fix .md or its gate before continuing"
    OVERALL_PASS=false
    while IFS= read -r md; do
      if ! bash "$ROOT/scripts/check-gate-rigor.sh" "$md" >/dev/null 2>&1; then
        FIRST_FAIL_MD="$md"
        break
      fi
    done < <(find goals -maxdepth 1 -type f \( -name '[0-9]*.md' -o -name '_meta.md' \) | sort -V)
  fi
fi
echo

idx=0
for goal_md in "${GOALS[@]}"; do
  wait_for_slot
  launch_goal "$idx" "$goal_md"
  idx=$((idx + 1))
done

echo
echo "--- collecting results ---"
echo

idx=0
for goal_md in "${GOALS[@]}"; do
  pid="${GOAL_PIDS[$idx]}"
  goal_name="${GOAL_NAMES[$idx]}"
  out_file="${GOAL_OUT_FILES[$idx]}"
  launch_failed="${GOAL_LAUNCH_FAILED[$idx]}"

  if [ "$launch_failed" = "1" ]; then
    goal_exit=1
  else
    if wait "$pid"; then
      goal_exit=0
    else
      goal_exit=$?
    fi
  fi

  echo "--- Goal: $goal_name ($goal_md) ---"
  if [ -f "$out_file" ]; then
    cat "$out_file"
  fi
  if [ "$goal_exit" -eq 0 ]; then
    printf '    ✓ goal %s passes all gates.\n' "$goal_name"
  else
    printf '    ✗ goal %s has failing gates.\n' "$goal_name"
    OVERALL_PASS=false
    if [ -z "$FIRST_FAIL_MD" ]; then
      FIRST_FAIL_MD="$goal_md"
    fi
  fi
  printf '\n'

  idx=$((idx + 1))
done

if [ "$OVERALL_PASS" = true ]; then
  echo "ALL_DONE" > "$ACTIVE_FILE"
  echo "🎉 ALL GOALS ACHIEVED. Every gate of every goal passes."
  exit 0
fi

echo "$FIRST_FAIL_MD" > "$ACTIVE_FILE"
echo "⚠ Active goal: $(cat "$ACTIVE_FILE")"
echo "  Continue iterating against that goal."
exit 1
