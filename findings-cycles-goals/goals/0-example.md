# Goal 0 — (example) runnable scripts carry a shebang

> 이 goal을 active로 잡은 에이전트는 먼저 `guidelines/goal-iteration.md`를
> 읽어 iteration 프로토콜을 확인할 것.

> **This is a throwaway teaching example.** It demonstrates the three-file
> goal shape and the universal-claim ↔ enumeration rule, and it passes out
> of the box so you can watch the chain turn green. Once you understand the
> pattern, author your own `goals/0-<name>.{md,gates.sh,next-task.sh}` from
> your spec and **delete this triplet**.

## Mission

Every shell script under `scripts/` that is meant to be run directly
(i.e. not a sourced helper prefixed with `_`) begins with a `#!` shebang.

## Completion Conditions

1. Every runnable `scripts/*.sh` starts with a `#!` line.
2. This goal's gate passes `scripts/check-gate-rigor.sh`: the universal
   claim above forces the gate to **enumerate** the filesystem rather than
   sample a single file.

## Sources Of Truth

- `find scripts -maxdepth 1 -name '*.sh' ! -name '_*'`

## Verification

```
bash goals/0-example.gates.sh
bash scripts/completion-check.sh
```
