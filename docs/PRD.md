# KALDRAX v0.1 Product Requirements Document

**Status:** Implementation baseline
**Category:** Autonomous Engineering Infrastructure
**Release objective:** Prove a bounded, observable, independently evaluated improvement cycle.

## Vision

KALDRAX is infrastructure for specifying work, coordinating execution, evaluating artifacts against explicit contracts, and iterating safely when results fail. It is not merely a chat interface or AI coding wrapper. The same execution model should eventually support software projects, agent systems, workflows, and other engineered artifacts.

## Problem

Agentic workflows can produce plausible outputs without proving that requirements were met. Common failure modes include unbounded retries, opaque decisions, evaluators coupled to the producing agent, missing provenance, and unsafe execution permissions. KALDRAX makes execution bounded and inspectable and separates artifact production from acceptance decisions.

## Target users

- Individual developers using local agent and tool providers.
- Engineering teams that need repeatable, auditable agent workflows.
- Platform builders integrating execution and evaluation through APIs.
- Operators managing local and remote workers.

## v0.1 goals

1. Define a task contract with objective, explicit acceptance criteria, and iteration limit.
2. Execute through a pluggable executor interface.
3. Evaluate each candidate using an evaluator independent of the executor.
4. Feed failed criteria back into the next iteration.
5. Stop on success or a hard iteration limit.
6. Persist a structured run report with events and evaluation results.
7. Provide an offline CLI demonstration and automated tests.

## Non-goals

- Autonomous unrestricted shell or code execution.
- LLM-provider integrations or agent spawning.
- Cloud worker provisioning or distributed scheduling.
- Self-modification of KALDRAX source code.
- Web UI, hosted control plane, or multi-tenant service.
- Production deployment automation.
- Semantic correctness claims beyond the implemented deterministic checks.

## Primary user journey

1. Define an objective and acceptance criteria.
2. Set a finite maximum iteration count.
3. Start a run through CLI or Python API.
4. Review each iteration and independent evaluation.
5. Inspect the final artifact and machine-readable report.
6. Treat a passing result as satisfying only the declared criteria, not as universal correctness.

## Functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| FR-01 | Task contract | Reject blank objectives, empty criteria, and invalid iteration limits. |
| FR-02 | Pluggable executor | Engine depends on an executor protocol, not a provider implementation. |
| FR-03 | Independent evaluator | Evaluator receives only task contract and candidate. |
| FR-04 | Recursive correction | Missing criteria become feedback to the next iteration. |
| FR-05 | Bounded execution | Never exceed the configured maximum iterations. |
| FR-06 | Explicit outcomes | Report passed or iteration-limit reached; never silently imply success. |
| FR-07 | Provenance | Record ordered events, evaluations, timestamps, and run identifier. |
| FR-08 | Persistence | Write JSON report when an artifact directory is configured. |
| FR-09 | CLI demo | Run offline without credentials or network access. |

## Quality attributes

- **Safety:** no arbitrary command execution in the core loop.
- **Reliability:** deterministic evaluator and tests for pass/fail/limit paths.
- **Auditability:** structured event history and persisted reports.
- **Extensibility:** stable executor protocol and evaluator interface.
- **Portability:** Python 3.11+, standard-library runtime.
- **Cost control:** hard iteration bound in v0.1; token and monetary budgets before provider integrations.

## Success metrics

- All v0.1 acceptance tests pass.
- Demo reaches a passing result after at least one failed evaluation.
- Incomplete executor stops exactly at configured limit.
- Persisted report contains all iteration evaluations and terminal status.
- CLI runs offline with no API key.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| String matching is weaker than semantic evaluation | Label evaluator honestly; add benchmarked evaluator plugins later. |
| Executor may return malformed output | Validate output type and treat empty candidates as failures. |
| Recursive loops consume resources | Enforce iteration limit; add wall-clock and token budgets before model providers. |
| Producer/evaluator collusion | Separate evaluator interface and deny it executor state. |
| Reports contain sensitive artifacts | Local-only by default; define redaction and retention before remote storage. |

## Release exit criteria

FR-01 through FR-09 implemented, automated tests pass, CLI demo produces a persisted passing report, and documentation states current limitations accurately.
