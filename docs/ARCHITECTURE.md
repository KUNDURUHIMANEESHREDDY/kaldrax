# KALDRAX v0.1 Architecture

## Architecture decision

Use a modular Python core with explicit ports for execution and evaluation. The first release operates locally while preserving a hybrid deployment path: local control plane and future remote workers communicate through versioned task and report contracts.

## Technology stack

| Layer | v0.1 choice | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | Portable and suitable for agent/tool integrations. |
| Core | Python standard library | Small, provider-neutral runtime. |
| Packaging / CLI | pyproject.toml, setuptools, argparse | Minimal installable package and CLI. |
| Tests | pytest | Behavior-focused automated tests. |
| Run records | JSON files | Human-inspectable local provenance. |
| API | Deferred | Add versioned HTTP API after core contracts stabilize. |
| Cloud workers | Deferred | Implement behind executor boundary after local semantics are proven. |
| Web UI | Deferred | Optional API client; never owns orchestration logic. |
| Containers | Deferred | Add sandboxing when untrusted workloads are supported. |

## Component boundaries

- **Task contract (models):** immutable objective, acceptance criteria, iteration budget.
- **Executor port (execution):** produces one candidate per iteration. Provider adapters implement this protocol later.
- **Evaluation (evaluation):** deterministic acceptance check. It receives no executor reference or hidden executor state.
- **Engine (engine):** controls iteration, feedback, stop conditions, and event recording.
- **CLI (cli):** user entry point; delegates behavior to engine.
- **Run report:** terminal status, evaluations, output, and ordered events.

## Recursive execution sequence

1. Validate task contract.
2. Start run and record event.
3. Ask executor for a candidate.
4. Evaluate candidate against original acceptance criteria.
5. If all criteria pass, stop successfully.
6. If criteria fail, pass only missing criteria as feedback and repeat.
7. If iteration budget is exhausted, stop with limit_reached.
8. Persist report.

The evaluator cannot rewrite acceptance criteria. The executor cannot set its own status. A passing evaluation means only that deterministic checks passed.

## Hybrid evolution path

- **Local control plane:** CLI, configuration, run coordination, policy, and local records.
- **Remote worker:** later executes a task envelope and returns candidate plus execution metadata.
- **Shared contracts:** versioned task, artifact, event, and evaluation schemas.
- **Cloud storage/database:** deferred until multi-worker coordination and retention needs are specified.
- **API and UI:** later clients of control plane; neither may bypass policy enforcement.

## Security and trust boundaries

- v0.1 core does not execute shell commands or load arbitrary plugins.
- Executors are trusted in-process Python implementations in this release.
- Acceptance criteria are supplied by task author and remain immutable for a run.
- Reports are local files; users must protect sensitive outputs.
- Future remote workers require authentication, least-privilege capabilities, isolated execution, signed task envelopes, and explicit resource limits.

## Known limitations

The initial evaluator uses case-insensitive substring matching. It is deterministic and independent but does not establish semantic correctness, test software behavior, or prevent a candidate from including required words without satisfying their intent. Production evaluation requires layered tests, policy checks, provenance, and independent benchmark suites.
