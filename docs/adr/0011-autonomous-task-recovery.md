# ADR 0011: Autonomous Task Recovery and Replanning

- Status: Accepted
- Date: 2026-11-18

## Context

The task-graph scheduler already supported bounded transient retries, dependency blocking, checkpoint resume, and an escalation callback. Permanent failures remained terminal: the callback could suggest a recovery action, but the accepted graph was not revised and successful outputs could not be carried into a new dependency plan.

## Decision

Add a bounded repair loop around the DAG scheduler.

1. After normal retries, collect every failed and blocked node with its task definition, attempts, errors, and prerequisite states.
2. Ask the planner for a structured diagnosis per affected node. Each diagnosis includes a category, evidence-grounded cause, exact evidence reference, retryability, operator-input requirement, and repair instruction. Validate the evidence against the task error or a real failed/blocked dependency state.
3. Ask the planner to produce a complete replacement graph and a `retired_task_ids` list. Validate it through the normal `TaskGraph` and `TaskNode` contracts, including unique IDs, dependencies, acyclicity, path rules, and repository file-scope requirements.
4. Require every previously successful task to remain present with exactly the same ID, description, dependencies, acceptance criteria, phase, and file scope. Preserve its output and cumulative attempt count. Never execute it again.
5. Reset failed/blocked tasks that remain in the replacement graph to pending, carry their cumulative attempts into the report, and allow new tasks to start with zero prior attempts. Any omitted failed/blocked task must be explicitly listed as retired.
6. Resume the scheduler with the revised graph. Recalculate topological execution waves from its new dependency edges.
7. Keep all aggregate acceptance gates unchanged: the final reviewer and distinct evidence-backed evaluator are mandatory; repository mode additionally keeps scope, sandbox, and explicit apply gates.

## Boundedness and persistence

- `--max-replans` defaults to 2 and accepts only 0–3.
- The count is cumulative across restarts, not a per-invocation reset.
- Each task still uses the configured per-round retry limit (1–5 attempts).
- Operator-input-required diagnoses stop automatic repair.
- Checkpoints persist the active graph revision, request fingerprint, repository binding, node states/outputs, cumulative attempt counts, and repair history.
- `--fresh` is the explicit escape hatch to discard the prior recovery state and decompose again.

## Consequences

- A failed plan can be corrected without repeating completed work.
- Dependency edges for unfinished work can be recalculated by the repair planner and are revalidated before scheduling.
- Invalid diagnoses, untraceable evidence, malformed repair graphs, and checkpoint mismatches fail closed.
- A bounded repair attempt does not guarantee correctness. Repaired tasks must execute, and the unchanged independent reviewer/evaluator gates remain authoritative.
- The aggregate patch builder still receives the union of all scopes in the final graph; per-task ownership remains enforced at task-worker input and at the final patch boundary.

## Verification

Regression coverage verifies exact diagnosis coverage and evidence validation, dependency rewiring, immutable successful tasks, rejection of changed completed work, checkpoint persistence of revised graphs, cumulative attempts, and an end-to-end CLI recovery in which a successful task runs once while a failed task is replanned and retried. Automated execution and hosted CI status must be recorded separately from source-level implementation.
