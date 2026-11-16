# KALDRAX Development Log

This file records implementation decisions, changes, commands, verification, and outstanding risks. Append an entry for every meaningful engineering session.

## 2026-11-16 — v0.2 LLM executor and evidence evaluator

### Decisions
- Continue working directly on GitHub \`main\`; no feature branches or pull requests.
- Preserve the executor/evaluator ports and the Python 3.11+ standard-library runtime.
- Use an OpenAI-compatible chat-completions transport so provider SDKs do not enter the core dependency set.
- Configure executor and evaluator with different model identifiers; document that this is not proof of provider-level independence.
- Require complete criterion coverage and verbatim candidate quotes for passing LLM evaluator results.
- Derive the verdict from validated per-criterion results; never trust a model-supplied aggregate verdict.
- Keep the offline evaluator literal and deterministic, but use phrase boundaries and quote provenance.
- Record evaluator exceptions as failed runs and persist the run report.

### Changes
- Added \`llm.py\` with HTTP authentication, configurable endpoint/model, timeout, output-token cap (\`max_completion_tokens\` by default, optional legacy \`max_tokens\`), response size limit, response validation, and API-key redaction in HTTP errors.
- Added \`LLMExecutor\` that sends objective, acceptance criteria, iteration number, and previous evaluator feedback as structured JSON.
- Added \`LLMEvaluator\` with strict result-shape validation, exact criterion coverage, and verbatim quote enforcement.
- Upgraded \`CriteriaEvaluator\` to whole-phrase boundaries and evidence quotes.
- Added criterion-evidence records to evaluation reports and rejected duplicate task criteria.
- Updated the engine to persist evaluator failures as explicit failed runs.
- Added \`kaldrax run\` with required environment configuration and distinct executor/evaluator model IDs; kept \`kaldrax demo\` offline.
- Added \`.env.example\`, v0.2 documentation, and ADR 0002.

### Commands and results
- \`PYTHONPATH=src python -m pytest -q\` — 26 passed (final verification).
- \`PYTHONPATH=src python -m kaldrax.cli demo --artifacts /tmp/kaldrax-demo-report\` — passed in 2 iterations; JSON report persisted.
- \`python -m compileall -q src tests\` — passed.
- \`python -m pip install -e . --no-deps --no-build-isolation\` — succeeded using the environment-installed setuptools 82.0.1. (The default isolated install could not download build requirements because this runner has no network access.)
- \`kaldrax --help\` — succeeded.
- \`kaldrax demo --artifacts /tmp/kaldrax-installed-demo\` — passed; installed CLI produced a persisted JSON report.

### Risks / follow-up
- LLM evaluator judgments remain probabilistic; verbatim quotes establish traceability, not semantic truth.
- Same provider key/endpoint may serve both models; separate model IDs do not guarantee independent training data or provider behavior.
- Aggregate token and monetary accounting is not implemented; only per-request output caps and iteration bounds exist.
- The executor produces text only. Do not execute generated code until an isolated sandbox, resource limits, and explicit command policy exist.

## 2026-11-16 — v0.3 persistent project memory

### Decisions
- Continue direct development on \`main\`; no feature branches or pull requests.
- Keep KALDRAX's v0.2 LLM executor and independent evaluator intact and make memory an additive engine port.
- Use SQLite from the standard library for local durable memory; default path is \`.kaldrax/memory.sqlite3\`.
- Separate transient working memory, episodic run history, and semantic reusable lessons.
- Require \`project_id\` on every task (default \`default\`) and every memory query/write.
- Treat \`agent_id=None\` as project-shared knowledge; an agent-scoped lookup sees only its own private memory plus shared project records.
- Preserve the legacy executor method and add an optional \`execute_with_memory(task, context)\` capability.
- Send retrieved memory only to memory-aware executors, never to the evaluator. Include previous candidate and feedback in working memory.
- Automatically persist every run as an episode. Extract semantic memories only from explicit \`Decision:\`, \`Pattern:\`, \`Lesson:\`, or \`Rule:\` lines in a passing artifact; do not ask an LLM to invent facts.
- Use deterministic lexical token-overlap ranking, not embeddings. Keep consolidation explicit and limited to exact normalized duplicates, preserving source provenance.
- Treat retrieved memory as untrusted historical data and instruct the LLM executor not to follow embedded instructions.

### Changes
- Added typed memory records, memory matches, memory types, working-memory state, and a \`MemoryStore\` protocol.
- Added SQLite persistence with project/type/agent indexes, WAL mode, a busy timeout, deterministic lexical retrieval, and exact-duplicate consolidation.
- Added automatic episodic recording for passed, failed, and iteration-limit runs.
- Added conservative semantic extraction from explicit reusable-knowledge markers after passing runs.
- Added engine memory retrieval, audit events with retrieved record IDs, optional agent scope, and best-effort memory failure reporting.
- Extended \`LLMExecutor\` with a compatible memory-aware entry point carrying retrieved records, source run/event provenance, feedback, and previous candidate.
- Added CLI \`--project\`, \`--agent\`, and \`--memory-db\` options plus \`kaldrax memory search\` and \`kaldrax memory consolidate\`.
- Updated README, PRD, architecture, repository structure, and added ADR 0003.

### Verification
- \`PYTHONPATH=src python -m pytest -q\` — 41 passed.
- \`PYTHONPATH=src python -m compileall -q src tests\` — passed.
- Offline CLI demo executed twice against the same SQLite database; the second run retrieved prior project memories.
- \`kaldrax memory search\` returned persisted records with source run and event provenance.
- \`kaldrax memory consolidate\` merged an exact duplicate while preserving contributing provenance.
- No live provider request was made; existing LLM adapter/evaluator tests remain offline.

### Risks / follow-up
- Lexical retrieval does not find paraphrases and does not use embeddings.
- Explicit-marker extraction misses useful lessons that are not labeled and can still preserve misleading candidate text.
- Exact deduplication cannot detect contradictions or determine whether knowledge is stale.
- Memory and run reports may contain sensitive project context; local storage and access controls remain the operator's responsibility.
- Cross-process SQLite use is supported for local persistence but is not a distributed agent coordination protocol.

## 2026-11-16 — CI workflow baseline

### Decisions
- Add GitHub Actions checks for pushes to main, pull requests targeting main, and manual dispatch.
- Test Python 3.11 and 3.13.
- Grant the workflow read-only repository contents permission.

### Changes
- Added .github/workflows/ci.yml to install the editable package with development dependencies, run pytest, and compile source/tests.

### Verification
- Confirmed GitHub main points to commit 753a70c8accf7f33f7b923a8262b921b2969b9dd before this log-only follow-up.
- Fetched the committed workflow file and inspected its trigger, matrix, permissions, and steps.
- GitHub commit status returned no status checks, and the visible Actions-runs query returned zero runs at inspection time. A completed hosted CI result is not yet verified.
- The v0.3 development entry records 41 passing tests; this session did not independently rerun the repository suite because a local GitHub clone was unavailable.

### Risks / follow-up
- Confirm the first GitHub Actions run completes on both Python versions.
- Live provider validation, evaluator benchmark work, sandboxed code execution, and aggregate token/cost limits remain deferred as requested.
