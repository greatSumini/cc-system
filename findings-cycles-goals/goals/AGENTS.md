# `goals/` — Working Protocol for the mission stack

`goals/` is the **mission stack**: the versioned, machine-verified
definition of "what done means." The lowest-numbered goal whose gates fail
is the **active goal** — the single routing signal every harness tool
(`diagnose.sh`, `next-task.sh`, `active-check.sh`) reads.

Read `docs/goal-design.md` (design) and `guidelines/goal-iteration.md`
(per-iteration operating manual) before authoring or editing a goal.

---

## The three-file set

Each goal is **three files** sharing a `<n>-<name>` stem:

| File                      | Role                                                                                       |
| ------------------------- | ------------------------------------------------------------------------------------------ |
| `<n>-<name>.md`           | Mission. States the "done" conditions in prose (use universal claims).                     |
| `<n>-<name>.gates.sh`     | Machine verification. **If the `.md` says "every X", the gate MUST enumerate X** from a source of truth. |
| `<n>-<name>.next-task.sh` | Advisory hint. Reads workflow state (file existence, gate pass/fail) and prints the next action. Never gates. |

`_meta` is a special set (no number) for cross-cutting invariants (lint /
typecheck / test / build); `completion-check.sh` launches it first.

**Discovery rule.** The harness treats a markdown file in `goals/` as a
goal only when its name starts with a digit (`<n>-<name>.md`) or is exactly
`_meta.md`. Anything else here — this `AGENTS.md`, a `README.md`, scratch
notes — is ignored by `completion-check.sh` / `check-gate-rigor.sh` /
`diagnose.sh`, so it never shows up as a "missing gate" failure.

---

## `.md` conventions

- Put a one-line pointer right under the title so an agent that opens the
  goal first can reach the operating manual in one hop:

  ```
  > 이 goal을 active로 잡은 에이전트는 먼저 `guidelines/goal-iteration.md`를
  > 읽어 iteration 프로토콜을 확인할 것.
  ```

- Sections that work well: `## Mission`, `## Completion Conditions`,
  `## Sources Of Truth` (the enumeration commands), `## Verification`.
- Universal claims ("every / all / each <noun>") trigger the rigor check.
  Only claim universality when you mean it — and back it with an
  enumerating gate.

---

## Adding a goal

```
goals/<n>-<name>.md            # mission
goals/<n>-<name>.gates.sh      # machine verification (chmod +x)
goals/<n>-<name>.next-task.sh  # next-action hint (chmod +x)
```

The next `completion-check.sh` run picks the lowest failing goal as active.
Before writing it, run the **self-audit** in `docs/goal-design.md §"Adding
a goal"`: does this goal merely retarget a prior gate's path (case a),
require loosening a prior gate's logic (case b), or supersede a prior gate
(case c)? Prior gates are immutable unless one of those is explicitly
declared.

---

## Designing gates (summary — full rules in goal-design.md §1, §1.5)

- **Universal claim ⇒ enumerate from a source of truth** (filesystem,
  schema, route table). Never type the entity names into the gate.
- **Gates ≠ convention police.** Don't grep for what a test, typecheck, or
  coverage threshold catches more precisely. A gate legitimately owns only:
  the rigor mechanism, negative-universal greps ("X appears nowhere"), and
  structural anchors (a file's existence that routes a later goal).
- Skeptical heuristic: *"if this invariant broke, which test would go
  red?"* If one would, the test owns it — drop it from the gate.

Every gate should source `scripts/_gate-cache.sh`, declare `GATE_INPUTS`,
and end with a `check-gate-rigor.sh` self-check on its own `.md`.
