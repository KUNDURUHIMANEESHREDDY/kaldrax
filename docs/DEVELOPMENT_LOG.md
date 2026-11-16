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


## 2026-11-16 — v0.5 budgeted engineering runtime

### Decisions
- Preserve v0.4 hybrid memory, human approval, and memory retrieval benchmarks.
- Share a single run-wide call/token/cost ledger across all chat model roles and optional memory extraction.
- Use UTF-8 byte-based prompt estimates when provider token usage is absent; label these as estimates.
- Keep monetary ceilings optional and operator-configured because model pricing differs by provider and model.
- Run candidate Python only in a fixed Docker container with network disabled and resource limits.
- Keep the coordinator sequential and bounded; reviewer approval cannot supersede final independent evaluation.
- Keep live provider checks manually triggered and secret-gated.

### Changes
- Added a thread-safe run budget with call, input, output, total-token, and optional estimated monetary limits.
- Extended the OpenAI-compatible client to reserve/settle budgets and retain provider usage metadata.
- Added an evaluator regression benchmark corpus and accuracy/precision/recall/F1/confusion/error reporting.
- Added a Docker-backed Python sandbox with read-only container root, unprivileged execution, no network, temporary workspace, resource/time/output limits, and pre-pulled image policy.
- Added a sequential planner-builder-reviewer coordinator with a separate final evaluator and agent-scoped role traces.
- Added provider-check, benchmark-evaluator, team, and sandbox CLI commands.
- Extended GitHub Actions with evaluator and memory benchmarks, an actual Docker smoke test, and a manual secret-gated live-provider job.
- Added ADR 0005 and updated setup/architecture/requirements documentation.

### Verification
- Pending hosted CI for this commit. The local execution environment cannot independently run the complete GitHub repository or Docker daemon.
- Provider smoke remains unverified until repository secrets/model variables are configured and the manual job is dispatched.
- Docker sandbox behavior has unit tests using a fake Docker process; hosted CI will exercise a real Docker run.

### Risks / follow-up
- Provider token byte estimates are approximate; exact model tokenization is not bundled.
- Monetary rates must be configured using conservative values for the most expensive model in a run.
- Evaluator benchmark cases are a small regression corpus and expose known negation false positives.
- Docker tag is mutable and not digest-pinned; operators should verify image provenance or use an immutable digest before high-assurance use.
- Team agents currently produce candidate artifacts and traces but do not patch repositories or automatically invoke the sandbox.

## 2026-11-15 — v0.5 memory quality and contradiction analysis

### Decisions
- Keep benchmark evaluation isolated from the operator's runtime SQLite database.
- Use manually annotated synthetic engineering workloads as a deterministic regression baseline; do not describe synthetic results as production performance.
- Expand contradiction detection with explicit opposing policy dimensions, lexical subject overlap, environment scoping, and optional same-batch local embedding similarity.
- Keep every detected contradiction as a human-reviewed candidate. No automatic activation, superseding, or resolution.
- Define extractor confidence as a conservative estimated probability of a correct, supported, durable claim; preserve the model-reported value and evaluate it rather than treating it as calibrated.
- Keep live LLM extraction benchmarking optional and separate from credential-free CI.

### Changes
- Added `memory_contradictions.py` and connected its explainable candidate results to the existing conflict-review workflow.
- Added opposition dimensions for allow/deny, public/private, local/cloud, online/offline, sync/async, mutable/immutable, retain/delete, include/exclude, required/optional, accept/reject, automatic/manual, encrypted/plaintext, and strict/fail-open policies.
- Added subject Jaccard and optional local-embedding similarity checks, with lexical fallback and disjoint-environment filtering.
- Added `memory_retrieval_engineering_v2.json`: 40 annotated memory records and 42 queries across 15 synthetic engineering categories.
- Expanded retrieval reporting to Precision@k, NDCG@k, category aggregates, in addition to Recall@k, MRR, and top-1. Added corpus-reference validation.
- Added `memory_extraction_v1.json`: 10 annotated extraction cases and 30 expected claims.
- Added `memory_quality.py` with one-to-one annotated claim matching, precision/recall/F1, false-positive/negative counts, exact-evidence quote validity, Brier score, and five-bin ECE.
- Strengthened extraction evidence minimums and defined/persisted confidence semantics.
- Added CLI support for `kaldrax memory extraction-benchmark`; the default retrieval benchmark now uses the broader engineering corpus.
- Added contradiction, extraction quality/calibration, retrieval corpus, and CLI regression tests.
- Updated README, PRD, architecture, repository map, and ADR 0006.

### Verification
- GitHub Actions verification is pending for the final main-branch head. Do not treat this implementation as verified until the workflow completes.
- The retrieval benchmark and deterministic extraction evaluator have not yet been measured with a live Ollama/LLM provider in this session.
- The extraction benchmark is opt-in and makes one configured provider request per case; its default dataset has 10 cases.
- No project memory database schema changes were introduced in this track.

### Risks / follow-up
- Both datasets are synthetic curated fixtures; representative production evaluation still requires privacy-reviewed project traces and human relevance/claim labels.
- Extraction matching is deterministic and term-based, not a full semantic equivalence judge.
- Brier/ECE over 30 expected claims are sample diagnostics, not calibrated guarantees.
- Contradiction dimensions and thresholds are heuristic; nuanced scope, time, exception, and domain logic may be missed or over-flagged.
- Embedding assistance for contradiction detection requires the existing local Ollama embedding configuration.


### Benchmark and budget repair follow-up — 2026-11-16

- Hosted CI run [43826700841](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43826700841) reported 87 passed and 2 failed on both Python 3.11 and 3.13. Later runs showed the same single remaining benchmark fixture failure after the memory benchmark count test was updated for the expanded corpus.
- `tests/test_benchmark.py` incorrectly expected a whole-phrase evaluator to match the substring "tests" for criterion "test". The fixture now uses the exact phrase "test was not run" to measure a genuine negation false positive.
- Added `KALDRAX_MAX_RUN_DURATION_SECONDS` (default 600 seconds) to the shared run budget. Provider HTTP timeouts are capped by the remaining run deadline.
- Failed/uncertain provider calls now consume the full reserved completion allowance as well as the reserved input estimate, avoiding free retries after a timeout that may follow provider-side generation.
- Added regression tests for wall-clock enforcement, conservative failed-call accounting, and request-timeout capping.
- Hosted CI after these fixes is pending; v0.5 must not be marked verified until both Python matrix jobs pass.


### v0.5 hosted verification result — 2026-11-16

- Verified engineering-runtime checkpoint: [891f84c9](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/commit/891f84c9a021d1c2b0cd3b6077fbb5e9fecb6f83).
- GitHub Actions run [43828149727](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43828149727) passed: Python 3.11 and 3.13 each ran 104 passing tests, the memory retrieval benchmark, evaluator acceptance benchmark, and compilation. The Python 3.13 job also ran a real Docker sandbox smoke and printed `KALDRAX_SANDBOX_SMOKE_OK`.
- Later main-branch memory quality follow-ups passed both Python matrix jobs and the Docker smoke in run [43828388469](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43828388469).
- The optional live-provider job was skipped because repository credentials/model variables were not configured; live provider behavior remains unverified.
- The deterministic evaluator regression fixture reported 0.80 accuracy, 0.714 precision, and 1.0 recall. Known false accepts remain; this is a small regression fixture, not proof of semantic reliability.
- Cost guardrails use operator-supplied estimates. Docker trusts the host daemon/kernel. Multi-agent orchestration is sequential and does not yet apply repository patches or invoke sandbox execution automatically.

### Final review follow-up

- Rewired `memory extraction-benchmark` against the current v0.5 CLI tree and shared `RunBudget`; extraction evaluation no longer uses a separate unbudgeted provider path.
- Require model-reported confidence explicitly rather than silently substituting a default score.
- Require evidence quotes to contain at least three meaningful tokens as well as the exact-candidate and 12-character constraints.
- Return a null evidence-validity rate when no claims were produced.
- Batch fixture embedding indexing in groups of 32, fall back to lexical scoring if local embedding initialization/indexing fails, and keep fixture IDs out of retrieval text.
- Normalize environment aliases (for example, prod/production) and add parameterized tests for all 13 opposition dimensions.
- Final GitHub Actions result for the newest main-branch commit remains unverified in this session; keep this milestone marked pending until the push-triggered workflow result is checked.


## 2026-11-16 — Repository-grounded memory validation

### Decisions
- Use only the public KALDRAX repository snapshot as the initial real-project dataset. Do not collect local SQLite records, runtime reports, secrets, shell environment values, private conversation content, or other private repositories.
- Keep assistant-proposed relevance judgments and privacy-screening state visibly pending. Do not call the dataset human-verified until a human reviews every query label and approves the source scope.
- Compare lexical and local-hybrid retrieval on the same judged queries. Emit paired deltas only when embedding indexing and query embedding both succeed; unavailable embeddings produce a lexical-only report.
- Keep ordinary CI credential-free. Extend only the existing manually dispatched, secret-gated provider job with live extraction evaluation.

### Changes
- Added `benchmarks/memory_retrieval_kaldrax_v1.json`: 37 source-backed memories and 36 query proposals, each with source or rationale provenance, pinned to public repository snapshot `1b50f309c7cd2f9a0dc7ec444f12fc57c25cc7d9`.
- Added `memory_benchmark_comparison.py` and `kaldrax memory benchmark-compare` with lexical baseline, optional hybrid run, aggregate/per-category/per-query deltas, and explicit unavailable states.
- Preserved source revision, annotation status, privacy-screening status, and per-query annotation rationale in benchmark reports.
- Added comparison unit tests and a corpus guard that verifies source paths and pending-review metadata.
- Added the lexical comparison baseline to regular CI and the 10-request live extraction benchmark to the manual secret-gated provider job. The manual extraction step caps each completion at 1,024 tokens and uses the shared run budget.
- Updated README, PRD, architecture, and ADR 0006.

### Verification and limitations
- GitHub source edits were committed to `main`; the newest commit still requires hosted Actions verification.
- Direct repository cloning was unavailable in this execution environment, so a local pytest/compile run could not be performed here.
- No local Ollama service or user-configured model endpoint was accessed from this session; hybrid scores and live extraction scores remain unmeasured here.
- The new dataset is public-repository-derived, but its 36 relevance labels are assistant proposals and the privacy scope is pending operator sign-off. These are not yet human-verified data.


## 2026-11-16 — Human annotation and immutable benchmark exports

### Decisions
- Implement the first validation bottleneck as a local-first terminal workflow; keep review state separate from runtime project memory and source benchmark files.
- Require per-query reviewer identity and UTC timestamp, explicit dataset-level annotation approval, and a separate privacy-scope approval.
- Export only after all relevance labels are approved or corrected and both dataset and privacy gates pass.
- Make exports versioned, hash-addressed, integrity-verifiable, and write-once. Keep incomplete sessions resumable under .kaldrax.

### Changes
- Added query-by-query annotation review with approve, reject, edit, skip, and quit/resume actions.
- Display proposed relevant memories and a complete candidate-ID index so reviewers can correct labels.
- Added independent dataset-approval and privacy-screening records.
- Added immutable versioned exports with source revision, source-file SHA-256, reviewer provenance, and a canonical content-integrity digest.
- Added benchmark report eligibility metadata; pending or tampered datasets remain exploratory-only.
- Added unit tests for modified labels, reviewer/timestamp provenance, separate approvals, rejected labels, export integrity, and exploratory-only reporting.

### Verification and limitations
- The implementation was pushed to main; hosted CI is the authoritative verification because this session cannot clone GitHub in its local execution environment.
- No query labels or privacy scope were approved by the assistant. The source-backed dataset remains pending until an operator completes the review workflow.
- Ollama hybrid comparison and live extraction quality remain unmeasured until a configured local embedding model and provider run are available.
