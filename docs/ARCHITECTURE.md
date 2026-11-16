# KALDRAX v0.3 Architecture

## Architecture decision

KALDRAX uses a modular Python core with explicit ports for execution and evaluation. Local orchestration, policy, memory, and reports remain in the control plane. Provider integrations are adapters and cannot control run status or rewrite acceptance criteria.

## Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | Portable and suitable for agent/tool integrations. |
| Core / provider transport | Python standard library | Small, provider-neutral runtime; no SDK lock-in. |
| Packaging / CLI | pyproject.toml, setuptools, argparse | Minimal installable package and CLI. |
| Tests | pytest | Behavior-focused automated tests. |
| Run records | JSON files | Human-inspectable local provenance. |
| Memory persistence | SQLite | Durable local records without a new runtime dependency. |
| LLM transport | OpenAI-compatible chat completions | Compatible hosted or local endpoints through one adapter. |
| API, cloud workers, UI | Deferred | Stabilize local execution and evaluation contracts first. |

## Component boundaries

- **Task contract (models):** immutable objective, unique acceptance criteria, iteration budget, and project scope.
- **Chat client (llm):** provider HTTP transport, authentication header, timeout, response size, and response-shape validation.
- **Executor (execution):** produces one candidate per iteration; the LLM adapter cannot assign a verdict.
- **Evaluator (evaluation):** evaluates only the task contract and candidate. The LLM evaluator requires criterion-level results and exact candidate quotes for positive judgments.
- **Memory (memory):** typed records, working context, retrieval matches, and a storage protocol; SQLite is the first adapter.
- **Engine (engine):** controls iteration, memory retrieval, feedback, stop conditions, error handling, and event recording.
- **CLI (cli):** configures adapters from environment variables and delegates to the engine.
- **Run report:** terminal status, evaluations, quote evidence, final output, and ordered events. API credentials are excluded.

## Execution and evaluation sequence

1. Validate the task contract and finite iteration limit.
2. Ask the executor for a candidate.
3. Ask the independent evaluator to assess every original acceptance criterion.
4. Validate the evaluator response schema and evidence quotes.
5. Derive the overall verdict from validated per-criterion results.
6. On failure, pass missing criteria back to the executor; stop on success or iteration exhaustion.
7. On executor/evaluator exception, mark the run failed and persist an explicit error event.
8. Persist the report when an artifact directory is configured.

## Provider configuration

The LLM CLI reads \`KALDRAX_API_KEY\`, \`KALDRAX_MODEL\`, and \`KALDRAX_EVALUATOR_MODEL\`. Executor and evaluator model identifiers must differ. \`KALDRAX_BASE_URL\`, \`KALDRAX_TIMEOUT_SECONDS\`, \`KALDRAX_MAX_TOKENS\`, and \`KALDRAX_TOKEN_PARAMETER\` are optional. The token parameter defaults to \`max_completion_tokens\`; legacy-compatible endpoints can select \`max_tokens\`. A separate model identifier reduces direct self-evaluation but does not prove independence of provider, model lineage, or data. Secrets are not serialized into reports or memory.

## v0.3 memory architecture

### Memory layers

- **Working memory:** transient state owned by one \`RecursiveEngine.run\` call. It contains run/project IDs, retrieved matches, current iteration, previous/current candidate, and failed-criterion feedback. It is discarded after the run.
- **Episodic memory:** a durable record for every completed run, including passed, failed, and iteration-limit outcomes. Each entry stores objective, acceptance criteria, outcome, iteration count, final candidate, source run ID, and originating event sequence numbers.
- **Semantic memory:** reusable knowledge extracted only from explicit \`Decision:\`, \`Pattern:\`, \`Lesson:\`, or \`Rule:\` lines in passing candidates. Each entry retains its source run and event provenance.

### Components and dependency direction

- **Memory contract (\`memory\`):** \`MemoryRecord\`, \`MemoryMatch\`, \`WorkingMemory\`, \`MemoryType\`, and the \`MemoryStore\` protocol.
- **SQLite adapter (\`SQLiteMemoryStore\`):** schema creation, durable writes, project-constrained retrieval, and exact-duplicate consolidation.
- **Engine:** retrieves context before the first iteration, updates working memory during retries, and records the completed run after execution/evaluation.
- **Memory-aware executor:** optional \`execute_with_memory(task, context)\` extension. Existing executors implementing only \`execute(task, feedback, iteration)\` remain compatible.
- **LLM executor:** serializes bounded relevant memories with IDs, scores, source run IDs, event sequences, and tags. Retrieved memories are labeled untrusted historical input and cannot override the task contract.
- **Evaluator:** receives only the original task and candidate. Memory is intentionally not supplied to the evaluator.

### Run sequence with memory

1. Validate the task, including its stable \`project_id\` and finite iteration limit.
2. Retrieve up to the configured number of relevant project memories using the objective and acceptance criteria.
3. Populate working memory and record the retrieved memory IDs in the run event stream.
4. Ask the executor for a candidate. A memory-aware executor also receives relevant memory, prior feedback, and the previous candidate.
5. Evaluate the candidate against the unchanged acceptance criteria using the independent evaluator.
6. On failure, update working memory with the missing criteria and current candidate, then retry within the iteration budget.
7. Persist the run report and an episodic memory record. On success, also extract explicitly marked reusable knowledge into semantic memory.
8. Consolidate duplicates only when explicitly invoked by the operator.

### Persistence, isolation, and retrieval

The default database is \`.kaldrax/memory.sqlite3\`, ignored by Git. All SQL retrieval paths include \`project_id\`. Records with \`agent_id=None\` are project-shared; an agent-scoped query can see that agent's private records plus shared records. A project-level query with no agent ID can inspect all records in that project. SQLite WAL mode and a busy timeout are enabled for local multi-process access; this is not a distributed coordination guarantee.

Retrieval uses deterministic lexical token overlap over content, summary, and tags. There is no embedding model, vector index, external database, or LLM-generated query expansion in v0.3. Consolidation groups identical normalized content by project, memory type, and agent scope, preserving contributing run IDs, event sequence numbers, and tags. It does not merge paraphrases, detect contradictions, or judge freshness.

### Trust and data handling

Memory content is historical, potentially stale, and untrusted. The LLM executor is instructed not to follow instructions embedded in memory. Memory cannot alter acceptance criteria or evaluator policy. SQLite memory and JSON reports may contain sensitive prompts, outputs, or project facts; protect \`.kaldrax/\` and custom paths. Remote access control, retention policies, encryption-at-rest management, and distributed shared memory remain future work.

## Known limitations

LLM evaluation is probabilistic. Verbatim evidence improves traceability but does not establish that a quote logically satisfies a criterion. The offline evaluator is literal phrase matching and does not understand paraphrases. The executor emits text only; this release does not run generated code, tests, shell commands, or deployments. A passing run means only that the configured evaluator accepted the declared criteria.

Semantic memory means reusable labeled knowledge records, not embedding-based semantic search. Extraction is conservative and marker-based, so unmarked lessons are not captured. Exact deduplication is operator-triggered and cannot resolve conflicting or outdated facts. The current store has no automatic expiry or human approval workflow for extracted knowledge.
