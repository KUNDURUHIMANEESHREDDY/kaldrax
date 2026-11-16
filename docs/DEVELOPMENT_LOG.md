# KALDRAX Development Log

This file records implementation decisions, changes, commands, verification, and outstanding risks. Append an entry for every meaningful engineering session.

## 2026-11-16 — v0.2 LLM executor and evidence evaluator

### Decisions
- Continue working directly on GitHub main; no feature branches or pull requests.
- Preserve executor/evaluator ports and the Python 3.11+ standard-library runtime.
- Use an OpenAI-compatible chat-completions transport with no provider SDK dependency.
- Require a different configured model identifier for executor and evaluator, without claiming provider-level independence.
- Require complete criterion coverage and verbatim candidate quotes for passing LLM evaluations.
- Derive run verdicts from validated per-criterion results.

### Changes
- Added the OpenAI-compatible chat client, LLM executor, evidence-backed evaluator, strict response validation, per-request timeout/output cap, and CLI integration.
- Added criterion-evidence records and explicit persisted executor/evaluator failure events.
- Added v0.2 PRD, architecture, and ADR 0002.

### Verification
- CI ran on Python 3.11 and 3.13 and passed for the v0.2 code at the time of this baseline.

## 2026-11-16 — v0.3 persistent project memory

### Decisions
- Continue direct development on main.
- Use SQLite from the standard library at .kaldrax/memory.sqlite3.
- Separate working, episodic, and semantic memory.
- Scope all memory by project; allow project-shared and agent-private records.
- Preserve the legacy executor protocol and optionally expose working context to memory-aware executors.
- Persist every completed run; initially extract semantic lessons from explicit markers.
- Keep memory untrusted and isolated from the evaluator.

### Changes
- Added project memory, run/event provenance, lexical retrieval, duplicate consolidation, memory-aware executor context, and memory CLI commands.
- Added migration-ready storage, tests, and ADR 0003.

### Verification
- The v0.3 implementation baseline recorded 41 passing tests and an offline cross-run retrieval check.
- GitHub Actions CI later passed on both supported Python versions for the repository state preceding v0.4.

## 2026-11-16 — v0.4 memory intelligence

### Decisions
- Keep the v1 architecture local-first: SQLite remains the durable store and embeddings are generated only by an optional loopback Ollama endpoint.
- Do not introduce a hosted vector database, remote embedding provider, or required third-party Python package.
- Persist embedding model identity and compare vectors only when the query and memory use the same model.
- Use hybrid lexical/vector ranking with confidence and freshness adjustments; fall back to lexical scoring if embeddings are absent or unavailable.
- Make all automatically extracted semantic memories pending by default; only approved records are provided to future runs.
- Use exact candidate quotes for LLM-extracted facts and retain source run/event provenance.
- Limit contradiction detection to explicit opposing polarity with high token overlap. Require a human to resolve conflicts.
- Apply fixed initial retention periods: 365 days for episodes and 180 days for semantic knowledge. Preserve expired/rejected records for audit.

### Changes
- Added a provider-neutral embedding port and loopback-only Ollama adapter using POST /api/embed.
- Added SQLite migrations for embeddings, model identity, confidence, status, verification, expiry, and update timestamps.
- Added hybrid retrieval, lexical fallback, confidence/freshness ranking, reindexing, and same-model vector checks.
- Added pending approval/rejection, explicit-polarity conflict detection, conflict resolution with superseded provenance, and expiry maintenance.
- Added evidence-checked LLM knowledge extraction after passing LLM-backed runs; proposals remain pending.
- Added retrieval benchmark dataset and Recall@k, MRR, and top-1 metrics.
- Added CLI commands for memory review, conflicts, resolution, expiry, reindexing, and benchmarking.
- Updated README, PRD, architecture, repository structure, and added ADR 0004.

### Verification
- Test suite and GitHub Actions results are pending this v0.4 commit. Do not report a passing result until CI completes.
- No live LLM or Ollama request is required for the test suite; adapter behavior uses fake HTTP responses.

### Risks / follow-up
- Semantic retrieval requires the operator to install and run a local Ollama embedding model; without it, the store falls back to lexical retrieval.
- Confidence scores are not calibrated probabilities.
- Contradiction detection catches only explicit polarity patterns and can miss paraphrased or more subtle contradictions.
- The benchmark corpus is a regression fixture, not representative production workload evidence.
- The LLM extractor makes an additional provider request after a passing run and may add cost.
- The local database and reports may contain sensitive project data; protect local storage.


### v0.4 hosted verification result
- GitHub Actions run [43823453713](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43823453713) completed successfully.
- Python 3.11: package installation, complete pytest suite, and compileall all passed.
- Python 3.13: package installation, complete pytest suite, and compileall all passed.
- Tests use fake local HTTP responses for embedding and LLM adapters; no live Ollama or LLM provider request was needed.
- The v0.4 test suite was verified by hosted CI; it was not independently run in this network-restricted local container.
