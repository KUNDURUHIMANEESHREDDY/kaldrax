# ADR 0007: Repository-Aware Engineering Loop

- Status: Accepted
- Date: 2026-11-16

## Context

The bounded planner/builder/reviewer team originally produced candidate prose, while the Docker sandbox executed one Python file. That was not sufficient to validate a real software change end to end. Repository writes also need explicit authorization, protection against stale checkouts, and an execution boundary that never mounts the operator's working tree.

## Decision

Add a separate repository-aware coordinator behind the existing team command's optional workspace mode.

- Require a clean Git repository root and capture its HEAD before provider calls.
- Provide a bounded, prioritized source/test snapshot with common secrets and runtime state excluded.
- Require the builder to return a validated unified Git diff.
- Reject binary diffs, renames, submodules, mode changes, unsafe paths, Git metadata, runtime state, and credential files.
- Stage the patch in a temporary Git repository and run only allowlisted Python verification modules in a second disposable Docker copy.
- Disable Docker networking and apply unprivileged execution, CPU, memory, PID, timeout, and output limits.
- Require successful verification, non-zero test discovery for unittest/pytest, reviewer approval, and independent evaluator acceptance.
- Default to dry run. Only explicit apply writes to the actual checkout, after rechecking clean status and the original HEAD. Do not automatically commit or push.
- Allow an operator-selected, pre-pulled image through KALDRAX_SANDBOX_IMAGE.

## Consequences

- The existing prose-only team command remains compatible.
- Repository changes have inspectable diffs, test output, reviewer findings, evaluator results, and a structured run report.
- The bounded snapshot can omit files; the agent must not infer their contents. Projects exceeding the snapshot limits may require a future configurable manifest.
- Docker daemon, host kernel, and image provenance remain trusted. This is not VM-grade isolation.
- The default Python image does not include pytest or arbitrary dependencies; operators must prebuild and pre-pull an image when project dependencies are needed.
- The accepted patch remains an uncommitted working-tree change for the operator to inspect.
