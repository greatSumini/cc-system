#!/usr/bin/env bash
# goals/_meta.gates.sh — Cross-cutting gate suite (lint / typecheck / test / build).
#
# Captures invariants that span the whole repo rather than a single goal.
# Centralizing here eliminates duplicate execution across goals and CI,
# and lets each goal-local gate focus on its own universal claim.
#
# CONFIGURE: fill META_CHECKS and GATE_INPUTS for your stack (see below).
#
# Env:
#   GATES_SKIP_DEEP=1   skip checks whose label matches DEEP_LABELS_RE
#   GATES_NO_CACHE=1    bypass the content-fingerprint cache

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=../scripts/_gate-cache.sh
source "$ROOT/scripts/_gate-cache.sh"

# ─── CONFIGURE: your cross-cutting checks ───────────────────────────────
# Each entry is "Label::shell command". The command runs from the repo
# root and must exit non-zero on failure. Examples (uncomment + edit):
#   "typecheck::pnpm exec tsc --noEmit"
#   "lint::pnpm exec eslint . --max-warnings 0"
#   "test+coverage::pnpm exec vitest run --coverage"
#   "build::pnpm -r build"
#   "test::pytest -q"
#   "lint::ruff check ."
#   "typecheck::mypy ."
#   "build::cargo build --locked"
#   "test::cargo test"
#   "test::go test ./..."
#   "vet::go vet ./..."
META_CHECKS=(
  # "typecheck::<command>"
  # "lint::<command>"
  # "test::<command>"
  # "build::<command>"
)

# ─── CONFIGURE: files whose change should bust this gate's cache ────────
# Broaden to cover your source + config so any code change re-runs the
# suite. Keep the three self-references at the end.
GATE_INPUTS=(
  # src
  # tests
  # package.json
  # pyproject.toml
  # Cargo.toml
  # go.mod
  goals/_meta.gates.sh
  goals/_meta.md
  scripts/_gate-cache.sh
)

# Labels matching this (case-insensitive) are "deep" — skipped under
# GATES_SKIP_DEEP=1 for fast inner-loop iteration.
DEEP_LABELS_RE='test|build|e2e|coverage|integration'

# ─── Cache key: shallow runs never satisfy the full `_meta` key, so a
# full check is always forced after an input change until one runs. ─────
if [ "${GATES_SKIP_DEEP:-}" = "1" ]; then
  CACHE_KEY="_meta-shallow"
else
  CACHE_KEY="_meta"
fi

if gate_cache_hit "$CACHE_KEY" "${GATE_INPUTS[@]}"; then
  echo "[cache hit] _meta ($CACHE_KEY) inputs unchanged"
  exit 0
fi

if [ "${#META_CHECKS[@]}" -eq 0 ]; then
  echo "[_meta] no checks configured."
  echo "    ⚠ passing vacuously — edit META_CHECKS in goals/_meta.gates.sh to"
  echo "      wire your lint / typecheck / test / build commands."
  gate_cache_save "$CACHE_KEY" "${GATE_INPUTS[@]}"
  [ "$CACHE_KEY" = "_meta" ] && gate_cache_save "_meta-shallow" "${GATE_INPUTS[@]}"
  exit 0
fi

PASS=true
LOG_DIR=$(mktemp -d)
cleanup_meta_logs() {
  if [ "$PASS" = true ]; then
    rm -rf "$LOG_DIR"
  else
    echo "    logs retained at $LOG_DIR"
  fi
}
trap cleanup_meta_logs EXIT

# Enumerate every configured check — universal claim ⇒ universal gate.
i=0
for entry in "${META_CHECKS[@]}"; do
  i=$((i + 1))
  label="${entry%%::*}"
  cmd="${entry#*::}"
  is_deep=false
  printf '%s' "$label" | grep -iqE "$DEEP_LABELS_RE" && is_deep=true
  if [ "$is_deep" = true ] && [ "${GATES_SKIP_DEEP:-}" = "1" ]; then
    echo "[M.$i $label] ⊘ skipped (GATES_SKIP_DEEP=1)"
    continue
  fi
  echo "[M.$i $label] $cmd"
  log="$LOG_DIR/m$i.log"
  if bash -c "$cmd" >"$log" 2>&1; then
    echo "    ✓ pass"
  else
    echo "    ✗ fail — see $log"
    PASS=false
  fi
done

if [ "$PASS" = true ]; then
  gate_cache_save "$CACHE_KEY" "${GATE_INPUTS[@]}"
  [ "$CACHE_KEY" = "_meta" ] && gate_cache_save "_meta-shallow" "${GATE_INPUTS[@]}"
  exit 0
fi
exit 1
