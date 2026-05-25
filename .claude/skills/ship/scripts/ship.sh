#!/usr/bin/env bash
# ship.sh — Push the current branch, open a PR, and squash-merge it.
#
# Operates on the git repo of the current working directory. Runs the
# *deterministic plumbing* of shipping; the human-judgment part (writing
# the commit) happens before this script is called (see SKILL.md). Assumes
# all work is already committed on a NON-default branch.
#
# Usage:
#   ship.sh [--base <branch>] [--title <t>] [--body <b>] [--no-merge] [--draft]
#
# Flags:
#   --base <branch>  PR base (default: repo's default branch)
#   --title <t>      PR title (default: derived from commits via --fill)
#   --body  <b>      PR body  (default: derived from commits via --fill)
#   --no-merge       Create/push the PR but do not merge (stop after creation)
#   --draft          Create the PR as a draft (implies --no-merge)
#
# Env:
#   SHIP_ADMIN=1     Allow `gh pr merge --admin` to bypass failing/pending
#                    required checks. OFF by default — bypassing checks is a
#                    deliberate, rarely-correct act. Never set this silently.
#
# Safety: never force-pushes, never uses --no-verify, refuses to run on the
# default branch, and never bypasses checks unless SHIP_ADMIN=1.
set -uo pipefail

die() { echo "ship: $*" >&2; exit 1; }
info() { echo "ship: $*" >&2; }

BASE="" TITLE="" BODY="" NO_MERGE=0 DRAFT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --base)  BASE="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --body)  BODY="$2"; shift 2 ;;
    --no-merge) NO_MERGE=1; shift ;;
    --draft) DRAFT=1; NO_MERGE=1; shift ;;
    *) die "unknown arg: $1" ;;
  esac
done

# ── Preflight ────────────────────────────────────────────────────────────
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git repo"
command -v gh >/dev/null 2>&1 || die "gh CLI not found"
gh auth status >/dev/null 2>&1 || die "gh not authenticated (run: gh auth login)"

BRANCH="$(git branch --show-current)"
[ -n "$BRANCH" ] || die "detached HEAD — checkout a branch first"

if [ -z "$BASE" ]; then
  BASE="$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name 2>/dev/null)"
  [ -n "$BASE" ] || BASE="main"
fi
[ "$BRANCH" != "$BASE" ] || die "on default branch '$BASE' — create a feature branch before shipping"

# Working tree must be clean: ship plumbs an already-committed branch.
if [ -n "$(git status --porcelain)" ]; then
  die "working tree not clean — commit (or stash) changes before shipping. Uncommitted:
$(git status --short)"
fi

# Must have something to ship relative to base.
git fetch origin "$BASE" >/dev/null 2>&1 || true
AHEAD="$(git rev-list --count "origin/$BASE..HEAD" 2>/dev/null || echo '?')"
if [ "$AHEAD" = "0" ]; then
  die "branch '$BRANCH' has no commits ahead of origin/$BASE — nothing to ship"
fi
info "branch '$BRANCH' is $AHEAD commit(s) ahead of origin/$BASE"

# ── Push ─────────────────────────────────────────────────────────────────
info "pushing $BRANCH → origin (no force)…"
git push -u origin "$BRANCH" 2>&1 | sed 's/^/ship:   /' >&2 \
  || die "git push failed (debug: network? remote rejection? do NOT --force)"

# ── PR (reuse if one already exists for this branch) ───────────────────────
PR_URL="$(gh pr view "$BRANCH" --json url --jq .url 2>/dev/null || true)"
if [ -n "$PR_URL" ]; then
  info "reusing existing PR: $PR_URL"
else
  CREATE_ARGS=(--base "$BASE" --head "$BRANCH")
  if [ -n "$TITLE" ]; then CREATE_ARGS+=(--title "$TITLE"); fi
  if [ -n "$BODY" ];  then CREATE_ARGS+=(--body "$BODY"); fi
  if [ -z "$TITLE" ] && [ -z "$BODY" ]; then CREATE_ARGS+=(--fill); fi
  if [ "$DRAFT" = "1" ]; then CREATE_ARGS+=(--draft); fi
  info "creating PR (base=$BASE)…"
  PR_URL="$(gh pr create "${CREATE_ARGS[@]}" 2>&1 | grep -Eo 'https://github.com/[^ ]+/pull/[0-9]+' | head -1)"
  [ -n "$PR_URL" ] || die "gh pr create failed"
  info "created PR: $PR_URL"
fi

if [ "$NO_MERGE" = "1" ]; then
  echo "$PR_URL"
  info "stopped before merge (--no-merge/--draft)."
  exit 0
fi

# ── Squash merge ───────────────────────────────────────────────────────────
MERGE_ARGS=(--squash --delete-branch)
[ "${SHIP_ADMIN:-0}" = "1" ] && MERGE_ARGS+=(--admin)

info "squash-merging…"
if gh pr merge "$PR_URL" "${MERGE_ARGS[@]}" 2>/tmp/ship-merge-err; then
  :
else
  cat /tmp/ship-merge-err >&2
  # Blocked by pending/required checks? Queue an auto-merge instead.
  if grep -qiE 'not mergeable|required|checks|protected|pending' /tmp/ship-merge-err; then
    info "immediate merge blocked (likely required checks) — enabling auto-merge…"
    gh pr merge "$PR_URL" --squash --delete-branch --auto 2>/tmp/ship-merge-err2 \
      || { cat /tmp/ship-merge-err2 >&2; info "auto-merge unavailable; PR left open for checks. Poll & merge later: gh pr merge $PR_URL --squash --delete-branch"; echo "$PR_URL"; exit 3; }
  else
    die "merge failed (see error above)"
  fi
fi

# ── Honest final state ─────────────────────────────────────────────────────
STATE="$(gh pr view "$PR_URL" --json state --jq .state 2>/dev/null || echo UNKNOWN)"
echo "$PR_URL"
case "$STATE" in
  MERGED) info "✅ MERGED (squash): $PR_URL" ;;
  OPEN)   info "⏳ auto-merge queued — will squash-merge when checks pass: $PR_URL" ;;
  *)      info "state=$STATE — verify manually: $PR_URL" ;;
esac
