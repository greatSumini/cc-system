#!/usr/bin/env bash
# goals/0-example.gates.sh — Worked example. DELETE once you author your
# own goal 0. Demonstrates three things every real gate should have:
#   1. the gate cache (source _gate-cache.sh, declare GATE_INPUTS),
#   2. enumeration from a source of truth (universal claim → for-loop),
#   3. the rigor self-check.

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck source=../scripts/_gate-cache.sh
source "$ROOT/scripts/_gate-cache.sh"

GATE_INPUTS=(
  scripts
  goals/0-example.gates.sh
  goals/0-example.md
  scripts/_gate-cache.sh
)

if gate_cache_hit "0-example" "${GATE_INPUTS[@]}"; then
  echo "[cache hit] goal 0-example inputs unchanged"
  exit 0
fi

PASS=true

# 0.1 — Universal claim: "every runnable script under scripts/ begins with
# a shebang." The claim is universal, so the gate ENUMERATES the source of
# truth (the filesystem) instead of sampling one file.
echo "[0.1] every runnable scripts/*.sh starts with a #! shebang"
MISSING=()
while IFS= read -r f; do
  first=$(head -n1 "$f" 2>/dev/null || true)
  case "$first" in
    '#!'*) : ;;
    *) MISSING+=("$f") ;;
  esac
done < <(find scripts -maxdepth 1 -name '*.sh' ! -name '_*' -type f | sort)
if [ "${#MISSING[@]}" -eq 0 ]; then
  echo "    ✓ pass"
else
  echo "    ✗ fail — missing shebang:"
  printf '        %s\n' "${MISSING[@]}"
  PASS=false
fi

# 0.2 — Gate rigor self-check. Every goal's gate carries this so a
# universal claim in the .md can never ship without an enumerating gate.
echo "[0.2] gate rigor"
if bash "$ROOT/scripts/check-gate-rigor.sh" "$ROOT/goals/0-example.md" >/dev/null 2>&1; then
  echo "    ✓ pass"
else
  echo "    ✗ fail"
  bash "$ROOT/scripts/check-gate-rigor.sh" "$ROOT/goals/0-example.md" | sed 's/^/      /'
  PASS=false
fi

if [ "$PASS" = true ]; then
  gate_cache_save "0-example" "${GATE_INPUTS[@]}"
  exit 0
fi
exit 1
