# KALDRAX

**Autonomous Engineering Infrastructure**
*Build. Verify. Evolve.*

KALDRAX is a local-first engineering application. Its local Python control plane runs bounded engineering tasks, independently evaluates candidate artifacts, and preserves project knowledge between runs. AI providers are adapters; local SQLite storage and the offline demo do not require a hosted KALDRAX service.

## Core capabilities (v0.6)

- Bounded recursive execution with a separate evidence-backed evaluator.
- Persistent SQLite memory scoped by project, with optional agent-private records and project-shared records.
- Per-run working memory with retrieved context, retry feedback, and previous candidates.
- Hybrid retrieval: embedding cosine similarity plus lexical relevance, confidence, and freshness.
- Optional hosted OpenAI-compatible embeddings; no local model, embedding SDK, or hosted vector database.
- Automatic episodic run memory and evidence-checked LLM knowledge extraction.
- Human approval required before extracted semantic memories can influence future runs.
- Confidence metadata, configurable memory lifetimes, and automatic exclusion of expired records.
- Explainable contradiction candidates across negation, access policy, visibility, local/cloud, sync/async, retention, and other opposing concepts; optional hosted embeddings improve paraphrase recall. Human resolution remains mandatory.
- Annotated engineering retrieval corpus covering 40 memories and 42 queries across 15 workload categories, with Recall@k, Precision@k, NDCG@k, MRR, top-1, and category breakdowns.
- Extraction evaluation over 10 annotated scenarios and 30 expected claims, reporting precision, recall, F1, evidence-quote validity, Brier score, and expected calibration error.
- Repository intelligence for multi-language structure discovery, import/export mapping, dependency graphs, cycle detection, entry points, change impact, and relevant test selection.
- Existing v0.2/v0.3 SQLite databases migrate in place.

## Quick start

Requires Python 3.11+.

\`\`\`powershell
python -m pip install -e ".[dev]"
kaldrax demo
\`\`\`

The offline demo requires no AI credentials. Reports are written under \`.kaldrax/runs/\` and persistent memory is stored at \`.kaldrax/memory.sqlite3\` by default. Runtime data is ignored by Git.

## Hosted semantic embeddings

KALDRAX supports an OpenAI-compatible hosted embeddings API over HTTPS. No local embedding runtime or model is installed. Configure the embedding model and API credentials only when ready to use semantic retrieval:

```powershell
$env:KALDRAX_EMBEDDING_MODEL = "text-embedding-3-small"
# Optional: defaults to KALDRAX_API_KEY when unset
$env:KALDRAX_EMBEDDING_API_KEY = "..."
# Optional: defaults to KALDRAX_BASE_URL, then https://api.openai.com/v1
$env:KALDRAX_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
kaldrax memory reindex --project kaldrax-core
```

The adapter calls the hosted `POST /embeddings` endpoint and stores returned vectors in the local SQLite database. It requires HTTPS and never targets a local model server. Embedding configuration is optional: when `KALDRAX_EMBEDDING_MODEL` is unset, KALDRAX uses lexical retrieval and makes no embedding requests. When the model changes, run `memory reindex`; vectors from different model or endpoint identities are not compared.

Embedding requests send project memory text to the configured provider. Do not enable hosted embeddings for projects whose memory must remain entirely on-device. No vector database or additional Python package is required.

## LLM-backed engineering runs

Copy \`.env.example\` to \`.env\` and export your provider settings in the shell; the CLI does not load \`.env\` automatically.

Required environment variables:

- \`KALDRAX_API_KEY\`
- \`KALDRAX_MODEL\` — executor model identifier
- \`KALDRAX_EVALUATOR_MODEL\` — a different model identifier for evaluation

Optional provider variables include `KALDRAX_BASE_URL`, `KALDRAX_TIMEOUT_SECONDS`, `KALDRAX_MAX_TOKENS`, and `KALDRAX_TOKEN_PARAMETER`. Hosted embedding variables are `KALDRAX_EMBEDDING_MODEL`, optional `KALDRAX_EMBEDDING_API_KEY`, optional `KALDRAX_EMBEDDING_BASE_URL`, and `KALDRAX_EMBEDDING_TIMEOUT_SECONDS`.

\`\`\`powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_MODEL = "executor-model"
$env:KALDRAX_EVALUATOR_MODEL = "different-evaluator-model"
$env:KALDRAX_EMBEDDING_MODEL = "text-embedding-3-small"
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

The benchmark reports Recall@k, Precision@k, NDCG@k, mean reciprocal rank, top-1 accuracy, and per-category results. The default curated corpus contains 40 synthetic memories and 42 queries across engineering workloads. It uses an isolated temporary database and does not modify project memory. Configure a hosted embedding model and API key to benchmark hybrid retrieval; without one it measures the lexical fallback.

Evaluate LLM memory extraction against the 10-case, 30-claim annotated corpus:

```powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_MODEL = "extraction-model"
kaldrax memory extraction-benchmark
```

This makes one extraction request per case (10 by default). The report includes claim precision/recall/F1 and confidence Brier/ECE metrics. `KALDRAX_MODEL` must point at a hosted HTTPS provider endpoint. The benchmark's `match_terms` are explicit annotation rules, and its confidence metrics describe this sample only.

## Repository-grounded memory validation

Run the repository-specific retrieval corpus and a paired lexical-versus-hosted-hybrid comparison:

```powershell
kaldrax memory benchmark-compare --k 3
```

The source-backed draft contains 37 memories and 36 queries derived from public KALDRAX repository files at snapshot `1b50f309c7cd2f9a0dc7ec444f12fc57c25cc7d9`. Each memory includes its source path and anchor. The report carries dataset provenance, source revision, privacy-screening status, and the review status of every query. Configure `KALDRAX_EMBEDDING_MODEL` and hosted embedding API credentials to compare the lexical baseline with hosted hybrid retrieval. Without a configured or working embedder, the command reports a lexical-only baseline and does not fabricate hybrid deltas.

**Review gate:** all 36 relevance judgments are currently `assistant_proposed_pending_human_review`; the privacy scope check is also pending operator sign-off. The dataset contains public repository content only. No local SQLite memory, `.kaldrax/` runtime report, private conversation, secret, or environment value was included. These scores must not be described as human-labeled or production validation until a human reviews each query's relevant IDs and rationale, and signs off the privacy scope in `benchmarks/memory_retrieval_kaldrax_v1.json`.

The manual GitHub Actions provider-smoke job runs the 30-case live extraction benchmark when the API key and model repository variables are configured. This requires up to 30 extraction requests in addition to the provider check, uses the shared run budget (40 calls, 60,000 estimated input tokens, 36,000 completion tokens, 100,000 total tokens), and caps each completion at 1,024 tokens. Ordinary push and pull-request CI remains credential-free. The manual job has not been executed as part of this repository change.

## Memory model and guarantees

- **Working memory** is transient and scoped to one engine run.
- **Episodic memory** records passed, failed, and iteration-limit runs with source run/event provenance.
- **Semantic memory** stores reusable knowledge proposals with supporting candidate quotes.
- **Approval state** separates pending, active, rejected, contested, superseded, and expired records. Only active records are retrieved by default.
- **Confidence** influences ranking. Extractors are prompted to report estimated correctness probabilities, but scores remain uncalibrated until measured. The extraction benchmark reports sample Brier score and expected calibration error; human approval remains a separate state and confidence floor.
- **Freshness** decays ranking as records age. Episodic records default to a 365-day lifetime and semantic records to 180 days; expired records are excluded even before the maintenance command marks their status.
- **Hybrid retrieval** combines hosted embedding cosine similarity and lexical overlap, then adjusts ranking by confidence and freshness.
- **Contradiction detection** flags explainable candidates using opposing concepts (negation, allow/deny, public/private, local/cloud, sync/async, required/optional, retention, and related dimensions), subject overlap, environment scope, and optional hosted embedding similarity. It remains a heuristic review aid, not general natural-language inference. A human decides which record remains active.
- **Consolidation** merges exact normalized duplicates only and preserves contributing source run IDs and event sequences.

When a hosted embedding provider is not configured or temporarily unavailable, memory persistence and lexical retrieval continue to work. Contradiction detection falls back to lexical subject overlap. Semantic extraction, review, and conflict resolution do not require embeddings.

## Local-first boundary and limitations

The application, SQLite database, reports, and lexical retrieval are local. Hosted LLM and embedding calls send their inputs to the configured providers. The bundled memory corpora are synthetic curated fixtures, not production telemetry; add project-specific gold queries and reviewer labels before making production-quality claims. Use the offline demo when task data must remain on-device. KALDRAX does not install or run local models. LLM-backed execution can send the task and candidate to the configured model provider; it does not run arbitrary shell commands or generated code, spawn distributed agents, provision cloud workers, or deploy software.

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

The small provider connectivity check remains available:

```powershell
kaldrax provider-check
```

For the full live engineering acceptance run, configure all four distinct role models and a provider API key:

```powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_PLANNER_MODEL = "planner-model"
$env:KALDRAX_MODEL = "builder-model"
$env:KALDRAX_REVIEWER_MODEL = "reviewer-model"
$env:KALDRAX_EVALUATOR_MODEL = "evaluator-model"
kaldrax validate-live
```

The full check exercises the actual planner → builder → reviewer → independent evaluator workflow against a disposable Git repository. The generated patch is applied only to that disposable fixture after reviewer approval, independent evaluation, and Docker test success. It also checks SQLite Memory retrieval and project isolation, validates Docker daemon availability, and writes a JSON report under `.kaldrax/validation/`. The report includes per-role call latency, provider failures, token usage, shared budget data, changed paths, and test verification; it never stores API keys, prompts, or completions.

The command exits 0 on full success, 1 on a validation failure, and 2 when required configuration or infrastructure is blocked. A blocked report is still written so missing provider configuration is explicit rather than silently treated as a pass. The run makes real provider requests and consumes the configured shared budget. GitHub Actions exposes a separate manual provider-smoke job; ordinary pushes and pull requests never require provider credentials.

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

This is a bounded local workflow, not a distributed scheduler. With `--workspace`, the repository coordinator captures a clean Git snapshot, provides a path manifest and repository-intelligence map to the planner, and gives the builder a bounded source snapshot plus the dependency/test map. For every candidate patch it calculates affected components and relevant tests, stages the unified diff in isolation, and verifies a disposable copy with the Docker workspace sandbox. A patch is applied only when sandbox verification succeeds, the reviewer approves, and the independent evaluator passes the original task criteria. Dry-run is the default; `--apply` is explicit. The engine rechecks the base commit and clean worktree before applying. It never commits or pushes.

For an example, see the repository engineering integration tests. Docker image and dependency availability remain operator-managed; arbitrary dependency installation and network access are not enabled inside the verification container.

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
- [ADR 0008: Repository intelligence and dependency mapping](docs/adr/0008-repository-intelligence.md)
- [ADR 0010: Task file-scope enforcement](docs/adr/0010-task-file-scope-enforcement.md)
- [ADR 0011: Autonomous task recovery and replanning](docs/adr/0011-autonomous-task-recovery.md)
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

Supported single-stage verification modules are unittest, pytest, and compileall. The default remains unittest discovery under the tests directory. For a full Python repository gate, use --verify-module full; this runs the complete configured pytest discovery (pytest -q) and then compiles every Python file in the staged repository (compileall -q .). Both stages must pass, and at least one test must pass. The command set and discovery roots are fixed; --verify-arg is not accepted with the full profile.

The full profile requires a pre-pulled Python image containing pytest. Build the included image once and configure it before starting the run:

~~~powershell
docker build -f docker/verification.Dockerfile -t kaldrax-verification:py313 docker
$env:KALDRAX_SANDBOX_IMAGE = "kaldrax-verification:py313"
kaldrax team --workspace . --objective "Review the repository change" --criterion "all tests pass" --verify-module full
~~~

Before any provider clients are created, KALDRAX checks that Docker is available, the configured image exists locally, and an isolated no-network probe can import pytest. A missing Docker daemon, image, or pytest installation blocks the run before provider spending. KALDRAX never pulls images or installs dependencies during a run. Custom images must be pre-pulled, include Python plus the selected test dependencies, and are executed without network access.

The model-context snapshot is deliberately bounded to 240 files, 48 KB per file, and 45 KB total. This limit no longer defines the test workspace: patch staging separately reconstructs the complete safe tracked checkout from the Git index before applying the diff. Full verification staging is capped at 5,000 files, 20 MB per file, and 100 MB total. Tracked credentials/private files and excluded dependency/build/runtime directories are omitted. Tracked symlinks, submodules, unsafe paths, missing tracked files, or an exceeded size limit fail closed rather than silently producing a partial verification tree.

The sandbox copies that complete safe staged checkout into a disposable Docker workspace (never the operator's checkout), then runs each verification stage with networking disabled, an unprivileged UID, dropped capabilities, and CPU/memory/PID/time/output limits. Docker and its host kernel remain trusted; this is not a VM boundary. The model still receives only the smaller source-context snapshot.


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

**Commit the evidence used by the tag build.** Commit the approved retrieval export, both reviewed exports printed by `quality-review`, and the resulting `benchmarks/memory_quality_review_v1.json` manifest to the release candidate. Set the GitHub repository variables `KALDRAX_RETRIEVAL_DATASET`, `KALDRAX_CONTRADICTION_DATASET`, and `KALDRAX_EXTRACTION_DATASET` to those committed paths so the tag workflow evaluates exactly the reviewed datasets. If the latter two variables are unset, the workflow falls back to the original exploratory fixtures. Locally, pass the same paths to `quality-report --dataset PATH --contradiction-dataset PATH --extraction-dataset PATH`. The tag workflow checks out the tagged commit; files that exist only on a developer machine cannot satisfy the release gate. The SHA-256 digest detects accidental changes, but the reviewer field is an operator attestation, not a cryptographic identity signature.

For the tag job, configure the repository variable `KALDRAX_EMBEDDING_MODEL`, optional variable `KALDRAX_EMBEDDING_BASE_URL`, and secret `KALDRAX_EMBEDDING_API_KEY` (or reuse `KALDRAX_API_KEY`), plus `KALDRAX_API_KEY`, `KALDRAX_MODEL`, and `KALDRAX_BASE_URL`. The embedding endpoint must be a public HTTPS API reachable from the GitHub Actions runner.

A release candidate must then pass:

```bash
python -m kaldrax.cli memory quality-report --profile release --live-extraction
```

The release profile requires a validated retrieval export with privacy sign-off, a real hosted-embedding hybrid run, a live extraction run using the configured provider, a matching human label-review attestation, minimum sample sizes, and every release threshold. Initial minimums are 36 retrieval queries, 50 contradiction pairs (at least 20 positive and 20 negative), 30 extraction cases, 60 expected extraction claims, and 30 confidence observations. The expanded candidate fixtures now meet the numerical size floors: 50 contradiction pairs balanced 25/25, and 30 extraction cases with 70 proposed expected claims. However, the expanded and pre-existing labels are assistant-proposed and remain pending human review; sample-size compliance does not make them validated evidence. These are initial policy floors and should be recalibrated as the held-out corpus grows. A green regular CI run does not mean v0.6 is release-ready.


**Repository enforcement:** configure a GitHub tag/release ruleset for `v0.6.*` that requires the `v0.6 memory evidence and release thresholds` check. The workflow fails closed, but without a repository ruleset an administrator may still create a tag or release while its check is failing or skipped.

### Local repository inspection and guarded single-file edits

The local operator CLI also exposes a narrow repository interface:

```powershell
kaldrax repo status --root .\
kaldrax repo files --root .\ --directory src
kaldrax repo analyze --root .\
kaldrax repo analyze --root .\ --changed src\kaldrax\workspace.py --changed tests\test_workspace.py
kaldrax repo read --root .\ --path src\kaldrax\engine.py
```

A single-file replacement requires the SHA-256 returned by the last read and a UTF-8 content file:

```powershell
kaldrax repo apply --root .\ --path src\kaldrax\engine.py --content-file .\.kaldrax\proposed-engine.py --expected-sha256 CURRENT_SHA256
```

`repo analyze` is read-only and works with a dirty worktree. It reports file languages, detected frameworks/build systems, imports/exports, resolved local dependency edges, probable entry points, test files, strongly connected circular-dependency groups, and—when `--changed` paths are supplied—transitive dependents and likely tests. Python imports/exports use the standard-library AST. JavaScript/TypeScript, Go, Rust, Java/Kotlin, C#, and C/C++ use bounded language-specific recognizers; only resolvable local imports become graph edges. Results are navigation evidence, not compiler-grade semantic analysis. The scanner excludes credentials, runtime state, dependency/build outputs, symlinks, binary/oversized files, and files beyond its scan limits; omissions are reported.

The workspace filters secret/runtime/build paths, refuses path traversal and symlink components, limits files to supported UTF-8 text up to 1 MB, rejects stale hashes, backs up the old file under `.kaldrax/desktop-backups/`, and uses an atomic replacement. This is an explicit local edit, not an autonomous patching pipeline; it does not run tests or commit the change. The desktop editor adds a separate confirmation step before calling it.


## KALDRAX Desktop application

The native desktop application now lives in `desktop/` alongside the Python engine in this repository. It is built with React 19, TypeScript, Vite, Rust and Tauri 2, and invokes the Python package in the repository root through the local CLI.

### Run the desktop app (Windows)

Requirements: Node.js 20.19+ or 22.12+, Rust stable, Windows WebView2 Runtime, Microsoft C++ Build Tools, and Python 3.11+.

```powershell
python -m pip install -e ".[dev]"
cd desktop
npm ci
npm run desktop:dev
```

Browser preview (native Tauri commands are unavailable in a normal browser):

```powershell
cd desktop
npm run dev
```

Build and verify:

```powershell
cd desktop
npm run build
npm run lint
cargo fmt --manifest-path src-tauri/Cargo.toml -- --check
cargo check --manifest-path src-tauri/Cargo.toml
npm run desktop:build
```

Windows installers are emitted under `desktop/src-tauri/target/release/bundle/`. See [desktop/README.md](desktop/README.md), [desktop/DESIGN.md](desktop/DESIGN.md), [desktop/UX-CONTRACT.md](desktop/UX-CONTRACT.md), and [desktop/ENGINEERING-WORKFLOW-UI.md](desktop/ENGINEERING-WORKFLOW-UI.md) for setup, design and integration boundaries.


## Dependency-aware parallel orchestration

The `orchestrate` command decomposes one objective into a validated task DAG, runs independent tasks concurrently, and passes completed prerequisite outputs to dependent workers. The default concurrency is four workers (maximum eight). Every provider request shares the same thread-safe run budget.

Configure `KALDRAX_API_KEY` and four distinct role models (`KALDRAX_PLANNER_MODEL`, `KALDRAX_MODEL`, `KALDRAX_REVIEWER_MODEL`, and `KALDRAX_EVALUATOR_MODEL`), then run:

```powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_PLANNER_MODEL = "planner-model"
$env:KALDRAX_MODEL = "builder-model"
$env:KALDRAX_REVIEWER_MODEL = "reviewer-model"
$env:KALDRAX_EVALUATOR_MODEL = "evaluator-model"
kaldrax orchestrate --objective "Build a CSV import feature" --criterion "quoted fields are preserved" --max-workers 4
```

Each task has a bounded retry policy (default three attempts) with exponential backoff for transient transport failures. When work remains failed or blocked, KALDRAX asks the planner for structured root-cause diagnoses tied to task-error or dependency-state evidence, then requests a revised dependency graph. The repair plan may replace unfinished tasks and recalculate dependencies, but every successful task definition is immutable and its output is reused without rerunning it. Tasks depending on failed work remain blocked until the graph is repaired. Recovery is bounded by `--max-replans` (default 2, allowed range 0–3); the limit is persisted in the checkpoint across restarts. If the diagnosis requires operator input, automatic replanning stops. After all tasks succeed, the aggregate deliverable must pass a separate reviewer and evidence-backed independent evaluator; either gate can fail the overall run.

A graph-fingerprint-bound atomic JSON checkpoint is written under `.kaldrax/checkpoints/` by default. It stores the active task graph revision, node outputs, cumulative attempts, repository binding, and bounded repair history. Re-running the same objective resumes the latest persisted graph revision; successful outputs are preserved while only unfinished work is scheduled. Use `--retry-failed` to explicitly reset failed tasks, `--max-replans 0` to disable automatic graph repair, `--fresh` to ignore a prior checkpoint, `--checkpoint PATH` to select a checkpoint, and `--progress-jsonl PATH` to stream task events. A changed or corrupt graph/checkpoint binding is rejected rather than mixing results from different requests or repositories.

To carry completed task outputs into actual repository changes, pass a clean Git repository root:

```powershell
kaldrax orchestrate --objective "Implement a CSV import feature" --criterion "CSV tests pass" --workspace "C:/work/my-repo" --verify-module pytest
```

With `--workspace`, KALDRAX feeds the task graph and completed deliverables into the repository planner and patch builder. It validates the unified diff, stages it against an immutable clean-HEAD snapshot, executes the selected verification command in a disposable, network-isolated Docker workspace, then requires repository reviewer approval and independent evidence-backed evaluation. This mode is a dry run by default: it reports a verified patch without changing the checkout.

For DAG-backed runs, every task's `file_scope` is an exact repository-relative permission list. Each task worker receives its own scope. The aggregate patch builder is restricted to the union of those paths; KALDRAX rejects any created, modified, or deleted path outside that union before impact analysis or sandbox execution, repeats the check while staging, and checks again immediately before application. Empty, non-canonical, private, and excluded paths are rejected before task workers execute. This is exact-path matching, not directory-prefix or wildcard matching. The separate `team --workspace` workflow does not currently build a task DAG, so it retains the existing unsafe-path checks but does not yet provide per-task allowlists.

Add `--apply` to apply the patch to the selected checkout only after all gates pass. The command rejects a dirty or invalid workspace before creating provider clients, so unrelated work does not incur model charges. The apply operation rechecks that the checkout is still clean and its HEAD still matches the original snapshot immediately before writing. Never use `--apply` on a checkout containing unrelated work; commit or move unrelated changes first. The default maximum is two patch/review/verification cycles. `--max-cycles`, `--sandbox-timeout`, `--verify-module`, and repeated `--verify-arg` options configure that stage. A workspace that becomes dirty during execution is blocked by the coordinator and never has the patch applied.

Without `--workspace`, the DAG workflow returns and evaluates task deliverables without modifying a repository. No local LLM runtime is used; planning, workers, patch generation, reviewer, evaluator, and escalation calls use the configured hosted provider.
