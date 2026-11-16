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

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [ADR 0001: Core stack](docs/adr/0001-core-stack.md)
- [ADR 0002: LLM execution and evidence evaluator](docs/adr/0002-llm-executor-and-evidence-evaluator.md)
- [ADR 0003: Persistent project memory](docs/adr/0003-persistent-project-memory.md)
- [ADR 0004: Memory intelligence](docs/adr/0004-memory-intelligence.md)
- [Repository structure](docs/REPOSITORY_STRUCTURE.md)
