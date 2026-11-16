# KALDRAX

**Autonomous Engineering Infrastructure**
*Build. Verify. Evolve.*

KALDRAX is a local-first engineering application. Its local Python control plane runs bounded engineering tasks, independently evaluates candidate artifacts, and preserves project knowledge between runs. AI providers are adapters; local SQLite storage and the offline demo do not require a hosted KALDRAX service.

## Core capabilities (v0.6)

- Bounded recursive execution with a separate evidence-backed evaluator.
- Persistent SQLite memory scoped by project, with optional agent-private records and project-shared records.
- Per-run working memory with retrieved context, retry feedback, and previous candidates.
- Hybrid retrieval: local embedding cosine similarity plus lexical relevance, confidence, and freshness.
- Optional local Ollama embeddings; no embedding SDK or hosted vector database.
- Automatic episodic run memory and evidence-checked LLM knowledge extraction.
- Human approval required before extracted semantic memories can influence future runs.
- Confidence metadata, configurable memory lifetimes, and automatic exclusion of expired records.
- Explainable contradiction candidates across negation, access policy, visibility, local/cloud, sync/async, retention, and other opposing concepts; optional local embeddings improve paraphrase recall. Human resolution remains mandatory.
- Annotated engineering retrieval corpus covering 40 memories and 42 queries across 15 workload categories, with Recall@k, Precision@k, NDCG@k, MRR, top-1, and category breakdowns.
- Extraction evaluation over 10 annotated scenarios and 30 expected claims, reporting precision, recall, F1, evidence-quote validity, Brier score, and expected calibration error.
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

The benchmark reports Recall@k, Precision@k, NDCG@k, mean reciprocal rank, top-1 accuracy, and per-category results. The default curated corpus contains 40 synthetic memories and 42 queries across engineering workloads. It uses an isolated temporary database and does not modify project memory. Configure a local embedding model to benchmark hybrid retrieval; without one it measures the lexical fallback.

Evaluate LLM memory extraction against the 10-case, 30-claim annotated corpus:

```powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_MODEL = "extraction-model"
kaldrax memory extraction-benchmark
```

This makes one extraction request per case (10 by default). The report includes claim precision/recall/F1 and confidence Brier/ECE metrics. `KALDRAX_MODEL` may point at a hosted provider or a local OpenAI-compatible endpoint. The benchmark's `match_terms` are explicit annotation rules, and its confidence metrics describe this sample only.

## Repository-grounded memory validation

Run the repository-specific retrieval corpus and a paired lexical-versus-local-hybrid comparison:

```powershell
kaldrax memory benchmark-compare --k 3
```

The source-backed draft contains 37 memories and 36 queries derived from public KALDRAX repository files at snapshot `1b50f309c7cd2f9a0dc7ec444f12fc57c25cc7d9`. Each memory includes its source path and anchor. The report carries dataset provenance, source revision, privacy-screening status, and the review status of every query. Configure `KALDRAX_EMBEDDING_MODEL` and a running loopback Ollama instance to compare the lexical baseline with local hybrid retrieval. Without a configured or working embedder, the command reports a lexical-only baseline and does not fabricate hybrid deltas.

**Review gate:** all 36 relevance judgments are currently `assistant_proposed_pending_human_review`; the privacy scope check is also pending operator sign-off. The dataset contains public repository content only. No local SQLite memory, `.kaldrax/` runtime report, private conversation, secret, or environment value was included. These scores must not be described as human-labeled or production validation until a human reviews each query's relevant IDs and rationale, and signs off the privacy scope in `benchmarks/memory_retrieval_kaldrax_v1.json`.

The manual GitHub Actions provider-smoke job now also runs the 10-case live extraction benchmark when the API key and model repository variables are configured. That adds up to 10 model requests, uses the shared run budget, and caps each completion at 1,024 tokens. Ordinary push and pull-request CI remains credential-free. The manual job has not been executed as part of this repository change.

## Memory model and guarantees

- **Working memory** is transient and scoped to one engine run.
- **Episodic memory** records passed, failed, and iteration-limit runs with source run/event provenance.
- **Semantic memory** stores reusable knowledge proposals with supporting candidate quotes.
- **Approval state** separates pending, active, rejected, contested, superseded, and expired records. Only active records are retrieved by default.
- **Confidence** influences ranking. Extractors are prompted to report estimated correctness probabilities, but scores remain uncalibrated until measured. The extraction benchmark reports sample Brier score and expected calibration error; human approval remains a separate state and confidence floor.
- **Freshness** decays ranking as records age. Episodic records default to a 365-day lifetime and semantic records to 180 days; expired records are excluded even before the maintenance command marks their status.
- **Hybrid retrieval** combines local embedding cosine similarity and lexical overlap, then adjusts ranking by confidence and freshness.
- **Contradiction detection** flags explainable candidates using opposing concepts (negation, allow/deny, public/private, local/cloud, sync/async, required/optional, retention, and related dimensions), subject overlap, environment scope, and optional local embedding similarity. It remains a heuristic review aid, not general natural-language inference. A human decides which record remains active.
- **Consolidation** merges exact normalized duplicates only and preserves contributing source run IDs and event sequences.

When Ollama is not configured or temporarily unavailable, memory persistence and lexical retrieval continue to work. Contradiction detection falls back to lexical subject overlap. Semantic extraction, review, and conflict resolution do not require embeddings.

## Local-first boundary and limitations

The application, SQLite database, reports, and optional embeddings runtime are local. The bundled memory corpora are synthetic curated fixtures, not production telemetry; add project-specific gold queries and reviewer labels before making production-quality claims. LLM-backed execution can send the task and candidate to the configured model provider; use the offline demo or a local OpenAI-compatible model endpoint when task data must stay on-device. KALDRAX does not run arbitrary shell commands or generated code, spawn distributed agents, provision cloud workers, or deploy software.

Memory content and reports may contain proprietary information. Protect \`.kaldrax/\` and custom artifact/database paths. Memory is untrusted historical input and cannot alter evaluator policy or acceptance criteria.

## Development

\`\`\`powershell
python -m pytest -q
python -m compileall -q src tests
\`\`\`



## v0.6 engineering runtime

### Shared run budgets

All provider calls in one run share a single thread-safe budget, including the executor, evaluator, optional memory extractor, planner, builder, and reviewer.

Default limits are 20 calls, 60,000 estimated input tokens, 12,000 completion tokens, 72,000 total tokens, and 600 seconds of wall-clock time. Each provider request timeout is capped by the remaining run deadline. Override them using:

- `KALDRAX_MAX_PROVIDER_CALLS`
- `KALDRAX_MAX_RUN_INPUT_TOKENS`
- `KALDRAX_MAX_RUN_OUTPUT_TOKENS`
- `KALDRAX_MAX_RUN_TOTAL_TOKENS`
- `KALDRAX_MAX_RUN_DURATION_SECONDS` — shared wall-clock budget (default 600 seconds)

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
- [ADR 0006: Memory quality and contradiction evaluation](docs/adr/0006-memory-quality-evaluation.md)
- [ADR 0007: Repository-aware engineering loop](docs/adr/0007-repository-engineering-loop.md)
- [Repository structure](docs/REPOSITORY_STRUCTURE.md)


## Human-reviewing retrieval benchmark datasets

The source-backed KALDRAX retrieval corpus is an annotation proposal, not a human-labeled benchmark. Its query labels and privacy scope remain pending until an operator reviews them.

Start or resume the local terminal review:

```bash
kaldrax memory benchmark-annotate \
  --dataset benchmarks/memory_retrieval_kaldrax_v1.json \
  --reviewer "<reviewer-id>" \
  --version 1.0.0
```

For each query, the workflow displays the query, proposed relevant memories, and the full candidate-memory index. Reviewers can approve the proposed IDs, reject the proposal, replace the relevant-ID set, skip, or stop and resume later. Each decision records the reviewer and UTC timestamp in a resumable session under `.kaldrax/benchmark-reviews/`.

Dataset annotation approval and privacy approval are separate gates. Privacy approval requires an explicit confirmation after the source paths and copied memory content have been displayed. The source dataset is never edited. An export is written under `.kaldrax/benchmark-exports/` only when every query is approved or corrected, dataset annotation approval is granted, and privacy screening is independently approved.

Exports use a numeric MAJOR.MINOR.PATCH version, a SHA-256 content digest, and write-once filenames. Retrieval benchmark reports expose `benchmark_validation.status`; datasets without complete review provenance and a valid integrity digest are labelled `exploratory_only`, not validated. Review sessions and exports are local operator data and are ignored by Git.


### Repository-aware team workflow

KALDRAX can now perform a guarded repository build-test-review cycle. It requires a Git repository root with a clean working tree, Git installed, Docker running, four distinct configured role models, and a pre-pulled sandbox image.

~~~powershell
docker pull python:3.13-slim
kaldrax team --workspace . --project kaldrax-core --objective "Fix CSV parsing so quoted commas are preserved and blank rows are ignored" --criterion "csv.reader" --criterion "any(field.strip() for field in row)" --criterion "Sandbox verification exit code: 0" --verify-module unittest --sandbox-timeout 90
~~~

The default is a dry run: KALDRAX snapshots a bounded selection of source and test files, asks the builder for a unified Git diff, rejects unsafe paths and credential/runtime files, stages the patch in a temporary Git workspace, and runs the selected verification command in a separate disposable Docker copy. The reviewer sees the diff and actual test output; a separate evaluator checks the evidence pack. A patch is accepted only when verification exits successfully, at least one test was discovered for unittest/pytest, output was not truncated or timed out, the reviewer approves, and the independent evaluator passes.

To write the accepted patch into the real checkout, add the explicit apply flag:

~~~powershell
kaldrax team --workspace . --objective "Fix CSV parsing" --criterion "csv.reader" --criterion "Sandbox verification exit code: 0" --verify-module unittest --apply
~~~

The apply flag modifies the working tree but does not create a Git commit. It rechecks that the original HEAD is unchanged and the checkout remains clean immediately before applying. Without apply, the report records a verified dry run and leaves the checkout untouched. Existing prose-only team operation remains available without a workspace argument.

Supported verification modules are unittest, pytest, and compileall. The default is unittest discovery under the tests directory. Pytest requires an image that already contains pytest and the project's test dependencies. Configure a pre-pulled image with KALDRAX_SANDBOX_IMAGE; KALDRAX never pulls arbitrary images during a run. The image must contain Python and the selected verification module. Additional module arguments can be supplied with repeated verify-arg options.

The snapshot is bounded to 240 files, 48 KB per file, and 45 KB total. Source and test paths take priority over docs and examples. Common credential locations, environment files (except the example file), key/certificate/database files, Git metadata, and KALDRAX runtime state are excluded or rejected. A repository that is dirty, has unsupported submodules/symlinks in touched paths, or changes HEAD during the run is refused.

The sandbox disables networking, uses an unprivileged UID, drops capabilities, applies CPU/memory/PID/time/output limits, and mounts only a disposable copy (never the operator's checkout). Docker and its host kernel remain trusted; this is not a VM boundary. The workspace is a bounded snapshot, not an unrestricted clone: omitted files are unavailable to the model and may make a patch unverifiable.


## Memory evaluation and v0.6 release gate

Generate the full deterministic report during normal development:

```bash
python -m kaldrax.cli memory quality-report --profile ci
```

The command writes JSON and Markdown under `.kaldrax/evaluation/` by default. CI uploads the same evidence as a GitHub Actions artifact and enforces the credential-free regression floors from `benchmarks/memory_release_thresholds_v1.json`.

Before a v0.6 release candidate, complete the existing query-by-query review and separate privacy approval with `memory benchmark-annotate`, then use the resulting approved immutable export as the retrieval benchmark dataset. Review contradiction and extraction labels with the resumable, case-by-case workflow:

```bash
python -m kaldrax.cli memory quality-review --reviewer "reviewer-id"
```

For each contradiction case, explicitly accept or toggle the proposed conflict label. For each extraction case, accept or replace the expected-claims JSON. Progress is saved under `.kaldrax/`; the session is bound to the exact source-file hashes and refuses to resume against changed datasets. Each dataset requires a separate typed approval before immutable, hash-addressed reviewed exports are written under `benchmarks/reviewed/`. The command then creates the hash-bound approval manifest. It never approves labels without those interactive decisions.

**Commit the evidence used by the tag build.** Pass the approved retrieval export to `quality-approve --retrieval-dataset PATH`. Commit that export, any corrected contradiction/extraction dataset files, and the resulting `benchmarks/memory_quality_review_v1.json` manifest to the release candidate. Set the GitHub repository variable `KALDRAX_RETRIEVAL_DATASET` to the committed export path so the tag workflow evaluates the same file (when unset, it uses `benchmarks/memory_retrieval_kaldrax_v1.json`). Locally, pass the same path to `quality-report --dataset PATH`. The tag workflow checks out the tagged commit; files that exist only on a developer machine cannot satisfy the release gate. The SHA-256 digest detects accidental changes, but the reviewer field is an operator attestation, not a cryptographic identity signature.

For the tag job, configure `KALDRAX_EMBEDDING_MODEL` and `KALDRAX_OLLAMA_URL` reachable from the GitHub Actions runner, plus `KALDRAX_API_KEY`, `KALDRAX_MODEL`, and `KALDRAX_BASE_URL`. The default Ollama URL points to localhost on the runner, not the developer's computer. A private local endpoint requires a reachable deployment or a runner hosted inside the same network.

A release candidate must then pass:

```bash
python -m kaldrax.cli memory quality-report --profile release --live-extraction
```

The release profile requires a validated retrieval export with privacy sign-off, a real Ollama hybrid run, a live extraction run using the configured provider, a matching human label-review attestation, minimum sample sizes, and every release threshold. Initial minimums are 36 retrieval queries, 50 contradiction pairs (at least 20 positive and 20 negative), 30 extraction cases, 60 expected extraction claims, and 30 confidence observations. The current fixtures (8 contradiction pairs and 10 extraction cases) are intentionally below these release minimums and must be expanded with independently reviewed examples. These are initial policy floors and should be recalibrated as the held-out corpus grows. A green regular CI run does not mean v0.6 is release-ready.


**Repository enforcement:** configure a GitHub tag/release ruleset for `v0.6.*` that requires the `v0.6 memory evidence and release thresholds` check. The workflow fails closed, but without a repository ruleset an administrator may still create a tag or release while its check is failing or skipped.
