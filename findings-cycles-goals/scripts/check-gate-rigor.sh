#!/usr/bin/env bash
# check-gate-rigor.sh — Meta-gate: if a goal's markdown claims universality
# ("every / all / each <entity / model / route / file / command / test …>"),
# the matching `<n>-<name>.gates.sh` MUST contain at least one iteration
# construct (for / while / find / xargs / mapfile / readarray).
#
# Why this exists: a persistence gate that "passes" by testing a single
# record while the goal text claims "every entity" is a cheat. The fix is
# not to police phrasing but to require gates to enumerate from a source
# of truth. A universal claim demands a universal gate.
#
# The noun list below is deliberately broad and stack-neutral. Tune it for
# your domain if needed, but keep the --self-test green (completion-check
# runs it). Over-matching is safe — it only asks a gate to enumerate;
# under-matching lets a narrow-gate cheat through.
#
# Usage:
#   scripts/check-gate-rigor.sh                  # checks the active goal
#   scripts/check-gate-rigor.sh goals/2-foo.md   # checks one goal
#   scripts/check-gate-rigor.sh --all            # checks all goals
#   scripts/check-gate-rigor.sh --self-test      # smoke-test the regex

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

QUANT='(every|all|each)'
NOUN='(entit(y|ies)|models?|tables?|records?|rows?|routes?|endpoints?|apis?|files?|modules?|packages?|commands?|subcommands?|functions?|methods?|class(es)?|components?|pages?|views?|fields?|columns?|propert(y|ies)|tests?|use ?cases?|rules?|checks?|gates?|invariants?|migrations?|schemas?|types?|interfaces?|handlers?|services?|events?|messages?|quer(y|ies)|mutations?|resolvers?|enums?|configs?|settings?|flags?|verbs?|entrypoints?|scenarios?)'
UNIVERSAL_RE="${QUANT} ([a-zA-Z-]+ )?${NOUN}"
ITER_RE='\<for\>|while\s+IFS|while\s+read|\<find\>|\<xargs\>|mapfile|readarray'

check_one() {
  local md="$1"
  local name gate
  name=$(basename "$md" .md)
  gate="goals/${name}.gates.sh"

  if [ ! -f "$gate" ]; then
    echo "✗ check-gate-rigor: $gate missing"
    return 1
  fi

  local claims
  claims=$(grep -iEo "$UNIVERSAL_RE" "$md" | sort -u || true)
  if [ -z "$claims" ]; then
    return 0
  fi

  if grep -qE "$ITER_RE" "$gate" 2>/dev/null; then
    return 0
  fi

  echo "✗ check-gate-rigor: $name claims universality:"
  echo "$claims" | sed 's/^/        /'
  echo "    but $gate has no for / while / find / xargs iteration."
  return 1
}

case "${1:-}" in
  --self-test)
    MUST_MATCH=(
      "every entity must"
      "all routes should"
      "each command is"
      "every use case must"
      "every file in"
      "all models are"
      "every test passes"
      "each scenario must"
      "every endpoint should"
    )
    MUST_NOT=(
      "some entity"
      "most routes"
      "the test"
      "every time"
      "all good"
      "each other"
    )
    SELF_FAIL=0
    for phrase in "${MUST_MATCH[@]}"; do
      if ! echo "$phrase" | grep -iqE "$UNIVERSAL_RE"; then
        echo "✗ self-test FAIL: should match — '$phrase'"
        SELF_FAIL=1
      fi
    done
    for phrase in "${MUST_NOT[@]}"; do
      if echo "$phrase" | grep -iqE "$UNIVERSAL_RE"; then
        echo "✗ self-test FAIL: should NOT match — '$phrase'"
        SELF_FAIL=1
      fi
    done
    if [ "$SELF_FAIL" -eq 0 ]; then
      echo "✓ check-gate-rigor --self-test: UNIVERSAL_RE passes smoke cases"
      exit 0
    fi
    exit 1
    ;;
  --all)
    FAIL=0
    while IFS= read -r md; do
      check_one "$md" || FAIL=1
    done < <(find goals -maxdepth 1 -type f \( -name '[0-9]*.md' -o -name '_meta.md' \) | sort -V)
    if [ "$FAIL" -ne 0 ]; then
      exit 1
    fi
    echo "✓ check-gate-rigor: every goal with universal claims has an iterating gate"
    exit 0
    ;;
  '')
    ACTIVE_FILE="$ROOT/.state/active-goal"
    if [ -f "$ACTIVE_FILE" ]; then
      ACTIVE=$(cat "$ACTIVE_FILE")
    else
      ACTIVE=""
    fi
    if [ -z "$ACTIVE" ] || [ "$ACTIVE" = ALL_DONE ] || [ ! -f "$ACTIVE" ]; then
      echo "✓ check-gate-rigor: no failing goal to check"
      exit 0
    fi
    if check_one "$ACTIVE"; then
      echo "✓ check-gate-rigor: $(basename "$ACTIVE" .md) gate iterates as required"
      exit 0
    fi
    exit 1
    ;;
  *)
    if [ ! -f "$1" ]; then
      echo "✗ check-gate-rigor: '$1' is not a file"
      exit 1
    fi
    if check_one "$1"; then
      echo "✓ check-gate-rigor: $(basename "$1" .md) gate iterates as required"
      exit 0
    fi
    exit 1
    ;;
esac
