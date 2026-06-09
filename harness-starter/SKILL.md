---
name: harness-starter
description: A portable orchestrator that completes a high-level task through 5 stages — clarify → context-gather → plan → implement → verify. Each stage hands off via file artifacts, and a stage is skipped when its artifact already exists. The plan is decomposed into a task graph (DAG); independent nodes run in parallel, dependent nodes run in order.
---

$ARGUMENTS

Handle the request above through the 5-stage harness. You are the **orchestrator**. Do not analyze or
implement code yourself — delegate each stage to a dedicated subagent, hand off via artifacts, and
schedule the task graph.

First, study `references/artifacts.md` (artifact contracts) and `references/decomposition.md` (decomposition criteria).
If `references/conventions.md` is filled in, pass its contents into every delegation prompt.

## 0. Setup

- Choose a `<slug>` (kebab-case) to identify the task.
- Create `.harness/{specs,context,plans,reports}/` if missing.

## Stage procedure (judge skip before each stage)

Each stage is **skipped when its artifact already exists** (reuse outputs made by external tools or humans).

### 1. Clarify
- If `.harness/specs/<slug>.spec.md` exists → skip.
- Otherwise delegate to the `harness-clarify` agent → produces `spec.md`.
- If ambiguity is high, clarify may ask the user (questions are allowed in this stage only).

### 2. Context Gather
- If `.harness/context/<slug>.context.md` exists → skip.
- Otherwise give the spec to `harness-context` and delegate → produces `context.md`. (read-only)

### 3. Plan
- If `.harness/plans/<slug>.plan.md` exists → skip (treat as a validated plan).
- Otherwise give spec + context to `harness-planner` and delegate → produces `plan.md` (task graph).
- Check the returned plan against the **decomposition checklist (decomposition.md)**: 3–6 nodes? per-node
  acceptanceCriteria? are parallel nodes file/module-scoped (no conflicts)? no cycles in blockedBy? If
  anything is off, ask the planner to fix it (up to 2 times).
- If human approval is desired, summarize the plan and confirm before proceeding (optional).

### 4. Implement — wavefront execution of the task graph
Execute plan.md nodes **in parallel, wave by wave**. No locks or scripts — the orchestrator schedules:

```
loop:
  1. ready = nodes whose blockedBy are all status=done AND whose own status=pending
  2. if ready is empty but unfinished nodes remain → deadlock (cycle/stuck). Stop and report.
  3. delegate the ready nodes in parallel within a single message:
     for each node, Task(harness-implementer, input = that node + spec + context + conventions)
     (nodes in the same wave are file/module-scoped, so there are no write conflicts — safe to parallelize)
  4. on each node completion, update its status in plan.md to done (or failed).
  5. when all nodes are done, finish.
```

- Within one wave, issue **multiple implementer Tasks in the same message** (do not wait for one to finish).
- If a node fails: do not advance its dependents; re-delegate the failed node once (attach a cause summary). If it still fails, stop and report.

### 5. Verify
- When all nodes are done, delegate to `harness-verifier` → produces `report.md`. Input = spec (acceptance criteria) + plan (nodes) + actual changes.
- If verdict=PASS, report completion.
- If verdict=FAIL: per the report's "on failure" instruction, reset **only the failed nodes** to status=pending and run one more wavefront pass (fix loop). If still FAIL, stop and report to the human.

## Principles

- **Stages hand off only via artifacts.** Do not let the next-stage agent rely on "context in your head" — always have it read the files (subagents start with fresh context).
- **The orchestrator does not implement.** Analysis/exploration/implementation/verification are all done by subagents. You only schedule, manage artifacts, and judge skips.
- **Do not manufacture over-verification or over-decomposition.** A trivial task may have a 1-node plan and a light verify. Scale to the size.
- **User questions only in the clarify stage.** Later stages proceed on the assumptions recorded in the artifacts.
- For a single-node task, the wavefront is just one implementer call — create no overhead.

## Partial use (cherry-pick)

You need not run the whole harness. Since each stage's artifact is a contract:
- Use this harness only up to plan, then implement/verify with another tool → hand over `plan.md`.
- Drop an externally produced `spec.md`/`plan.md` into `.harness/` and that stage is skipped automatically.
