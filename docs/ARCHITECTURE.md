# KALDRAX v0.4 Architecture

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
- **Memory intelligence (memory_intelligence):** optional LLM extraction with exact-candidate evidence requirements.
- **Benchmark (memory_benchmarks):** measures retrieval on an isolated fixture database.
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

The benchmark fixture reports Recall@k, mean reciprocal rank, and top-1 accuracy. Benchmark execution uses a temporary SQLite database and does not seed or modify the user's project memory.

## Confidence, freshness, and approval

Confidence is metadata used as a ranking signal, not a calibrated probability. Automatically extracted semantic memories begin in pending status and carry a verbatim evidence quote plus their source run/event provenance. The approval operation records reviewer and timestamp, raises confidence to at least 0.9, refreshes verification time, and resets the retention deadline. Rejected proposals remain stored for audit but are not retrieved.

Episodic records default to 365 days; semantic records default to 180 days. Search excludes expired records even before the operator runs the expiry maintenance command. The CLI command marks expired records with an explicit status so they can be inspected and counted.

## Contradiction detection and resolution

The current detector examines semantic records within a project for explicit opposing-polarity markers (for example, a positive statement versus an otherwise matching statement containing not/never/avoid). It requires high token-set similarity and does not infer arbitrary logical equivalence. Detected pairs are recorded as open conflicts. A pending record involved in an open conflict cannot be approved until an operator resolves the pair. Resolution activates one side and supersedes the other, recording the reviewer and decision. This is a conservative review gate, not a general contradiction model.

## Knowledge extraction

The offline extractor continues to recognize explicit Decision/Pattern/Lesson/Rule lines, but queues them for review rather than activating them automatically. The LLM extractor can propose additional reusable facts after a passing LLM-backed run. Every proposal must include a short exact substring from the candidate, must fit a strict JSON contract, and is stored as pending. Invalid, fabricated, or missing quotes reject the extraction response. The evaluator is never asked to validate memory proposals and does not see memory context.

## Trust, privacy, and local-first constraints

Memory content and retrieved prompts are untrusted historical data. The executor is instructed not to follow embedded instructions and to consider staleness/relevance. Memory cannot alter acceptance criteria or evaluator policy. Ollama embeddings are restricted to loopback endpoints to prevent accidental remote transfer. LLM-backed task execution still sends prompts/candidates to the configured chat endpoint; use a local compatible endpoint for fully local model inference. Secrets are not stored in memory or run reports.

## Known limitations

- Local embedding models must be installed and started separately; KALDRAX does not bundle model weights.
- Hybrid retrieval is a single-vector SQLite scan, suited to a local project memory store; it is not a distributed vector index.
- Confidence is heuristic metadata and requires evaluation against real outcomes before it can be interpreted probabilistically.
- Freshness defaults are fixed by memory type in this release; per-project retention policy UI is deferred.
- The contradiction detector catches a narrow class of explicit polarity conflicts and requires human judgment.
- Automatic extraction can still propose inaccurate claims; evidence quotes improve traceability but do not prove meaning.
- The bundled benchmark is a regression fixture, not a representative measure of all engineering-memory workloads.
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
