# ADR 0010: Task File-Scope Enforcement

- Status: Accepted
- Date: 2026-11-18

## Context

Repository-aware task decomposition already assigns each task an exact relative `file_scope`, and the scope is included in worker prompts. Prompt instructions alone do not prevent a later aggregate patch builder from changing files that were not part of the accepted task graph.

## Decision

For `kaldrax orchestrate --workspace`, task file scopes are enforced as a host-side permission boundary:

1. Validate every task scope before task workers execute. Paths must be canonical, repository-relative, unique within each task, and must not target Git/runtime state, credentials, or excluded dependency/build paths.
2. Pass each focused task worker only its own exact `file_scope` as its allowed-path list.
3. Pass the union of all task scopes to the aggregate unified-patch builder. The builder is instructed that this is a hard allowlist, not a preference.
4. Parse every changed path from the diff, including file creation and deletion, and reject the candidate if any path is outside the union. This happens before repository impact analysis and sandbox execution.
5. Repeat the path check when staging the patch and immediately before applying it to the operator's checkout.
6. Include the allowed paths and actual changed paths in the repository report, reviewer request, and independent-evaluator evidence.

Path matching is exact and case-sensitive. Directory prefixes and wildcard patterns are not supported. A missing allowlist (`None`) preserves existing behavior for coordinator callers that do not use a task DAG; an explicitly empty allowlist authorizes no changed paths.

## Consequences

- The final repository diff cannot create, modify, or delete paths outside the task graph's declared scope.
- Scope violations fail before sandbox execution and are returned as builder feedback so a bounded repair cycle may correct them.
- Staging and application repeat the check rather than trusting an earlier validation result.
- The unified patch builder is authorized for the union of task scopes, while focused DAG workers receive their individual scopes. Per-task hunk attribution is not yet enforced because the current design produces one aggregate patch.
- The separate `team --workspace` workflow does not currently create a task DAG. It retains path-safety validation but does not yet enforce per-task allowlists.

## Verification

Regression coverage verifies rejection of out-of-scope modifications, new files, and deletions; validates that out-of-scope changes cannot reach staging or application; checks that task workers and the patch builder receive their respective scope data; and confirms that an out-of-scope candidate is rejected before sandbox, reviewer, or evaluator execution.
