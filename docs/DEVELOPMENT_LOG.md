# KALDRAX Development Log

This file records implementation decisions, changes, commands, verification, and outstanding risks. Append an entry for every meaningful engineering session.

## 2026-11-16 — v0.2 LLM executor and evidence evaluator

### Decisions
- Continue working directly on GitHub `main`; no feature branches or pull requests.
- Preserve the executor/evaluator ports and the Python 3.11+ standard-library runtime.
- Use an OpenAI-compatible chat-completions transport so provider SDKs do not enter the core dependency set.
- Configure executor and evaluator with different model identifiers; document that this is not proof of provider-level independence.
- Require complete criterion coverage and verbatim candidate quotes for positive LLM evaluator results.
- Derive the verdict from validated per-criterion results; never trust a model-supplied aggregate verdict.
- Keep the offline evaluator literal and deterministic, but use phrase boundaries and quote provenance.
- Record evaluator exceptions as failed runs and persist the run report.

### Changes
- Added `llm.py` with HTTP authentication, configurable endpoint/model, timeout, output-token cap (`max_completion_tokens` by default, optional legacy `max_tokens`), response size limit, response validation, and API-key redaction in HTTP errors.
- Added `LLMExecutor` that sends objective, acceptance criteria, iteration number, and previous evaluator feedback as structured JSON.
- Added `LLMEvaluator` with strict result-shape validation, exact criterion coverage, and verbatim quote enforcement.
- Upgraded `CriteriaEvaluator` to whole-phrase boundaries and evidence quotes.
- Added criterion-evidence records to evaluation reports and rejected duplicate task criteria.
- Updated the engine to persist evaluator failures as explicit failed runs.
- Added `kaldrax run` with required environment configuration and distinct executor/evaluator model IDs; kept `kaldrax demo` offline.
- Added `.env.example`, v0.2 documentation, and ADR 0002.

### Commands and results
- `PYTHONPATH=src python -m pytest -q` — 26 passed (final verification).
- `PYTHONPATH=src python -m kaldrax.cli demo --artifacts /tmp/kaldrax-demo-report` — passed in 2 iterations; JSON report persisted.
- `python -m compileall -q src tests` — passed.
- `python -m pip install -e . --no-deps --no-build-isolation` — succeeded using the environment-installed setuptools 82.0.1. (The default isolated install could not download build requirements because this runner has no network access.)
- `kaldrax --help` — succeeded.
- `kaldrax demo --artifacts /tmp/kaldrax-installed-demo` — passed; installed CLI produced a persisted JSON report.

### Risks / follow-up
- LLM evaluator judgments remain probabilistic; verbatim quotes establish traceability, not semantic truth.
- Same provider key/endpoint may serve both models; separate model IDs do not guarantee independent training data or provider behavior.
- Aggregate token and monetary accounting is not implemented; only per-request output caps and iteration bounds exist.
- The executor produces text only. Do not execute generated code until an isolated sandbox, resource limits, and explicit command policy exist.
