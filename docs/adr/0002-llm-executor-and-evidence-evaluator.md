# ADR 0002: LLM execution adapter and evidence-backed evaluation

- **Status:** Accepted for v0.2
- **Date:** 2026-11-16

## Context

The v0.1 executor was an offline example and the deterministic evaluator used raw substring matching. KALDRAX needs a practical model-backed execution path without coupling core orchestration to one SDK or provider. It also needs stronger evaluation that can explain why each criterion passed and reject unsupported claims.

## Decision

- Add a standard-library OpenAI-compatible chat-completions client using environment-provided credentials, model IDs, base URL, timeout, and per-request output-token cap.
- Keep LLM execution behind the existing `Executor` protocol.
- Add an LLM evaluator behind an evaluator protocol. The CLI requires a different configured model ID for executor and evaluator.
- Require one result per acceptance criterion and a verbatim evidence quote for every passing judgment. Derive the overall verdict from validated criterion results; ignore any model-provided aggregate verdict.
- Retain an offline deterministic evaluator, upgraded to whole-phrase token boundaries and quote evidence.
- Persist evaluator failures as explicit failed runs; do not convert evaluator errors into passing or retry indefinitely.
- Keep provider calls outside domain models and avoid persisting API credentials.

## Consequences

- No runtime SDK dependency is added; the adapter uses Python's standard library.
- The same provider endpoint/key may be used for both roles, but model identifiers must differ. This is role separation, not a guarantee of organizational or training-data independence.
- LLM judgments remain probabilistic. Verbatim quotes establish provenance to candidate text, not correctness of the model's interpretation.
- High-assurance tasks still require deterministic tests, policy checks, and external review. No arbitrary shell or code execution is enabled by this decision.
