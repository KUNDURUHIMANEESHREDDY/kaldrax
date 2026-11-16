# ADR 0005: Budgeted execution, sandbox, and bounded team runtime

- **Status:** Accepted for v0.5
- **Date:** 2026-11-16

## Context

KALDRAX v0.4 adds local memory intelligence, but its LLM-backed operations still lack shared run-wide spending ceilings, candidate execution isolation, acceptance-evaluator regression measurements, live provider diagnostics, and a bounded multi-role workflow.

## Decisions

- Share one thread-safe run budget across all provider clients involved in a task/team run. Reserve calls, prompt input estimate, and completion ceilings before requests; settle actual usage when returned by the provider.
- Use optional estimated monetary ceilings only when the operator supplies input and output token rates. Explain that rates and byte-based token estimates are not provider invoices.
- Provide an evaluator-specific benchmark corpus and classification metrics independent of the memory-retrieval benchmark.
- Add a live provider smoke command; execute it in CI only on manual dispatch and only when repository secrets/variables are present.
- Execute Python source only inside a fixed Docker image with networking disabled, read-only root, dropped capabilities, no-new-privileges, unprivileged UID, disposable workspace, and resource/time/output limits.
- Add a bounded sequential planner-builder-reviewer flow. All provider roles share one budget; reviewer approval is necessary but never substitutes for the final evaluator.
- Store role traces in existing project/agent memory with provenance.
- Defer repo patch/apply tools, dependency provisioning, automatic sandbox invocation from the team workflow, and distributed/parallel agent scheduling.

## Consequences

- Model calls can be stopped before they exceed configured reservations. Late provider usage reports may reveal an overrun only after a provider call has been billed.
- Monetary enforcement is only as accurate as the rates supplied by the operator and the usage metadata returned by the endpoint.
- Docker is a stronger isolation boundary than host execution, but the daemon, host kernel, and image provenance remain trusted.
- Benchmark scores are regression signals, not proof of semantic reliability.
- The first team workflow is bounded and auditable but is not yet a complete AI coding agent that edits repositories and runs their test suites automatically.
