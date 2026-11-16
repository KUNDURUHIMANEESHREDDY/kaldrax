# KALDRAX v0.2 Product Requirements Document

**Status:** v0.2 implementation baseline
**Category:** Autonomous Engineering Infrastructure
**Release objective:** Add real model-backed execution and traceable independent evaluation while preserving bounded, inspectable orchestration.

## Vision

KALDRAX is infrastructure for specifying work, coordinating execution, evaluating artifacts against explicit contracts, and iterating safely when results fail. It is not merely a chat interface or AI coding wrapper.

## v0.2 goals

1. Preserve the provider-neutral executor and evaluator ports.
2. Add an OpenAI-compatible chat-completions adapter without a runtime SDK dependency.
3. Add an LLM executor that receives the objective, criteria, iteration, and failed-criterion feedback.
4. Add an LLM evaluator configured with a different model identifier from the executor.
5. Require one evaluator result per criterion and verbatim candidate evidence for every positive judgment.
6. Derive run success from validated criterion results, never a model-provided aggregate verdict.
7. Improve offline deterministic matching to avoid substring false positives and preserve matched quotes.
8. Persist evaluator exceptions as explicit failed runs.
9. Keep the offline demo credential-free.

## Non-goals

- Autonomous unrestricted shell or code execution.
- Multi-agent coordination or agent spawning.
- Cloud worker provisioning, distributed scheduling, API, or web UI.
- Production deployment automation.
- A claim that LLM evaluation is objectively correct or fully independent.

## Functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| FR-01 | Task contract | Reject blank objective, empty/blank/duplicate criteria, and invalid iteration limit. |
| FR-02 | Pluggable executor | Engine depends on the executor protocol, not a provider implementation. |
| FR-03 | Pluggable evaluator | Evaluator receives only task contract and candidate. |
| FR-04 | LLM executor | OpenAI-compatible request uses configured model and carries retry feedback. |
| FR-05 | Independent model setting | CLI requires a non-empty evaluator model different from executor model. |
| FR-06 | Evidence-backed LLM evaluation | Require exact criterion coverage; accept positive criterion only with a verbatim quote from candidate. |
| FR-07 | Safe outcome derivation | Derive pass/fail from validated criterion rows, not model aggregate claims. |
| FR-08 | Deterministic fallback | Match whole phrases case-insensitively with token boundaries and record matched quote. |
| FR-09 | Bounded execution | Never exceed configured iterations; apply timeout and per-request output-token limit. |
| FR-10 | Explicit failures | Persist executor/evaluator errors as failed run events. |
| FR-11 | Provenance | Persist evaluations, evidence, ordered events, timestamps, and run identifier. |
| FR-12 | Offline demo | Demo runs without network or credentials. |

## Quality attributes

- **Safety:** no arbitrary command execution; candidate is treated as untrusted by evaluator.
- **Reliability:** strict response-schema checks, bounded requests, explicit failure events, behavior tests.
- **Auditability:** criterion-level quotes and JSON report.
- **Extensibility:** provider transport and core policies remain behind stable interfaces.
- **Portability:** Python 3.11+, standard-library runtime.
- **Cost control:** per-request output cap and iteration limit; aggregate token and monetary budgets remain open work.

## Success metrics

- Existing offline demo remains functional.
- LLM adapter and evaluator behavior tested without live API calls.
- Fabricated evidence cannot produce a pass.
- Missing, duplicate, or unknown criterion results are rejected.
- Executor/evaluator failures produce persisted failed reports.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Evaluator misinterprets evidence | Verbatim quote requirement; document probabilistic limitation; add deterministic checks for critical criteria. |
| Same model self-approves output | Require distinct model IDs; do not claim provider-level independence. |
| Provider hangs or returns oversized output | Per-request timeout and 4 MiB response cap. |
| Model usage becomes expensive | Per-request output cap and iteration limit; add aggregate token/cost accounting before higher autonomy. |
| Generated code is unsafe | Do not execute generated code in v0.2; sandboxing remains prerequisite. |
