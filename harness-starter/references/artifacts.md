# Artifact Contracts

The stages of this harness hand off **through file artifacts, not live conversation context**.
Each stage *reads one input artifact → writes one output artifact*. That is what lets any stage be
swapped between your own implementation and an external tool (OMC, etc.). This file is the **type contract**
that makes the swap possible.

## State directory

Relative to the root of the codebase you ported into:

```
.harness/
  specs/<slug>.spec.md          # output of clarify
  context/<slug>.context.md     # output of context-gather
  plans/<slug>.plan.md          # output of planner (task graph + execution state)
  reports/<slug>.report.md      # output of verifier
```

`<slug>` = a kebab-case identifier for the task (e.g. `add-oauth-login`). All four artifacts of one task share the same slug.

> Put `.harness/` in `.gitignore` (work products) or commit it for review traceability — your team's choice.

## Skip rules (the OMC skip-flag pattern)

The orchestrator **skips a stage when its artifact already exists.**

| If present | Skip stage |
|---|---|
| `<slug>.spec.md` | clarify |
| `<slug>.context.md` | context-gather |
| `<slug>.plan.md` | clarify + context-gather + plan (it is a validated plan) |

→ Drop an externally produced spec/plan into the path/format below and that stage is skipped automatically.

---

## 1. spec.md — output of clarify

```markdown
# Spec: <task title>
slug: <slug>

## Goal
<one paragraph: what, and why>

## In Scope
- <what is included>

## Out of Scope
- <what is explicitly NOT done>

## Acceptance Criteria
- [ ] <verifiable completion condition 1>
- [ ] <verifiable completion condition 2>

## Open Assumptions
- <premises we proceed on without confirmation. "None" if none>
```

Rule: each acceptance criterion must be **decidable true/false by test or observation**. "It works well" ✗ / "POST /login returns 200 with a JWT" ✓.

## 2. context.md — output of context-gather

```markdown
# Context: <slug>

## Relevant Files
| Path | Role | Relation to this task |
|---|---|---|
| src/auth/session.ts | session management | add token verification here |

## Conventions observed
- <patterns this codebase actually uses; augments references/conventions.md>

## Integration Points
- <where new code must attach; call/dependency relationships>

## Key Snippets
```<lang>
// path:line — why this matters
```

## Gotchas
- <what breaks if touched, hidden dependencies>
```

Rule: **read-only.** Do not modify code. List only files actually read, never guesses.

## 3. plan.md — output of planner (task graph + execution state)

The result of decomposition per `references/decomposition.md`. It is both the **task graph (DAG)** and the **execution tracking board**.

```markdown
# Plan: <slug>
intent: trivial | refactor | build | mid    # intent classification
source_spec: .harness/specs/<slug>.spec.md
source_context: .harness/context/<slug>.context.md

## Task Graph

```yaml
nodes:
  - id: T1
    subject: <concise one-line title>
    description: |
      <enough detail that an executor can work without further guessing>
    scope: file:src/auth/session.ts        # file:<path> or module:<name>
    blockedBy: []                           # ids of prerequisite nodes; [] if none
    acceptanceCriteria:
      - <criterion an executor can verify this node is done>
    modelTier: low | medium | high          # suggested model tier
    status: pending                         # pending|in_progress|done|failed
  - id: T2
    subject: ...
    blockedBy: [T1]
    ...
```

## Execution Notes
- <wavefront progress, blocked nodes, replan reasons — updated by the orchestrator>
```

### Node schema rules (the core of the contract)
- **`scope` is file/module-level** so nodes in the same wave can run in parallel without write conflicts. If two nodes write the same file, merge them into one node or serialize with blockedBy.
- **`blockedBy` only where a real ordering exists** (e.g. shared type definition → its consumers). No unnecessary serialization = maximize parallelism.
- **`acceptanceCriteria` is required per node** → this is the definition of "actionable": the smallest unit one implementer can verify as done by itself.
- Node count **3–6 recommended** per intent (no over-decomposition / no vagueness). If more is needed, split into a second-pass plan.
- **No cyclic dependencies**: the blockedBy graph must be a DAG (checked by planner and orchestrator).

## 4. report.md — output of verifier

```markdown
# Verify Report: <slug>

## Acceptance Criteria Verdict (per spec.md)
| Criterion | Result | Evidence |
|---|---|---|
| POST /login returns 200 + JWT | PASS | actual call log / test name |
| ... | FAIL | what diverged |

## Per-Node Verdict (per plan.md)
| Node | Result | Note |
|---|---|---|
| T1 | PASS | |

## Summary
verdict: PASS | FAIL
On failure: <which node to fix and how — used as input to re-implement>
```

Rule: verdicts must rest on **actual execution / test / observation evidence**. No "appears to pass".
