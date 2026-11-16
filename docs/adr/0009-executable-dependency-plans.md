# ADR 0009: Repository-Aware Executable Dependency Plans

- Status: Accepted
- Date: 2026-11-16

## Context

KALDRAX already validates task dependency graphs and schedules prerequisite-ready tasks concurrently. However, the first decomposition pass previously received only the objective and acceptance criteria. Repository structure was analyzed later by the patch coordinator, after the task graph had already been selected and executed. That timing prevented the planner from grounding task boundaries, file paths, and prerequisites in the actual project.

## Decision

When a workspace is supplied, run the read-only repository analyzer before task decomposition and include its bounded structure map in the planner input. The map includes source paths, local dependency edges, exports, entry points, detected languages/frameworks, and test candidates.

Each repository-backed task must include:
- a phase label (for example configuration, security, data, API, integration, or tests);
- an explicit relative `file_scope` of files to create or modify;
- explicit `depends_on` task identifiers;
- verifiable acceptance criteria.

Task nodes reject absolute paths, traversal, Git/KALDRAX runtime paths, and environment-secret paths. New relative paths may be proposed when the repository does not yet contain a required module. Repository context is untrusted metadata, not instructions.

The task graph exposes deterministic topological execution waves. Tasks in one wave have satisfied prerequisites and may execute in parallel; downstream work remains blocked until their own dependencies succeed. The same phase and file-scope contract is passed to workers, repository patch planning, and review. The serialized execution order and waves are included in the run artifact and graph fingerprint.

When no workspace is supplied, KALDRAX retains generic task decomposition without requiring file scopes.

## Consequences

- Planning becomes repository-aware before implementation starts.
- File scopes and dependency edges are inspectable and checkpointed as part of the graph.
- Independent work remains parallelizable; dependencies determine order rather than artificial phase sequencing.
- Repository-backed workers receive local file/dependency/test context plus outputs from completed prerequisites.
- The planner's interpretation of dependency edges and proposed new paths still requires reviewer and sandbox verification. The analyzer's non-Python import extraction is heuristic and its graph is not a complete language-semantic model.
- Repository analysis failure prevents workspace-backed decomposition rather than silently reverting to an ungrounded plan.

## Verification

Regression coverage builds a JWT-authentication plan spanning configuration, data, security, API, and tests; checks topological waves and file-scope propagation; rejects unsafe paths; and exercises workspace-backed orchestration. The CI workflow runs the full pytest suite and source compilation on supported Python versions.
