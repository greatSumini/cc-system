# Goal _meta — Cross-cutting invariants

> 이 goal을 active로 잡은 에이전트는 먼저 `guidelines/goal-iteration.md`를
> 읽어 iteration 프로토콜을 확인할 것.

This goal is a **meta gate suite**, separate from the numeric goal stack.
It collects the universal claims that apply to *every* goal — lint,
typecheck, tests + coverage, build — in one place, so each numeric goal's
gate can focus only on its own goal-specific invariant.

## Why this exists

The same commands (`test`, lint, typecheck, build) otherwise get scattered
across goals 0/1/2/… and the CI workflow, so a single completion-check run
executes identical work several times. These are not "one goal's universal
claim" — they are **cross-cutting** claims that hold for all goals, so they
belong at the meta level, enforced once.

`completion-check.sh` recognizes `goals/_meta.md` and launches it first.
If it fails, `.state/active-goal` records `_meta` and `next-task.sh`
dispatches to `goals/_meta.next-task.sh`.

## The Goal (adapt to your stack)

The following hold for the whole repo. Edit `META_CHECKS` in
`goals/_meta.gates.sh` to match your toolchain:

1. **Every** source file typechecks.
2. **Every** source/test file passes the linter with zero warnings.
3. **Every** test passes and coverage thresholds are met.
4. **Every** buildable package builds.

Each condition must be enumerated from a source of truth (the tsconfig /
eslint config / test config / the set of packages), not sampled. That is
why `_meta.gates.sh` iterates over the configured checks with a `for` loop
— a universal claim demands a universal gate (`check-gate-rigor.sh`).

## Env flags

| Env                | Effect                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------- |
| `GATES_SKIP_DEEP=1`| Skip the checks whose label matches the deep pattern (test/build/e2e/coverage). Fast inner-loop only. |
| `GATES_SKIP_META=1`| `completion-check.sh` excludes `_meta` entirely. Use only where CI already runs those steps directly. |

`SKIP_DEEP` uses a separate `_meta-shallow` cache key, so repeated shallow
runs can cache-hit without ever claiming the deep checks have run. A full
run saves both keys, because it proves every shallow claim too.

## Why the `_` prefix

`_` (0x5F) sorts after the digits, but `completion-check.sh` special-cases
`_meta.md` and launches it first regardless. The prefix keeps it visually
distinct from the numeric mission stack.
