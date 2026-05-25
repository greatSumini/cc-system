# scripts/_gate-cache.sh — Source-only helper for goal gate memoization.
#
# Each goal's <n>-<name>.gates.sh declares its inputs and wraps its work:
#
#   source "$ROOT/scripts/_gate-cache.sh"
#
#   GATE_INPUTS=(
#     src
#     tests
#     package.json
#     goals/0-init.gates.sh
#     scripts/_gate-cache.sh
#   )
#
#   if gate_cache_hit "<goal-name>" "${GATE_INPUTS[@]}"; then
#     echo "[cache hit] goal <goal-name> inputs unchanged"
#     exit 0
#   fi
#
#   # ... run gates ...
#
#   if [ "$PASS" = true ]; then
#     gate_cache_save "<goal-name>" "${GATE_INPUTS[@]}"
#     exit 0
#   fi
#
# Cache key: sha256 fingerprint of every file resolved from GATE_INPUTS.
#
# Why content fingerprints instead of "HEAD + clean tree":
#   - Multiple agents may edit unrelated areas in parallel; a dirty tree
#     outside a goal's input surface no longer invalidates its cache.
#   - The cache survives commits that don't touch the goal's inputs.
#   - Uncommitted edits to in-scope files still invalidate (correctly).
#
# INPUTS entries may be:
#   - file paths        — contributes file content + path
#   - directories       — recursively hashed; node_modules/dist/.git/.state/
#                         .next/.turbo/coverage/.astro/target/__pycache__/
#                         .venv are pruned
#   - glob patterns     — expanded; each match contributes as above
#   - absent paths      — contribute a stable "absent" sentinel, so adding
#                         or removing a referenced file invalidates
#
# Manual override:
#   rm -rf .state/gate-cache              # bust all caches
#   rm    .state/gate-cache/<goal-name>   # bust one
#
# Env override:
#   GATES_NO_CACHE=1                      # bypass cache for this invocation

_gate_cache_dir() {
  local root
  root="${GATE_CACHE_ROOT:-${ROOT:-$(pwd)}}"
  echo "$root/.state/gate-cache"
}

# Pick a portable sha256 command once. macOS lacks `sha256sum` by default;
# `shasum -a 256` exists on both macOS and Linux. We use this name as a
# literal string with xargs below, so it must resolve to an external
# program — not a shell function.
if command -v shasum >/dev/null 2>&1; then
  _GATE_CACHE_SHA_CMD="shasum -a 256"
elif command -v sha256sum >/dev/null 2>&1; then
  _GATE_CACHE_SHA_CMD="sha256sum"
else
  _GATE_CACHE_SHA_CMD=""
fi

_gate_cache_sha256() {
  [ -n "$_GATE_CACHE_SHA_CMD" ] || return 1
  # shellcheck disable=SC2086  # intentional word splitting on the cmd
  $_GATE_CACHE_SHA_CMD "$@"
}

_gate_cache_is_glob() {
  case "$1" in
    *\**|*\?*|*\[*) return 0 ;;
    *) return 1 ;;
  esac
}

# Compute a single sha256 fingerprint over the given INPUTS list.
# Emits the fingerprint hex on stdout; empty string on hard error.
_gate_cache_fingerprint() {
  local manifest
  manifest=$(mktemp 2>/dev/null) || return 1

  local pattern p
  for pattern in "$@"; do
    local expanded=()
    if _gate_cache_is_glob "$pattern"; then
      while IFS= read -r m; do
        [ -n "$m" ] && expanded+=("$m")
      done < <(compgen -G "$pattern" 2>/dev/null || true)
      if [ "${#expanded[@]}" -eq 0 ]; then
        printf 'absent\t%s\t-\n' "$pattern" >> "$manifest"
        continue
      fi
    else
      expanded=("$pattern")
    fi

    for p in "${expanded[@]}"; do
      if [ -f "$p" ]; then
        local h
        h=$(_gate_cache_sha256 "$p" 2>/dev/null | awk '{print $1}')
        if [ -n "$h" ]; then
          printf 'file\t%s\t%s\n' "$p" "$h" >> "$manifest"
        else
          printf 'unreadable\t%s\t-\n' "$p" >> "$manifest"
        fi
      elif [ -d "$p" ]; then
        local listing
        listing=$(mktemp 2>/dev/null) || { rm -f "$manifest"; return 1; }
        find "$p" \
              -type d \( \
                  -name node_modules -o \
                  -name dist -o \
                  -name .git -o \
                  -name .state -o \
                  -name .next -o \
                  -name .turbo -o \
                  -name coverage -o \
                  -name .astro -o \
                  -name target -o \
                  -name __pycache__ -o \
                  -name .venv \
              \) -prune -o \
              -type f -print0 2>/dev/null \
          | LC_ALL=C sort -z \
          | xargs -0 $_GATE_CACHE_SHA_CMD -- 2>/dev/null \
          > "$listing"
        local dh
        dh=$(_gate_cache_sha256 < "$listing" | awk '{print $1}')
        rm -f "$listing"
        printf 'dir\t%s\t%s\n' "$p" "$dh" >> "$manifest"
      else
        printf 'absent\t%s\t-\n' "$p" >> "$manifest"
      fi
    done
  done

  local final
  final=$(LC_ALL=C sort "$manifest" | _gate_cache_sha256 | awk '{print $1}')
  rm -f "$manifest"
  printf '%s' "$final"
}

gate_cache_fingerprint() {
  local goal_name="$1"
  local cache_file
  cache_file="$(_gate_cache_dir)/$goal_name"
  [ -f "$cache_file" ] && cat "$cache_file"
}

gate_cache_hit() {
  local goal_name="$1"
  shift
  [ "${GATES_NO_CACHE:-}" = "1" ] && return 1

  local cache_file
  cache_file="$(_gate_cache_dir)/$goal_name"
  [ -f "$cache_file" ] || return 1

  local cached current
  cached=$(cat "$cache_file") || return 1
  [ -n "$cached" ] || return 1
  current=$(_gate_cache_fingerprint "$@")
  [ -n "$current" ] || return 1
  [ "$cached" = "$current" ]
}

gate_cache_save() {
  local goal_name="$1"
  shift
  local dir current
  dir="$(_gate_cache_dir)"
  current=$(_gate_cache_fingerprint "$@")
  [ -n "$current" ] || return 0
  mkdir -p "$dir"
  printf '%s\n' "$current" > "$dir/$goal_name"
}
