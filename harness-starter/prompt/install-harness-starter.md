# Install: harness-starter

Port the harness-starter kit into the **current codebase**. Follow the steps below exactly.

## Source

The kit lives at `cc-system/harness-starter/`. It contains:
- `SKILL.md` — the orchestrator skill
- `agents/*.md` — 5 stage subagents (`harness-clarify`, `harness-context`, `harness-planner`, `harness-implementer`, `harness-verifier`)
- `references/*.md` — `artifacts.md`, `decomposition.md`, `conventions.md`
- `README.md`

## Steps

1. **Place the skill.** Copy the kit into `.claude/skills/harness-starter/` of the target repo
   (so `SKILL.md`, `references/`, and `README.md` sit under `.claude/skills/harness-starter/`).
   The skill becomes invocable as `/harness-starter`.

2. **Place the agents.** Copy each file in `agents/` into `.claude/agents/` of the target repo
   (keep the `harness-` name prefix to avoid collisions). The five agents become available as subagent types.

3. **Wire the reference paths.** The agents and SKILL reference `references/artifacts.md`,
   `references/decomposition.md`, and `references/conventions.md`. Ensure those resolve from the installed
   skill directory (`.claude/skills/harness-starter/references/`). If your setup needs absolute paths,
   adjust the references accordingly.

4. **Fill in conventions.** Open `.claude/skills/harness-starter/references/conventions.md` and complete it
   with this project's stack, style, verification commands, and forbidden/caveat items. This is the step
   that adapts the general-purpose agents to this codebase — do not skip it.

5. **Create the state directory.** Add `.harness/{specs,context,plans,reports}/` (the orchestrator also
   creates it on first run). Decide whether to commit `.harness/` or add it to `.gitignore`.

6. **Smoke test.** Run `/harness-starter <a small real task>` and confirm:
   - `spec.md` is produced (or skipped if present),
   - `context.md` reflects real files,
   - `plan.md` has 3–6 nodes with per-node acceptanceCriteria and a sane blockedBy graph,
   - the implement wave runs and `report.md` gives an evidence-based verdict.

## Notes

- **Pure prompt, stack-neutral.** No scripts or runtime dependencies are required.
- **Cherry-pick is fine.** To adopt only the planning pattern, install just `agents/planner.md` and
  `references/decomposition.md` and call the planner directly.
- **Skip-flags interoperate.** Externally produced `spec.md`/`plan.md` dropped into `.harness/` cause the
  corresponding stages to be skipped — use this to combine harness-starter with other tools.
