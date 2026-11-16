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


### CI correction
- The first annotation-workflow CI run exposed a SemVer-validation regex escaping error; 130 other tests passed on Python 3.11 and 3.13.
- Corrected the pattern to use explicit dot character classes and strengthened the write-once export test to repeat the export from the persisted review session.
- Verification is pending the next hosted CI run.


### CI fixture correction
- The second hosted run passed 132 tests and exposed one test-input ordering error in the privacy-approval scenario. The workflow correctly required the explicit privacy action before its typed confirmation.
- Corrected the fixture sequence; hosted verification is pending.


## 2026-11-16 — v0.6 repository build-test-review runtime

### Decisions
- Keep repository-aware engineering separate from the existing prose-only team workflow.
- Require a clean Git repository root and snapshot one immutable base HEAD per run.
- Never mount the operator's working checkout into Docker. Stage the candidate patch in a temporary Git workspace, then execute tests against a second disposable copy.
- Accept unified Git diffs only; reject unsafe/traversal/credential/runtime paths, binary changes, renames, submodules, and mode changes.
- Make repository writes opt-in with the apply flag; dry-run is the default. Applying must re-check cleanliness and the original HEAD and never creates a commit.
- Require at least one discovered test for unittest/pytest; a zero-test green exit is not accepted.
- Keep verification commands allowlisted to Python modules (unittest, pytest, compileall). A custom sandbox image must be pre-pulled and is configured by the operator.

### Changes
- Added workspace.py for bounded source/test-prioritized snapshots, secret filtering, patch validation, isolated staging, and stale-HEAD-safe application.
- Added workspace_sandbox.py for a second disposable project copy and no-network, unprivileged, resource-limited Docker verification.
- Added engineering.py for repository-aware planner/builder/reviewer/evaluator coordination, structured evidence, retry feedback, trace/report output, and explicit application.
- Extended kaldrax team with workspace, opt-in apply, verifier-module/arguments, timeout, and sandbox-workspace options. Existing prose-only operation remains unchanged.
- Added KALDRAX_SANDBOX_IMAGE for a pre-pulled image containing Python and the selected verification module.
- Added a real CSV parsing repair integration fixture that begins with failing tests and verifies quoted-comma and blank-row behavior through Docker before applying.

### Verification
- Focused local test harness: 20 passed, 1 Docker integration test skipped because this execution environment has no Docker CLI.
- Python compilation of the new modules and CLI passed.
- The full repository matrix and actual Docker integration are delegated to push-triggered GitHub Actions; do not mark hosted verification complete until those jobs finish.
- Live provider validation remains credential-gated and is not implied by deterministic test clients used by the CSV integration fixture.

### Risks and limitations
- Snapshot limits are 240 files, 48 KB/file, and 45 KB aggregate; omitted files cannot be understood or patched reliably.
- Docker isolation trusts the Docker daemon, host kernel, and pre-pulled image; it is not a microVM.
- The default Python image ships with standard-library unittest; pytest and project-specific dependencies require a custom image pre-pulled on the host.
- The apply flag writes a patch to the user's working tree but does not commit or push it. The user remains responsible for inspecting and committing accepted changes.
- The multi-agent sequence remains serial. It does not dispatch independent parallel worker processes or execute arbitrary shell commands.


### Hosted verification — repository engineering workflow

- Main-branch commit [61e690c](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/commit/61e690c0873f254f41c3ebbbd8babfaab4e2b484) passed GitHub Actions run [43841362755](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43841362755).
- Python 3.11: 154 passed, 1 skipped; package install, both memory benchmarks, evaluator acceptance benchmark, and compilation passed.
- Python 3.13: 154 passed, 1 skipped; package install, both memory benchmarks, evaluator acceptance benchmark, Docker single-file smoke, repository patch integration, and compilation passed.
- The Docker-backed CSV repository integration test passed (1 passed). It exercised the actual repository coordinator and disposable Docker workspace against a real failing CSV parser fixture: preserving quoted commas, ignoring blank rows, reviewing the patch, independently evaluating the evidence pack, and applying the accepted patch to the fixture checkout.
- The integration uses deterministic fake model responses for planner/builder/reviewer to avoid depending on API credentials. It verifies the full orchestration path and real Docker test execution, but it is not a live-provider agent quality result.
- The optional live-provider smoke was skipped because KALDRAX_API_KEY and model variables were not configured. Live provider behavior therefore remains unverified.
- An initial CI run exposed a CLI merge regression: the repository-workspace patch had replaced the concurrently added memory benchmark-compare command. The CLI integration was rebased onto the updated main implementation in commit 61e690c; the subsequent full matrix passed.
- Local focused verification: 20 passed, 1 Docker integration test skipped because Docker is unavailable in the local execution environment. Hosted Python 3.13 CI ran that integration successfully.


### Final CI after planner-boundary regression test

- Commit [abf04ae](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/commit/abf04ae2f02ced1ea7207484add48051a523386e) completed workflow [43841989514](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43841989514) successfully.
- Python 3.13: 155 passed, 1 skipped. Docker single-file smoke passed. The repository engineering integration test passed separately (1 passed), and source/test compilation passed.
- Python 3.11: full test suite, memory retrieval, lexical-versus-hybrid benchmark baseline, evaluator benchmark, and compile checks passed. Docker-only steps are intentionally limited to Python 3.13.
- Added a regression assertion that the planner is explicitly told it receives only the manifest and cannot inspect source contents; builder remains the role with the bounded source snapshot.
- The optional live provider job remains skipped until operator-provided API credentials and model variables are configured.


## 2026-11-16 — Contradiction and extraction evaluation expansion

- Added category-level extraction precision, recall, F1, and FP/FN counts.
- Added a labeled contradiction-pair evaluator with TP/FP/FN/TN, precision, recall, F1, and category summaries.
- Added a synthetic contradiction fixture covering opposing policy dimensions, environment-specific cases, and unrelated vocabulary. Labels remain assistant-proposed and exploratory-only pending human review.
- Added `kaldrax memory contradiction-benchmark` with optional JSON report output.
- No live Ollama or configured LLM scores are claimed; provider measurements still require a configured environment.


## 2026-11-16 — Automated memory evaluation report and v0.6 release gate

### Decisions
- Keep ordinary CI deterministic, credential-free, and exploratory with respect to unreviewed human labels.
- Make release eligibility a separate strict profile; a green regular CI run is not a v0.6 release approval.
- Require a validated source-backed retrieval export, a real local-hybrid comparison, live extraction metrics, and hash-bound human review of contradiction/extraction labels for release.
- Keep release thresholds in a versioned JSON file and include its SHA-256 plus benchmark dataset SHA-256 values in every report.
- Treat human review as an explicit operator attestation; never upgrade assistant-proposed labels automatically.

### Changes
- Added `kaldrax memory quality-report` to aggregate lexical/hybrid retrieval, contradiction detection, live extraction, confidence calibration, dataset provenance, fingerprints, reproducibility metadata, and threshold results into JSON and Markdown.
- Added separate CI and release threshold profiles. Regular CI enforces deterministic retrieval and contradiction regression floors. The release profile requires stronger metrics and complete evidence.
- Added `kaldrax memory quality-approve`, an interactive, write-once human attestation for contradiction and extraction labels. The approval is bound to exact retrieval, contradiction, and extraction dataset hashes; changed data invalidates it.
- Extended CI to publish the machine-readable and human-readable evaluation report as an Actions artifact.
- Added a v0.6 tag-only release job that requires hybrid retrieval, configured live extraction, reviewed source-backed retrieval labels/privacy scope, hash-bound label review, and release thresholds.
- No human approvals, provider runs, or hybrid measurements were manufactured during implementation.

### Verification and remaining gates
- Push-triggered hosted CI is the authoritative test run; local repository cloning is unavailable in this execution environment.
- Release readiness remains blocked until an operator completes the retrieval annotation/privacy workflow, reviews contradiction and extraction labels using `quality-approve`, configures Ollama embeddings and the live extraction provider, and records reports passing the release thresholds.
- A tag job reports and fails closed on missing evidence, but repository tag/release protection must require the named release-gate check to prevent an administrator from bypassing the workflow.


### Release evidence integrity follow-up
- Strengthened quality-review approval validation to require unique, non-empty case IDs and exact ordered coverage of every contradiction and extraction case, even if an edited manifest is rehashed.
- Require a timezone-aware review timestamp.
- Documented that the approved retrieval export and the hash-bound review manifest must be committed to the tagged revision; local-only files cannot satisfy a hosted release check.
- Documented the need for a runner-reachable Ollama endpoint and a GitHub tag/release ruleset. The GitHub ruleset listing returned no rulesets; branch-protection details were inaccessible to the connected integration, so repository enforcement settings were not changed.


### Release sample-size guardrails
- Added explicit minimum evaluation sample sizes to the strict release profile: retrieval query count, contradiction total and class balance, extraction case/claim count, and confidence observations.
- The current synthetic contradiction/extraction fixtures intentionally fail these release minimums (8 pairs and 10 extraction cases); expand them with independently reviewed examples before v0.6.
- Threshold values and minimum sample sizes are initial policy floors, not population-level statistical guarantees; recalibrate them against a larger held-out corpus.


### Release dataset selection
- The tag-only workflow now accepts the committed, reviewed retrieval export path through the `KALDRAX_RETRIEVAL_DATASET` repository variable; unset defaults to the canonical benchmark path.
- Documentation now requires the same file path for local attestation creation and the GitHub tag-run report, preventing accidental approval/report path mismatches.

## 2026-11-16 — Desktop workflow bridge and repository workspace integration

### Delivered
- Added repository CLI commands for Git status, bounded text-file listing, UTF-8 file read with SHA-256, and explicit single-file apply using a hash precondition.
- Repository file access excludes private/runtime/build paths, rejects traversal and symlink components, and caps inspection/edits at 1 MB.
- Existing-file replacement creates a backup under `.kaldrax/desktop-backups/`, checks both runtime and backup roots against symlinks, writes a sibling temporary file, fsyncs, then atomically replaces the target.
- Added repository-aware team operation progress and cancellation. Cancellation is checked after each model role and immediately before patch application; the Docker workspace runner kills the active container when the cancellation file appears.
- Repository team reports include an explicit `cancelled` marker. Dry-run remains the default; apply still requires disposable Docker verification, reviewer approval, independent evaluation pass, and a clean/base-commit recheck. The engine does not commit or push.
- Added CLI `--cancel-file` support for team and single-file sandbox operations.
- Connected the desktop Memory, Team Runs, Sandbox and Repository screens to named Tauri commands. The team UI exposes the opt-in repository workflow and distinguishes cancelled repository-team results.
- Updated desktop README, design/UX contracts and integration record. The Downloads desktop directory is not a Git repository, so its source and built installers remain local files.

### Verification
- Python test suite: **170 passed, 4 skipped**. Windows symlink-permission guards skip when symlink creation is unavailable.
- `git diff --check` and staged diff whitespace checks passed.
- Direct repository CLI smoke passed in a disposable temporary Git repository: status, file listing, SHA-256 read, hash-guarded edit, backup existence and dirty status were verified.
- CLI help confirmed `--cancel-file` on team and sandbox commands.
- Desktop TypeScript/Vite production build passed.
- Oxlint passed with 0 errors; 22 warnings remain, largely existing template React effect/Fast Refresh warnings and effect-driven screen loading warnings.
- Rust `cargo fmt --check` and `cargo check` passed.
- Windows Tauri release build passed. MSI: 3.14 MiB. NSIS installer: 2.12 MiB.

### Boundaries and remaining risks
- The Docker Sandbox screen executes one selected Python file; repository-team mode separately stages a unified patch in a disposable copy and runs one selected verification module.
- Docker still trusts the host daemon, kernel and pre-pulled image. No network, arbitrary dependency provisioning, commit, push or deployment is introduced.
- Repository edits are local, single-file, explicit and hash-preconditioned. Repository-team patch application is also local and explicit, after all verification/review/evaluation gates.
- A provider request already submitted before cancellation may still finish or incur provider cost; cancellation prevents later role calls and patch application.
- Browser interaction QA performed earlier used mocked Tauri IPC. A complete native end-to-end UI click-through with a configured live LLM provider and Docker daemon remains unverified.

## 2026-11-16 — Resumable contradiction and extraction label review

### Changes
- Added `kaldrax memory quality-review` for per-case human review of contradiction and extraction labels.
- Contradiction reviewers can accept or toggle each proposed conflict label; extraction reviewers can accept or replace each expected-claims list.
- Persisted review progress in a source-hash-bound local session, with reviewer identity and timestamps per case. A changed source dataset invalidates the session.
- Require separate explicit dataset approvals before creating immutable, SHA-256-addressed reviewed exports.
- Automatically create the hash-bound review manifest against the exact reviewed exports and retrieval dataset path.

### Verification and limitations
- Added tests for label corrections, export metadata, resumable sessions, and changed-source rejection.
- Human review is still an operator action; no labels were reviewed or approved during implementation.
- Reviewed exports are generated only when an operator runs the command and completes every case and dataset approval.
- Hosted CI is the authoritative verification for this change.


## 2026-11-16 — Contradiction and extraction candidate corpus expansion

### Decisions
- Meet the strict release sample-size floors with a balanced contradiction candidate corpus and a larger extraction candidate corpus.
- Keep every existing and newly generated label explicitly pending human review. Corpus growth must not create or imply reviewer approval.
- Treat the generated examples as synthetic candidate data, not production observations or independent evaluation evidence.
- Increase only the explicitly invoked provider-smoke and strict release budgets to accommodate 30 extraction cases at the existing 1,024-token per-completion cap.

### Changes
- Expanded contradiction candidates from 8 to 50 pairs, balanced at 25 proposed conflicts and 25 proposed non-conflicts. Added 42 assistant-generated synthetic pairs with distinct case IDs and case-level pending-review metadata.
- Expanded extraction candidates from 10 to 30 cases and from 30 to 70 proposed expected claims. Added 20 assistant-generated synthetic candidates, each with two source-grounded proposed claims.
- Added dataset-level expansion provenance and explicit pending status to every case in both corpora. No reviewer identity, timestamp, dataset approval, or human-reviewed status was added.
- Added corpus regression tests for sample counts, contradiction class balance, unique IDs, pending-review provenance, and extraction-label term grounding.
- Raised the manually dispatched provider-smoke and tag-only release budgets to 40 provider calls, 36,000 completion tokens, and 100,000 total tokens so the 30-case extraction benchmark can run without silently exceeding its bounded budget.

### Verification and limitations
- GitHub Actions run [43869970403](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43869970403) passed for commit [e829858](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/commit/e829858e6fe3e9a92af65925673671eb60f82d19).
- Python 3.11 and 3.13 each completed the full suite with 180 passed and 1 skipped. The Python 3.13 job also passed the Docker sandbox smoke, repository patch integration, compilation, and CI-profile memory quality report.
- Every sample-size check passed: 50 contradiction pairs (25 positive, 25 negative), 30 extraction cases, and 70 expected claims. The unreviewed contradiction benchmark reported 23 true positives, 0 false positives, and 2 false negatives (precision 1.0, recall 0.92, F1 0.9583); the two missed candidates are search-index-execution and customer-session-retention. This remains exploratory-only because labels are pending human review.
- The overall CI-profile report passed, while release readiness remained false. Human retrieval/privacy approval, contradiction/extraction label review, hybrid retrieval evidence, live extraction, and 30 confidence observations remain outstanding.
- The optional live-provider smoke and tag-only release gate were skipped; no live provider requests, Ollama measurements, extraction metrics, or confidence-calibration measurements were performed by this change.


## 2026-11-16 — Hosted Docker verification refresh

### Verification
- GitHub Actions run [43871052469](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43871052469) passed on current main commit `4a9dcb3`.
- Python 3.11 completed the full Python suite, retrieval benchmark, source-backed lexical/hybrid comparison, evaluator benchmark, and compile check. Docker-specific steps and the CI-profile memory report were skipped for Python 3.11 by the workflow matrix conditions.
- Python 3.13 completed the full Python suite, retrieval and evaluator benchmarks, Docker sandbox smoke test, repository patch/Docker integration test, compile check, and CI-profile memory quality report.
- The provider smoke job was skipped because this was a push event, not a manually dispatched workflow. The v0.6 release gate was skipped because this was not a v0.6 tag.

### Updated environmental status
- Docker sandbox execution and repository-team patch verification are now proven on the hosted Ubuntu runner. The local Windows Docker Desktop Linux engine remains unavailable, so local Docker execution and a complete native desktop end-to-end click-through remain unverified.
- Live provider execution remains unverified until the operator configures `KALDRAX_API_KEY`, `KALDRAX_MODEL`, and `KALDRAX_EVALUATOR_MODEL` and dispatches the provider workflow.
- The last recorded desktop lint run had 0 errors and 22 warnings, primarily React Fast Refresh/export warnings and effect-driven screen-loading warnings. Desktop lint is not currently a GitHub Actions step, so the warning count has not been freshly rechecked by hosted CI.
- A green regular CI run is not v0.6 release approval. Human dataset review/privacy approval, live-provider evidence, hybrid retrieval measurements, and confidence-calibration evidence remain separate release gates.


## 2026-11-16 — Hosted embeddings; no local model runtime

### Decision
- KALDRAX will not install, download, launch, or depend on local language or embedding models. Hosted model APIs are configured later, after API-independent implementation and verification are complete.
- Keep SQLite local and preserve lexical retrieval when hosted embedding credentials/model settings are absent.
- Use an OpenAI-compatible HTTPS embeddings endpoint as the first hosted embedding adapter. The embedding API key can be dedicated or fall back to the existing KALDRAX_API_KEY.

### Changes
- Replaced the loopback-only Ollama embedding adapter with a standard-library hosted POST /embeddings adapter.
- Require HTTPS, reject URL credentials/query/fragment, redact API keys from HTTP error details, bound response size, and validate vector count, indices, numeric values, finiteness, and consistent dimensions.
- Wired KALDRAX_EMBEDDING_MODEL, KALDRAX_EMBEDDING_API_KEY, KALDRAX_EMBEDDING_BASE_URL, and timeout configuration into the CLI.
- Updated environment examples, user documentation, memory error messages, and the release workflow to use hosted embedding configuration.
- Kept embedding use opt-in; no API key is needed for lexical retrieval, the offline demo, or mocked adapter tests.

### Verification
- Added deterministic fake-HTTP tests for authentication headers, request payloads, result ordering, HTTPS enforcement, empty inputs, malformed vectors, response dimensions, duplicate indices, and API-key redaction.
- Live provider requests and hosted hybrid retrieval measurements remain unperformed until the operator configures credentials and dispatches the provider workflow.


### Hosted-only chat transport hardening
- Restricted the OpenAI-compatible chat client to HTTPS URLs with no embedded credentials, query, or fragment, matching the hosted embeddings adapter.
- Updated the README to remove local-model endpoint guidance.
- Added configuration regression coverage for plain HTTP and credential/query/fragment URL rejection.


### Desktop CI regression repair
- Moved the ProjectDetail page's memoized current-date hook above the missing-project early return. This preserves its value and dependencies while ensuring React hooks execute in the same order on every render.
- The repair addresses the conditional `useMemo` error reported by Oxlint; no other desktop behavior was changed.


### Desktop TypeScript build repairs
- StockAdjustForm is rendered only by its open-state wrapper; set the nested Modal's visibility to true instead of accidentally resolving the imported Tauri file-picker function named `open`.
- Added the missing memoized team-report refresh callback used by TeamRunsPage's Refresh action.
- These changes resolve the TypeScript errors found by the production build; normal initial report loading remains unchanged.


## 2026-11-16 — Desktop lint cleanup and hosted verification

### Decisions
- Keep Oxlint rule configuration enabled and unchanged; resolve Fast Refresh warnings by separating hooks, contexts, and pure UI helpers from component modules.
- Reset modal form state through keyed form mounts rather than synchronous state updates inside effects.
- Keep async page-loading effects cancellable and separate from stateful user-triggered handlers.
- Capture page clock references outside render to satisfy React purity checks.

### Changes
- Added a required desktop CI job that runs `npm ci`, `npm run lint`, and `npm run build` on Node.js 24.
- Split `usePageTitle`, `useRailBadges`, `useOutsideClose`, `useToast`, `useItemOptions`, and `useApp` into hook modules; moved toast context and shared UI helper functions/types into non-component modules.
- Replaced the donut chart's render-local mutable offset with an immutable reduction.
- Reworked stock adjustment, material consumption, and request rejection forms to reset on keyed mount; reinitialized Settings drafts when persisted settings change.
- Refactored memory, team-report, and repository loading effects to use cancellable asynchronous requests.
- Moved the AppStore state-ref synchronization to a layout effect.

### Verification
- GitHub Actions run [43879830327](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/actions/runs/43879830327) passed for commit [b1cf2ca](https://github.com/KUNDURUHIMANEESHREDDY/kaldrax/commit/b1cf2ca2eacf9cc18654bb46b74cc4c6dcc6404d).
- Desktop `npm run lint`: **0 warnings and 0 errors**. No lint rules were disabled or weakened.
- Desktop `npm run build`: TypeScript project build and Vite production build passed.
- Python 3.11 and 3.13 full suites, retrieval/evaluator benchmarks, and source compilation passed.
- Python 3.13 also passed the real hosted Docker sandbox smoke test, repository patch/Docker integration test, and CI-profile memory quality report.
- Python 3.11 Docker-specific steps and the optional CI-profile memory report were skipped by design.
- Live provider smoke was skipped because this was a push-triggered run; the v0.6 release gate was skipped because this was not a v0.6 tag.

### Remaining environmental and release gates
- Hosted Docker execution and repository-team patch verification are verified. Local Windows Docker Desktop/Linux-engine execution and native desktop end-to-end testing remain locally unverified.
- Live chat/embedding provider execution still needs operator-configured hosted API credentials and a manually dispatched provider check.
- Regular CI success is not v0.6 release approval. Human-reviewed retrieval/privacy evidence, contradiction/extraction label approval, live embedding/retrieval measurements, and live extraction/calibration evidence remain separate release requirements.

## 2026-11-16 — Dependency-aware parallel orchestration

### Decisions
- Add a distinct task-DAG workflow rather than changing the established sequential planner → builder → reviewer → independent evaluator or repository patch-verification contracts.
- Keep decomposition bounded to 32 tasks, concurrency to 8 workers, and retries to 5 attempts maximum. A run shares the existing thread-safe provider budget across planner, workers, and escalation calls.
- Persist task state atomically in a graph-fingerprint-bound JSON checkpoint. Never reuse checkpoint results if the decomposition fingerprint changes.
- Retry only transient transport/provider failures with capped exponential backoff. Permanent failures are escalated for planner diagnosis and remain failed until an operator explicitly retries them. Descendants of failed tasks are blocked; unrelated tasks continue.
- Keep all model completions on configured hosted HTTPS providers. No local LLM runtime or API credentials are needed for deterministic implementation tests.

### Changes
- Added `src/kaldrax/orchestration.py`: strict task graph validation, bounded LLM decomposition, dependency-aware parallel scheduling, per-task attempts and outputs, retry classification/backoff, failure escalation, progress events, and atomic checkpoint persistence/resumption.
- Added `kaldrax orchestrate` with worker/attempt bounds, checkpoint selection, fresh-run and retry-failed controls, artifact output, and JSONL progress events.
- Dependent workers receive completed outputs from their prerequisite tasks. Independent tasks run concurrently; failures do not cancel unrelated work.
- Once every graph node succeeds, task outputs are aggregated in graph order and passed through the independent reviewer and evidence-backed LLM evaluator. The CLI reports success only when task execution, reviewer approval, and evaluator acceptance all pass.
- Added `tests/test_orchestration.py` for malformed graphs/planner output, dependency cycles, concurrency, dependency blocking, transient retries, escalation, checkpoint resume, graph mismatch, explicit failed-task retry, and the final reviewer/evaluator gate.
- Documented the new workflow and its boundaries in README.md.

### Verification
- Focused orchestration, existing agent, and repository-engineering tests after the final reviewer/evaluator integration: 26 passed.
- Full local suite on the connected Windows device after rebasing onto the latest `origin/main` and before the final reviewer/evaluator integration: 196 passed, 4 skipped.
- The final full-suite rerun is currently blocked during collection by a separate, uncommitted live-validation change in the working tree: `src/kaldrax/live_validation.py` imports `OllamaEmbeddingProvider`, which is not exported by the current `src/kaldrax/embeddings.py`. The concurrent live-validation files and edits were left untouched and excluded from this commit.
- `python -m compileall -q src/kaldrax/orchestration.py src/kaldrax/cli.py tests/test_orchestration.py` and `git diff --check` passed.
- Live provider calls were not run. Hosted CI, Docker-backed integration, and live provider behavior remain separate verification layers.

### Limitations and risks
- The DAG runner aggregates task outputs and runs the separate reviewer and evidence-backed independent evaluator, but does not synthesize or apply repository patches or run sandbox verification over a repository checkout. Use `kaldrax team --workspace ...` for the established repository patch/review/sandbox/evaluator/apply gates.
- A resumed run invokes decomposition again; if the planner produces a different graph, the checkpoint fingerprint check fails closed rather than mixing work. Use `--fresh` to intentionally start over.
- Interrupted in-flight provider requests have unknown completion/billing state. Resume is at-least-once for those tasks, within the remaining attempt and shared run budgets.

## 2026-11-16 — Live-provider validation harness

### Decisions
- Keep live provider validation opt-in and credential-gated; ordinary CI remains deterministic and does not require paid API access.
- Require distinct planner, builder, reviewer, and evaluator model identifiers for the full Team Run.
- Apply provider-generated patches only to a disposable temporary Git fixture. Never use the user's working checkout as the live-validation target.
- Keep local SQLite retrieval and Docker availability checks independent of provider credentials so blocked live-provider runs still produce useful infrastructure evidence.
- Record provider role/model, per-call latency, failure type, token usage, shared budget, reviewer/evaluator decisions, changed paths, and Docker verification output. Never record API keys, prompts, or completions.

### Changes
- Added `kaldrax validate-live` and `src/kaldrax/live_validation.py`.
- The command validates all four role configurations, checks SQLite Memory persistence/retrieval and project isolation, and validates Docker daemon availability.
- With credentials configured, it executes a real planner → builder → reviewer → independent evaluator repository task, applies the patch to a disposable Git fixture, and requires Docker test success before reporting PASS.
- If hosted embeddings are configured, the Memory preflight also requires a successful semantic embedding/retrieval round trip; otherwise it explicitly reports lexical retrieval.
- Added regression coverage for provider telemetry, secret redaction, missing/duplicate configuration, and a Docker-backed end-to-end harness test using deterministic fake model responses.
- Updated `.env.example`, README instructions, and the manual GitHub Actions provider workflow to run the full validation and upload its JSON evidence when all four model variables and the API secret are configured.

### Verification
- Full local Python suite with `KALDRAX_RUN_DOCKER_INTEGRATION=1`: **199 passed, 3 skipped**.
- The Docker-backed repository engineering integration passed; the new full validation-harness integration also passed using deterministic fake provider responses and the actual Docker sandbox.
- Python source/test compilation passed.
- Local Docker Desktop Linux engine was reachable (server 29.9.2). Pulled `python:3.13-slim` for the isolated workspace tests (image digest `sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90`).
- `kaldrax validate-live` passed the local Docker preflight and SQLite lexical retrieval/project-isolation checks, then correctly returned **BLOCKED (exit 2)** because no `KALDRAX_API_KEY` or four role model variables are configured in this Windows environment. No live provider requests were made and no provider spend occurred.
- `git diff --check` passed.

### Remaining gate
- Configure `KALDRAX_API_KEY`, `KALDRAX_PLANNER_MODEL`, `KALDRAX_MODEL`, `KALDRAX_REVIEWER_MODEL`, and `KALDRAX_EVALUATOR_MODEL`, then run `kaldrax validate-live` to obtain the first genuine live-provider Team Run result. A passing fake-provider integration test is not live-provider evidence.
