# harness-starter

A **portable agent-harness template** you drop into any codebase.
It completes a high-level task through 5 stages: `clarify → context-gather → plan → implement → verify`.
It extracts the design patterns of `oh-my-claudecode` (artifact handoff, skip-flags, task-graph decomposition,
"LLM judgment + guardrails") in a stack-neutral, pure-prompt form.

## Design principles

1. **Handoff via artifact contracts** — stages are connected by files (`spec → context → plan → report`), not live context. So **any stage is swappable** between your own implementation and an external tool.
2. **Skip-flags** — if an artifact already exists, that stage is skipped (reuse outputs made externally or by a human).
3. **Two-axis decomposition** — separate logical decomposition (smallest verifiable unit) from physical decomposition (file/module boundaries for parallel safety). Dependencies only on real orderings.
4. **Parallel wavefront execution** — run nodes whose dependencies are cleared, wave by wave, in parallel. The orchestrator schedules without locks or scripts (same-wave nodes are file-scoped, so no conflicts).
5. **Judgment by LLM, safety by guardrails** — qualitative criteria like "actionable / verifiable" are LLM judgment in the prompts; node count, cyclic dependencies, and scope conflicts are narrowed by checklists.

## Layout

```
harness-starter/
  SKILL.md                  orchestrator (single entry point, 5 stages + wavefront scheduler)
  agents/
    clarify.md              request → spec.md          (fix verifiable acceptance criteria)
    context-gather.md       spec → context.md          (relevant files, conventions, integration; read-only)
    planner.md              spec+context → plan.md      (task-graph decomposition)
    implementer.md          one node → changes          (minimal change, immediate verify, fixed scope)
    verifier.md             changes → report.md         (evidence-based verdict on acceptance criteria)
  references/
    artifacts.md            artifact schemas = the seam contract that makes stages swappable
    decomposition.md        decomposition criteria (the planner's knowledge)
    conventions.md          ← slot the porting team fills with their project's rules
  prompt/
    install-harness-starter.md   prompt to port into an arbitrary codebase
```

Work products accumulate in the ported codebase under `.harness/{specs,context,plans,reports}/`.

## Usage

1. Use `prompt/install-harness-starter.md` to port `.claude/skills/harness-starter/` and `.claude/agents/harness-*` into the target repo.
2. Fill in `references/conventions.md` with that project's rules (the key step to fit general-purpose agents to the codebase).
3. Run with `/harness-starter <task description>`.

## Cherry-pick (partial use)

No need to use it whole. Since artifacts are contracts:
- Want **just the plan pattern**? Take only `agents/planner.md` + `references/decomposition.md`.
- Use this harness up to plan only, implement with another tool → hand over `plan.md`.
- Drop an externally produced `spec.md`/`plan.md` into `.harness/` and that stage is skipped automatically.

## Non-goals

- No heavy concurrency infrastructure like file locks or worktree isolation (file-scoped wavefronts suffice for parallelism).
- No forced model routing (`modelTier` is a suggestion; the mapping is up to the user/orchestrator).
