# Decomposition Criteria

The judgment criteria the planner agent follows when splitting a high-level task into subtasks (nodes).
Extracted from the planner/team decomposition patterns of `oh-my-claudecode`. Key insight: **decomposition has two axes, and we never conflate them.**

- **Logical decomposition** = "how finely to split" → criterion is *the smallest verifiable unit*
- **Physical decomposition** = "where to cut so parallel is safe" → criterion is *file/module boundaries*

Order: **split logically first → align only the nodes you'll parallelize to physical boundaries → add dependency edges only where a real ordering exists.**

---

## 0. Classify intent first (it sets the focus of decomposition)

| Intent | Focus | Decomposition tendency |
|---|---|---|
| `trivial` | quick fix | usually 1 node. Do not split |
| `refactor` | safety | behavior-preserving units; testable boundaries |
| `build` (greenfield) | discovery | unknowns first: explore → skeleton → flesh out |
| `mid` (mid-sized) | boundary setting | clean split along module boundaries |

The classification sets *what to split by*. Decide it before decomposing.

## 1. Logical granularity: 3–6 "actionable" steps

- Default **3–6 nodes**. `30 micro-steps` ✗, two vague directives like `"implement the feature"` ✗.
- Do not redesign architecture beyond what the task requires.
- If a piece is large enough that it would need finer splitting → keep it as one node and let the implementer handle it with its own todo (a second-pass plan only when truly needed).

## 2. Definition of "actionable" = smallest verifiable unit

> A node's boundary is **"the smallest unit that has acceptanceCriteria one implementer can verify as done by itself."**

- If you can't write a verification criterion → the node is too vague. Make it concrete or split it.
- If the criterion is self-evident and simple → stop splitting. **Stop decomposing once the plan is actionable.**

This judgment is **LLM (planner) reasoning, not a deterministic rule**. The rules are guardrails that *narrow* the judgment, not a replacement for it.

## 3. Physical boundary: parallel nodes are file/module-scoped

- Nodes to run in parallel in the same wave must be limited to **`scope: file:<path>` or `module:<name>`** → prevents concurrent write conflicts.
- If two logical steps **modify the same file**: either (a) merge into one node, or (b) serialize with `blockedBy`. Never let two nodes write the same file in parallel.
- **Crosscutting / shared files are serialization points.** Files that many nodes must touch — barrel/index (`index.ts`), route registries (`routes.ts`), `package.json`, dependency-injection containers, schema/migration indexes — leak the "file-scoped = independent" assumption. Handle them one of two ways:
  - **(a) Wire-up node**: extract the shared-file edits into a single dedicated node, and make it `blockedBy` the nodes that produce what it wires up (it runs last, alone).
  - **(b) Serialize**: if the edits can't be separated, chain the touching nodes with `blockedBy` so they never run in the same wave.
  Either way: **no two nodes write a shared file in parallel.**
- Note: file-scoping prevents *write* conflicts, not *semantic* ones (node A renames a symbol node B uses). If a node's change alters an interface another node depends on, add a `blockedBy` edge.

## 4. Dependency edges (blockedBy): real ordering only

- Draw `blockedBy` **only when a genuine ordering exists**. Canonical example: *shared type/schema definition → code that consumes it*.
- Unnecessary serialization kills parallelism. If independent, leave it edge-free = parallel in the same wave.
- **No cycles.** The blockedBy graph must be a DAG.

## 5. Model tier suggestion (modelTier)

Tag each node with a suggested tier (orchestrator/user maps to an actual model):

| tier | suited for |
|---|---|
| `low` | formatting, simple substitutions, mechanical edits |
| `medium` | general implementation, multi-file changes |
| `high` | architectural judgment, subtle logic, high cross-impact changes |

## Decomposition checklist (planner runs it every time)

```
1. Did you classify intent? (trivial/refactor/build/mid)
2. Are there 3–6 logical nodes? (not over-decomposed / not vague)
3. Does each node have a verifiable acceptanceCriteria?
4. Are parallel nodes file/module-scoped so there are no write conflicts?
5. Do no two parallel nodes touch the same file?
5b. Are crosscutting/shared files (index, routes, package.json, schema, DI) isolated into a wire-up node or serialized? (no shared-file parallel writes)
5c. Do no two parallel nodes have a semantic dependency (one alters an interface the other uses)? If they do, add blockedBy.
6. Is blockedBy applied only to real orderings? (no unnecessary serialization)
7. Is the blockedBy graph free of cycles? (DAG)
8. Is the plan actionable? → if yes, stop.
```
