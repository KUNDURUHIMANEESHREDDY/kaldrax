# KALDRAX v0.6 Architecture

## Architecture decision

KALDRAX is a local-first engineering application. The local Python control plane owns orchestration, policy, memory, and run reports. Model providers and the embedding runtime are adapters. The core remains usable without an internet connection through deterministic execution, evaluation, SQLite persistence, and lexical retrieval.

## Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | Portable local runtime. |
| Core / provider transport | Python standard library | No SDK lock-in or runtime service dependency. |
| Packaging / CLI | setuptools, argparse | Minimal application packaging. |
| Tests | pytest | Behavior-focused automated tests. |
| Run records | JSON files | Human-inspectable provenance. |
| Memory persistence | SQLite | Durable local records and vectors. |
| Embeddings | Local Ollama API, optional | Local semantic vectors without a hosted vector DB. |
| LLM transport | OpenAI-compatible chat completions | Configurable hosted or local model adapters. |
| Desktop/web UI | v1 local app surface; not part of this memory milestone | Keep application policy in the Python core. |

## Component boundaries

- **Task contract (models):** immutable objective, unique acceptance criteria, iteration budget, and project scope.
- **Chat client (llm):** model request transport, authentication, timeout, response size, and response validation.
- **Executor (execution):** produces one candidate per iteration; cannot assign a verdict.
- **Evaluator (evaluation):** evaluates only the task contract and candidate; the evaluator does not receive memory.
- **Embedding adapter (embeddings):** generates local vectors through Ollama's loopback-only HTTP API.
- **Memory (memory):** typed records, statuses, confidence, expiry, retrieval matches, conflicts, and SQLite persistence.
- **Memory intelligence (memory_intelligence):** optional LLM extraction with exact-candidate evidence requirements and explicitly defined confidence semantics.
- **Contradiction analysis (memory_contradictions):** explainable opposition-dimension, scope, lexical, and optional local-vector candidate detection; never auto-resolves.
- **Memory evaluation (memory_benchmarks, memory_quality):** isolated retrieval ranking and extraction quality/calibration benchmarks against versioned annotated corpora.
- **Engine (engine):** controls iteration, memory retrieval, feedback, extraction, stop conditions, and event recording.
- **CLI (cli):** configures adapters from environment variables and exposes local operator controls.

## Execution with memory

1. Validate the task, stable project ID, and iteration limit.
2. Retrieve active project memory using lexical ranking and, when configured, same-model embeddings.
3. Rank candidate records using hybrid relevance, confidence, and freshness.
4. Give the memory-aware executor bounded context containing retrieved records, provenance, feedback, and the previous candidate.
5. Give only the original task contract and candidate to the independent evaluator.
6. Retry with missing criteria as feedback, or stop on pass/limit/error.
7. Persist every completed run as an episodic record.
8. On a passing run, optionally extract reusable candidate-backed facts. Store proposals as pending; they are not retrieved by default until a human approves them.

## Memory persistence and schema evolution

The default database is \`.kaldrax/memory.sqlite3\`. SQLite schema migration adds confidence, status, verification/expiry timestamps, embedding vector/model, and update-time columns to v0.3 databases without discarding existing records. WAL mode and a busy timeout support local processes using one database; this is not a distributed coordination protocol.

Each record stores project ID, memory type, content/summary, source run ID, source event sequences, optional agent ID, tags, confidence, status, verification time, expiry time, and optional vector/model ID. SQL retrieval always scopes by project. Agent-scoped reads expose that agent's private records plus project-shared records.

## Hybrid retrieval

The optional \`OllamaEmbeddingProvider\` sends input to a local \`POST /api/embed\` endpoint. The base URL must resolve to localhost or a loopback IP. The returned vector is stored with the provider/model identifier. Query vectors are compared only to vectors created with the same model identifier and compatible dimension. A model change requires explicit reindexing.

Hybrid relevance combines normalized cosine similarity and lexical token overlap, with configurable semantic weight. If embeddings are disabled, unavailable, absent for older records, or incompatible, the record uses lexical score only. Confidence and an exponential freshness decay then scale the result. The search excludes records whose expiry deadline has passed and retrieves active records only unless an operator explicitly asks to include pending records.

The default engineering retrieval corpus contains 40 synthetic-curated memories and 42 judged queries across 15 engineering workload categories. Each query has a manually reviewed relevant-ID set. The runner validates IDs and reports Recall@k, Precision@k, NDCG@k, MRR, top-1, and category-level aggregates. Benchmark execution uses a temporary SQLite database and does not seed or modify the user's project memory. Optional Ollama embeddings run through the existing loopback-only adapter; without an embedder the same corpus measures lexical fallback.

## Confidence, freshness, and approval

Confidence is metadata used as a ranking signal, not a calibrated probability. Automatically extracted semantic memories begin in pending status and carry a verbatim evidence quote plus their source run/event provenance. The approval operation records reviewer and timestamp, raises confidence to at least 0.9, refreshes verification time, and resets the retention deadline. Rejected proposals remain stored for audit but are not retrieved.

Episodic records default to 365 days; semantic records default to 180 days. Search excludes expired records even before the operator runs the expiry maintenance command. The CLI command marks expired records with an explicit status so they can be inspected and counted.

## Contradiction detection and resolution

The detector examines active and pending semantic records within one project and produces explainable review candidates. It covers explicit negation plus opposition dimensions including allow/deny, public/private, local/cloud, online/offline, sync/async, mutable/immutable, retain/delete, include/exclude, required/optional, accept/reject, automatic/manual, encrypted/plaintext, and strict/fail-open policy. Candidate generation requires an opposing cue and sufficient subject overlap (Jaccard ≥0.42), or optional same-batch local embedding similarity (cosine ≥0.84) for paraphrases. Environment tokens such as production and staging are treated as scope boundaries when both sides specify different environments. Agent-private records owned by different agents are not compared. If the local embedder fails, detection falls back to lexical subject overlap. Each conflict stores the detected dimensions and similarity diagnostics. A pending record involved in an open conflict cannot be approved until an operator resolves the pair. Resolution still activates one side and supersedes the other with reviewer provenance. These are heuristics, not natural-language inference; all candidates require human inspection.

## Knowledge extraction

The offline extractor continues to recognize explicit Decision/Pattern/Lesson/Rule lines, but queues them for review rather than activating them automatically. The LLM extractor can propose additional reusable facts after a passing LLM-backed run. Every proposal must include an exact candidate substring of at least 12 characters and three meaningful tokens, fit a strict JSON contract, and is stored as pending. The extraction prompt defines confidence as a conservative estimated probability that the whole claim is accurate, supported, and durable; the model-reported score and that semantic definition are persisted. This is not trusted as calibrated merely because it is numeric. The extraction-quality runner evaluates predictions against manually annotated expected claims using deterministic one-to-one match-term assignment, then reports precision, recall, F1, false positives/negatives, and evidence-quote validity. It also calculates Brier score and five-bin ECE with empirical accuracy. The evaluator is never asked to validate memory proposals and does not see memory context.

## Trust, privacy, and local-first constraints

Memory content and retrieved prompts are untrusted historical data. The executor is instructed not to follow embedded instructions and to consider staleness/relevance. Memory cannot alter acceptance criteria or evaluator policy. Ollama embeddings are restricted to loopback endpoints to prevent accidental remote transfer. LLM-backed task execution still sends prompts/candidates to the configured chat endpoint; use a local compatible endpoint for fully local model inference. Secrets are not stored in memory or run reports.

## Known limitations

- Local embedding models must be installed and started separately; KALDRAX does not bundle model weights.
- Hybrid retrieval is a single-vector SQLite scan, suited to a local project memory store; it is not a distributed vector index.
- Confidence is an estimated probability supplied by the extractor. The bundled calibration report is based on only 30 synthetic expected claims and is descriptive, not proof of population calibration.
- Freshness defaults are fixed by memory type in this release; per-project retention policy UI is deferred.
- The contradiction detector covers a defined vocabulary of oppositions and similarity thresholds, but can miss contextual, temporal, modal, and domain-specific contradictions or generate false positives.
- Extraction match terms are deterministic rubric annotations; they are interpretable but do not fully score paraphrastic semantic equivalence.
- Both bundled memory corpora are synthetic curated regression fixtures. A representative production-quality assessment still needs privacy-reviewed real project queries, relevance labels, and extractor reviews.
- Embedding-enhanced conflict detection requires a local model to be configured; without it the system uses lexical overlap.
- Generated code is not executed; sandboxing and command policy are separate work.


## v0.5 execution runtime and coordination

### Shared budgets and provider transport

A thread-safe `RunBudget` is shared by every LLM client belonging to one task/team operation. Before a request is sent, the client reserves the provider-call count, UTF-8 prompt-byte estimate, and requested completion ceiling. When the response includes usage metadata, those actual counts settle the reservation; otherwise UTF-8 byte estimates are retained. The optional cost ceiling uses operator-provided per-million rates. This estimate is applied to every role model, so configure rates conservatively for the highest-cost role. Budget checks stop future calls; they cannot prevent charges for provider usage reported only after a request.

### Evaluator benchmark

The candidate-evaluator benchmark fixture is separate from the existing memory-retrieval benchmark. It measures binary acceptance decisions using accuracy, precision, recall, F1, true/false positives/negatives, and error counts. The fixture includes negation traps to expose the deterministic phrase evaluator's known limitation. LLM mode uses the configured evaluator model and the same shared budget. A small fixture score is a regression indicator, not a guarantee of semantic correctness.

### Docker execution boundary

The Python sandbox runs one source file in a disposable Docker container. It disables container networking, mounts only a temporary workspace, uses a read-only root filesystem, drops capabilities, sets no-new-privileges, runs as an unprivileged UID, and limits tmpfs, memory, CPU, PIDs, wall time, and captured output. The image must be pre-pulled by the operator; runtime uses `--pull=never`. Docker daemon/kernel/image provenance remain in the trusted computing base. No host repository checkout, arbitrary shell, privileged container, or package installation is exposed by this command.

### Multi-role orchestration

The team coordinator runs a bounded sequential graph: planner → builder → reviewer → independent evaluator. All role clients share one budget. Planner, builder, and reviewer traces are stored as agent-private episodic records under the selected project namespace. Reviewer JSON is schema- and size-validated. A reviewer approval cannot bypass the independent evaluator, which assesses the original task and acceptance criteria. Failed findings/missing criteria are fed into the next builder cycle. The current coordinator does not yet apply changes to a local Git repository or automatically invoke the sandbox.

### Live-provider verification

The provider smoke command executes a simple completion against the executor model and an evidence-backed evaluation against a distinct evaluator model. Regular CI is credential-free. A separate manual workflow dispatch can invoke live smoke only when the API key secret and model repository variables are configured.

## Memory quality evaluation

Run the default annotated retrieval workload:

```powershell
kaldrax memory benchmark --k 3
```

Set `KALDRAX_EMBEDDING_MODEL` to the local Ollama embedding model to measure hybrid retrieval. The report contains aggregate and per-category metrics.

Run extraction quality and confidence calibration against the annotated 10-case corpus:

```powershell
kaldrax memory extraction-benchmark
```

This optional command makes one LLM extraction request per case. It reports the number of expected and predicted claims, one-to-one matches, false positives/negatives, precision/recall/F1, quote validity, Brier score, ECE, and reliability bins. The benchmark does not write results into the user's memory database. The synthetic dataset and its matching rubric must be replaced or supplemented with privacy-reviewed, human-labeled project examples before its metrics can support production claims.


## Repository engineering workflow

The repository path is a separate coordinator from the prose-only team flow. It depends on the planner/builder/reviewer chat-client port, the independent evaluator port, the shared run-budget ledger, a clean Git workspace, and a Docker-backed workspace verifier.

1. Require a Git repository root with no staged, unstaged, or untracked changes; record the immutable base HEAD.
2. Capture a bounded UTF-8 file snapshot. Prioritize source/tests; omit Git/runtime metadata, dependency/build caches, credentials, environment files, databases, keys, certificates, symlinks, binary/oversized files, and lower-priority files that exceed the total limit.
3. Send the planner a path/size manifest, then send the builder the bounded snapshot and task contract. The builder must return JSON containing a summary and unified Git diff.
4. Validate every diff section and path. Reject traversal, Windows drive/ADS syntax, Git metadata/runtime paths, credential files, binary changes, renames, submodules, and mode changes.
5. Apply the patch only to a temporary Git staging workspace. Run one fixed Python verification module (unittest, pytest, or compileall) inside a separate disposable Docker copy. The container has no network and bounded memory, CPU, PIDs, runtime, and output.
6. Send the diff and captured verification results to the reviewer. The independent evaluator receives an evidence pack with the original criteria, patch, sandbox status/output, and reviewer verdict.
7. Only a successful command, non-empty test discovery for unittest/pytest, untruncated output, reviewer approval, and evaluator pass can accept the patch.
8. Default to dry-run. Applying requires the explicit apply flag; immediately before the write, verify the checkout remains clean and its HEAD matches the captured base commit. KALDRAX does not commit or push the resulting changes.

The workspace snapshot and sandbox copy are independent of the user's actual working directory. The actual checkout is never mounted into Docker. The Docker daemon, host kernel, and pre-pulled image remain trusted parts of the boundary. This is defense-in-depth, not VM-grade isolation. Custom images selected through KALDRAX_SANDBOX_IMAGE must be pre-pulled and contain Python plus the requested test module/dependencies.

## New repository runtime modules

- workspace captures bounded, secret-filtered Git snapshots, validates unified diffs, stages them in temporary Git workspaces, and applies accepted patches only after checking the base HEAD and clean-tree invariant.
- workspace_sandbox copies staged files into another disposable directory and runs an allowlisted Python verification module inside Docker with no network and resource/output limits.
- engineering implements the repository planner → patch builder → sandbox verifier → reviewer → independent evaluator loop with a shared run budget and structured report.
