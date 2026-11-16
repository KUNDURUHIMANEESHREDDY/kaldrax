# KALDRAX

**Autonomous Engineering Infrastructure**
*Build. Verify. Evolve.*

KALDRAX is a local-first engineering application. Its local Python control plane runs bounded engineering tasks, independently evaluates candidate artifacts, and preserves project knowledge between runs. AI providers are adapters; local SQLite storage and the offline demo do not require a hosted KALDRAX service.

## v0.4 capabilities

- Bounded recursive execution with a separate evidence-backed evaluator.
- Persistent SQLite memory scoped by project, with optional agent-private records and project-shared records.
- Per-run working memory with retrieved context, retry feedback, and previous candidates.
- Hybrid retrieval: local embedding cosine similarity plus lexical relevance, confidence, and freshness.
- Optional local Ollama embeddings; no embedding SDK or hosted vector database.
- Automatic episodic run memory and evidence-checked LLM knowledge extraction.
- Human approval required before extracted semantic memories can influence future runs.
- Confidence metadata, configurable memory lifetimes, and automatic exclusion of expired records.
- Conservative contradiction detection and operator-controlled conflict resolution.
- Reproducible retrieval benchmark with Recall@k, mean reciprocal rank, and top-1 accuracy.
- Existing v0.2/v0.3 SQLite databases migrate in place.

## Quick start

Requires Python 3.11+.

\`\`\`powershell
python -m pip install -e ".[dev]"
kaldrax demo
\`\`\`

The offline demo requires no AI credentials. Reports are written under \`.kaldrax/runs/\` and persistent memory is stored at \`.kaldrax/memory.sqlite3\` by default. Runtime data is ignored by Git.

## Local semantic embeddings

KALDRAX can generate embeddings through a local Ollama process. Install Ollama, pull an embedding model, and configure:

\`\`\`powershell
ollama pull embeddinggemma
$env:KALDRAX_EMBEDDING_MODEL = "embeddinggemma"
$env:KALDRAX_OLLAMA_URL = "http://127.0.0.1:11434"
kaldrax memory reindex --project kaldrax-core
\`\`\`

The Ollama adapter only accepts loopback endpoints. It uses Ollama's local \`POST /api/embed\` endpoint and stores vectors in the local SQLite database. Set \`KALDRAX_EMBEDDING_MODEL\` to an empty value or leave it unset to use lexical retrieval only. When an embedding model is changed, run \`memory reindex\` to refresh existing vectors; records indexed with a different model are not compared against the new model's query vectors.

Embedding requests include project memory text and remain on the local Ollama endpoint. No vector database or additional Python package is required.

## LLM-backed engineering runs

Copy \`.env.example\` to \`.env\` and export your provider settings in the shell; the CLI does not load \`.env\` automatically.

Required environment variables:

- \`KALDRAX_API_KEY\`
- \`KALDRAX_MODEL\` — executor model identifier
- \`KALDRAX_EVALUATOR_MODEL\` — a different model identifier for evaluation

Optional provider variables include \`KALDRAX_BASE_URL\`, \`KALDRAX_TIMEOUT_SECONDS\`, \`KALDRAX_MAX_TOKENS\`, and \`KALDRAX_TOKEN_PARAMETER\`. Embedding variables are \`KALDRAX_EMBEDDING_MODEL\`, \`KALDRAX_OLLAMA_URL\`, and \`KALDRAX_EMBEDDING_TIMEOUT_SECONDS\`.

\`\`\`powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_MODEL = "executor-model"
$env:KALDRAX_EVALUATOR_MODEL = "different-evaluator-model"
$env:KALDRAX_EMBEDDING_MODEL = "embeddinggemma"
kaldrax run --project kaldrax-core --agent primary --objective "Implement a CSV parser" --criterion "unit tests pass" --criterion "README documents usage" --max-iterations 3
\`\`\`

The LLM-backed run performs one additional knowledge-extraction request after a passing candidate. Extracted claims must include exact quotes from that candidate and remain pending until reviewed. The API key is not written to reports or memory. Per-request timeouts, output-token caps, and task iteration limits apply; aggregate monetary accounting is not yet implemented.

## Memory operations

Search approved project memories:

\`\`\`powershell
kaldrax memory search --project kaldrax-core --query "acceptance evaluator feedback"
\`\`\`

Inspect candidate memories awaiting review:

\`\`\`powershell
kaldrax memory search --project kaldrax-core --query "acceptance evaluator" --include-pending
\`\`\`

Approve or reject a pending record using its ID:

\`\`\`powershell
kaldrax memory review --id MEMORY_ID --decision approve --reviewer local-user
kaldrax memory review --id OTHER_MEMORY_ID --decision reject --reviewer local-user
\`\`\`

Detect possible contradictions and resolve them explicitly:

\`\`\`powershell
kaldrax memory conflicts --project kaldrax-core
kaldrax memory resolve-conflict --conflict-id CONFLICT_ID --keep-memory-id MEMORY_ID --reviewer local-user
\`\`\`

Refresh old records by reindexing, expire records whose retention deadline has passed, and consolidate exact duplicates:

\`\`\`powershell
kaldrax memory reindex --project kaldrax-core
kaldrax memory expire --project kaldrax-core
kaldrax memory consolidate --project kaldrax-core
\`\`\`

Run the bundled retrieval benchmark:

\`\`\`powershell
kaldrax memory benchmark
\`\`\`

The benchmark reports Recall@k, mean reciprocal rank, and top-1 accuracy. It uses an isolated temporary database and does not modify project memory. Configure a local embedding model to benchmark hybrid retrieval; without one it measures the lexical fallback.

## Memory model and guarantees

- **Working memory** is transient and scoped to one engine run.
- **Episodic memory** records passed, failed, and iteration-limit runs with source run/event provenance.
- **Semantic memory** stores reusable knowledge proposals with supporting candidate quotes.
- **Approval state** separates pending, active, rejected, contested, superseded, and expired records. Only active records are retrieved by default.
- **Confidence** influences ranking but is not a calibrated probability. Human approval raises confidence and refreshes verification time.
- **Freshness** decays ranking as records age. Episodic records default to a 365-day lifetime and semantic records to 180 days; expired records are excluded even before the maintenance command marks their status.
- **Hybrid retrieval** combines local embedding cosine similarity and lexical overlap, then adjusts ranking by confidence and freshness.
- **Contradiction detection** flags high-overlap statements with explicit opposing polarity. It is a review aid, not a general natural-language logic engine. A human decides which record remains active.
- **Consolidation** merges exact normalized duplicates only and preserves contributing source run IDs and event sequences.

When Ollama is not configured or temporarily unavailable, memory persistence and lexical retrieval continue to work. Semantic extraction, conflict detection, and approval workflows do not require embeddings.

## Local-first boundary and limitations

The application, SQLite database, reports, and optional embeddings runtime are local. LLM-backed execution can send the task and candidate to the configured model provider; use the offline demo or a local OpenAI-compatible model endpoint when task data must stay on-device. KALDRAX does not run arbitrary shell commands or generated code, spawn distributed agents, provision cloud workers, or deploy software.

Memory content and reports may contain proprietary information. Protect \`.kaldrax/\` and custom artifact/database paths. Memory is untrusted historical input and cannot alter evaluator policy or acceptance criteria.

## Development

\`\`\`powershell
python -m pytest -q
python -m compileall -q src tests
\`\`\`



## v0.5 engineering runtime

### Shared run budgets

All provider calls in one run share a single thread-safe budget, including the executor, evaluator, optional memory extractor, planner, builder, and reviewer.

Default limits are 20 calls, 60,000 estimated input tokens, 12,000 completion tokens, and 72,000 total tokens. Override them using:

- `KALDRAX_MAX_PROVIDER_CALLS`
- `KALDRAX_MAX_RUN_INPUT_TOKENS`
- `KALDRAX_MAX_RUN_OUTPUT_TOKENS`
- `KALDRAX_MAX_RUN_TOTAL_TOKENS`

An optional estimated spending ceiling requires all three variables:

- `KALDRAX_MAX_RUN_COST_USD`
- `KALDRAX_INPUT_COST_PER_MILLION_USD`
- `KALDRAX_OUTPUT_COST_PER_MILLION_USD`

Use conservative rates that cover the most expensive model in the run. When the provider returns usage metadata, KALDRAX records those token counts. Otherwise it uses UTF-8 prompt/output byte counts as a conservative approximation. Cost is an estimate, not an invoice or a guarantee of provider billing. A provider can report usage above a reservation after its request has already been billed; KALDRAX stops subsequent calls and reports the breach.

### Evaluator acceptance benchmark

Run the deterministic phrase evaluator against a small, versioned fixture containing exact matches, missing requirements, token-boundary examples, and negation cases:

```powershell
kaldrax benchmark-evaluator --mode deterministic --min-accuracy 0.80
```

Run the same fixture against the configured LLM evaluator:

```powershell
kaldrax benchmark-evaluator --mode llm --min-accuracy 0.80
```

The report includes accuracy, precision, recall, F1, confusion counts, and evaluator errors. The bundled set intentionally exposes false positives for statements such as "we did not run unit tests". Passing this small fixture is a regression check, not proof of semantic reliability. Add project-specific adversarial cases before depending on the evaluator for high-impact work.

### Live provider validation

Configure `KALDRAX_API_KEY`, `KALDRAX_MODEL`, and a distinct `KALDRAX_EVALUATOR_MODEL`, then run:

```powershell
kaldrax provider-check
```

This performs one completion against the executor endpoint and one evidence-backed evaluation against the evaluator endpoint. It consumes the configured shared budget. GitHub Actions exposes a separate manual provider-smoke job, enabled only when `KALDRAX_API_KEY` and the model repository variables are configured. Ordinary pushes and pull requests never require provider credentials.

### Docker sandbox for Python candidates

Install and start Docker Engine, then pre-pull the fixed image:

```powershell
docker pull python:3.13-slim
kaldrax sandbox run-python .\candidate.py --timeout 15 --memory-mb 256 --cpu-count 1
```

The runner uses a disposable temporary workspace, no container network, read-only root filesystem, dropped Linux capabilities, no-new-privileges, an unprivileged UID, bounded CPU/memory/PIDs, wall-clock timeout, and capped output. It uses `--pull=never`; image download is an explicit operator action. The tag is not a digest pin, so operators should verify image provenance and pin a digest for stricter supply-chain controls. The Docker daemon and host kernel remain trusted parts of the isolation boundary. This adapter runs a single Python file; it does not yet provision a repository checkout, install arbitrary dependencies, or automatically run a full project test suite.

### Bounded planner-builder-reviewer workflow

Configure four distinct model IDs:

```powershell
$env:KALDRAX_PLANNER_MODEL = "planner-model"
$env:KALDRAX_MODEL = "builder-model"
$env:KALDRAX_REVIEWER_MODEL = "reviewer-model"
$env:KALDRAX_EVALUATOR_MODEL = "independent-evaluator-model"

kaldrax team --project kaldrax-core --objective "Design a CSV import utility" --criterion "streaming rows are supported" --criterion "invalid input is rejected" --max-cycles 2
```

The coordinator runs sequentially: planner → builder → reviewer → independent evaluator. Failed reviewer findings and unmet acceptance criteria feed the next builder cycle. A run passes only when the reviewer approves and the separate evaluator passes the original immutable criteria. Role traces are stored in project-scoped, agent-specific memory, and every role shares the same run budget.

This is a bounded local workflow, not a distributed scheduler. The team coordinator currently produces candidate artifacts; it does not apply patches to a repository or automatically invoke the Docker sandbox. Those should be connected through an explicit, permissioned tool contract in the next iteration.

### CI coverage

The GitHub Actions matrix runs on Python 3.11 and 3.13, executes the full test suite, runs both memory-retrieval and evaluator regression benchmarks, compiles source/tests, and performs an actual Docker sandbox smoke run on the Python 3.13 job. A manual, secret-gated job is available for live provider validation.

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [ADR 0001: Core stack](docs/adr/0001-core-stack.md)
- [ADR 0002: LLM execution and evidence evaluator](docs/adr/0002-llm-executor-and-evidence-evaluator.md)
- [ADR 0003: Persistent project memory](docs/adr/0003-persistent-project-memory.md)
- [ADR 0004: Memory intelligence](docs/adr/0004-memory-intelligence.md)
- [ADR 0005: Budgeted sandbox and agent runtime](docs/adr/0005-budgeted-sandbox-agent-runtime.md)
- [Repository structure](docs/REPOSITORY_STRUCTURE.md)
