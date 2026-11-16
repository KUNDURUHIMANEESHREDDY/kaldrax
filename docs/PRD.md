# KALDRAX Product Requirements Document

**Status:** v0.5 implementation baseline; memory-quality track added
**Category:** Local-first Autonomous Engineering Infrastructure
**Release objective:** Improve project-memory retrieval, quality controls, and human oversight without introducing hosted infrastructure.

## Vision

KALDRAX is a local-first engineering application that learns from previous project runs while keeping execution policy, storage, and memory under local control. It should reuse traceable knowledge without treating unreviewed model output as fact.

## v0.4 goals

1. Add a pluggable embedding interface and optional loopback-only Ollama adapter.
2. Persist vectors and model identity in SQLite and support explicit reindexing after model changes.
3. Combine semantic cosine similarity and lexical relevance, then adjust by confidence and freshness.
4. Benchmark retrieval using Recall@k, Precision@k, NDCG@k, mean reciprocal rank, and top-1 accuracy.
5. Add confidence, verification timestamp, expiry timestamp, and review status to memory records.
6. Require human approval before extracted semantic memories become active retrieval context.
7. Extract additional candidate-backed knowledge through a strict optional LLM extractor.
8. Detect explainable contradiction candidates across opposing policy concepts and prevent approval until a human resolves them.
9. Provide local CLI commands to inspect, approve, reject, resolve, reindex, expire, benchmark, and consolidate memory.
10. Migrate existing v0.3 SQLite databases in place.

## Non-goals

- Hosted or distributed memory services.
- Remote embedding providers or a mandatory embedding model dependency.
- General natural-language theorem proving or contradiction resolution.
- Probabilistic confidence calibration.
- Multi-agent coordination across machines.
- Automatic destructive deletion of stale or rejected knowledge.
- Arbitrary shell/code execution or deployment automation.
- Web UI for memory review in this milestone.

## Functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| MEM-11 | Embedding provider port | Core retrieval accepts an injected embedding provider without importing provider SDKs. |
| MEM-12 | Local embedding adapter | Ollama adapter calls /api/embed and only accepts loopback URLs. |
| MEM-13 | Vector persistence | Save record vectors and model ID in SQLite; migrate v0.3 schemas in place. |
| MEM-14 | Hybrid retrieval | Combine lexical overlap and same-model cosine similarity; fall back to lexical when vectors are unavailable. |
| MEM-15 | Retrieval benchmarks | Produce Recall@k, MRR, and top-1 metrics against a versioned corpus. |
| MEM-16 | Confidence | Persist a bounded 0–1 confidence value and use it as a ranking factor. |
| MEM-17 | Freshness | Apply age decay and configurable search half-life; exclude records past expiry. |
| MEM-18 | Automatic expiry | Apply default 365-day episodic and 180-day semantic lifetimes; provide an explicit status-maintenance command. |
| MEM-19 | Approval queue | Keep automatic semantic extraction pending; require reviewer approval or rejection before retrieval. |
| MEM-20 | Evidence-backed extraction | LLM-generated proposals require exact quotes present in the candidate. |
| MEM-21 | Contradiction candidates | Detect high-overlap explicit opposing-polarity semantic statements. |
| MEM-22 | Conflict resolution | Prevent approval of conflicted pending records until a human chooses one side; supersede the rejected side with provenance. |
| MEM-23 | Local operator controls | CLI exposes search, review, conflicts, resolve, reindex, expire, benchmark, and consolidate. |
| MEM-24 | Backward migration | Existing SQLite memory records remain readable and default to active state after schema migration. |
| MEM-25 | Local-first privacy | Embeddings use loopback Ollama; no hosted vector DB or cloud memory service is introduced. |

## Quality attributes

- **Safety:** pending memories are excluded from default retrieval; memories cannot alter evaluation policy or task acceptance criteria.
- **Auditability:** all proposals retain source run/event references, evidence quotes, reviewer identity, and conflict resolutions.
- **Reliability:** provider failures fall back to lexical retrieval; embeddings are validated for count, dimension, and finite numeric values.
- **Portability:** Python 3.11+ and standard library; Ollama is optional.
- **Data integrity:** v0.3 SQLite databases migrate additively; reindexing is explicit after model changes.
- **Privacy:** local embedding adapter rejects non-loopback hosts; local app controls storage location.
- **Maintainability:** embedding, extraction, and storage remain behind independent interfaces.

## v0.4 success metrics

- Existing v0.3 records survive migration without data loss.
- Hybrid retrieval can return semantically relevant results with no lexical overlap when vectors are available.
- Provider failures retain lexical retrieval behavior.
- Extracted knowledge cannot enter default retrieval without approval.
- Conflicting pending facts cannot be approved until resolved.
- Expired records are not retrieved.
- Retrieval benchmark metrics are reproducible on the bundled fixture dataset.
- Existing v0.3 run/executor/evaluator tests remain green.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Embedding model changes vector space | Persist model identity and require reindex before querying with new model vectors. |
| Ollama is not running | Persist records without vectors and use lexical fallback. |
| Confidence is over-interpreted | Document that it is a ranking heuristic, not calibrated probability. |
| Contradiction heuristic misses nuanced claims | Require explicit polarity and high token overlap; keep human approval as the final decision. |
| LLM extraction creates inaccurate facts | Require exact candidate quote, strict schema validation, and pending approval. |
| Old memories become stale | Apply type-specific expiry and ranking decay; preserve audit data. |
| Benchmark is too small | Treat bundled data as a regression fixture; add real project query sets before claiming production retrieval quality. |


## v0.5 goals: budgeted execution and engineering runtime

1. Enforce shared provider-call, input-token, output-token, and total-token ceilings across all model roles in one operation.
2. Provide optional estimated monetary ceilings using operator-supplied input/output rates.
3. Add an evaluator benchmark with repeatable adversarial fixtures and standard classification metrics.
4. Add a credential-backed provider smoke command for executor and evaluator endpoints.
5. Make the live provider smoke workflow manual and secret-gated; normal CI remains credential-free.
6. Add Docker-backed Python execution with network, filesystem, CPU, memory, PID, timeout, and output restrictions.
7. Add a bounded planner-builder-reviewer workflow with final independent evaluation.
8. Share budgets across planner, builder, reviewer, evaluator, and memory-extraction requests.
9. Preserve existing local memory intelligence, human approval, hybrid retrieval, and memory benchmark commands.
10. Keep tests and deterministic benchmarks independent of hosted credentials and Docker availability; hosted CI additionally runs an actual Docker smoke test.

## v0.5 functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| RT-01 | Shared model-call budget | All LLM roles consume one shared call ledger. |
| RT-02 | Token ceilings | Prompt estimates and completion ceilings are reserved before each request; returned usage settles the ledger. |
| RT-03 | Cost ceiling | Optional preflight estimated cost enforcement requires both input and output rates. |
| RT-04 | Usage reporting | Run/team JSON includes provider calls, input/output/total token counts, and estimated cost when configured. |
| RT-05 | Evaluator benchmark | Report accuracy, precision, recall, F1, confusion counts, and model/evaluator errors. |
| RT-06 | Provider smoke | Test executor completion and evaluator schema/evidence handling using real configured endpoints. |
| RT-07 | Secret-gated CI | Live smoke occurs only on manual dispatch and only when required secrets/variables exist. |
| RT-08 | Sandboxed Python | Execute one Python file in Docker without network or arbitrary host mounts, with resource/time/output limits. |
| RT-09 | Team workflow | Run planner, builder, reviewer, and final evaluator sequentially for a bounded cycle count. |
| RT-10 | Independent decision | Team success requires reviewer approval and evaluator pass against the original task. |
| RT-11 | Team provenance | Persist role traces in project- and agent-scoped memory. |
| RT-12 | Offline unit verification | Core tests and benchmarks run without real provider credentials, Ollama, or Docker. |
| RT-13 | Hosted sandbox verification | CI pre-pulls the fixed image and executes a smoke file through the Docker sandbox command. |

## v0.5 limitations

- A UTF-8 byte count is a conservative prompt-size estimate, not a tokenizer-exact count.
- Monetary estimates depend on operator-entered rates and do not guarantee provider billing totals.
- Provider-reported over-budget usage can only be detected after the request has been processed.
- The evaluator fixture is small and intentionally reveals known deterministic false positives; broader domain-specific benchmark sets remain necessary.
- The sandbox executes a single Python file and relies on Docker plus the host kernel; repository patching, dependency provisioning, and whole-project test execution are not integrated yet.
- Team orchestration is local and sequential, not a distributed multi-agent scheduler.

## v0.5 memory-quality track

### Goals

1. Replace the five-query retrieval regression sample as the default with a curated engineering corpus of 40 memories and 42 relevance-judged queries, split across 15 engineering workload categories.
2. Report Recall@k, Precision@k, NDCG@k, MRR, top-1 accuracy, and category-level breakdowns from an isolated temporary SQLite database.
3. Reject malformed benchmark references, duplicate memory IDs, and relevance judgments pointing to memories absent from the corpus.
4. Detect contradiction candidates beyond negation using opposing policy dimensions such as allow/deny, public/private, local/cloud, sync/async, required/optional, retain/delete, and encrypted/plaintext.
5. Apply subject-overlap and environment-scope checks; optionally use a configured local embedding provider to discover paraphrased candidates, with lexical fallback when embeddings fail.
6. Preserve human review as the sole conflict-resolution authority. Detection must never automatically supersede or activate a memory.
7. Evaluate extraction on 10 annotated engineering scenarios with 30 expected claims, reporting precision, recall, F1, false positives, false negatives, and evidence-quote validity.
8. Treat extractor confidence as a reported probability estimate and measure sample calibration using Brier score and expected calibration error (ECE).
9. Keep benchmarks offline and credential-free except for the optional live extraction benchmark, which makes one configured model request per case.

### Functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| MEM-26 | Engineering retrieval corpus | Versioned synthetic-curated corpus includes at least 35 memories and 40 annotated queries across at least 10 workload categories. |
| MEM-27 | Retrieval metrics | Report Recall@k, Precision@k, NDCG@k, MRR, top-1, and category breakdowns; reject unknown relevance IDs. |
| MEM-28 | Opposition-aware conflict candidates | Detect supported opposite-polarity dimensions beyond negation and preserve project/agent/environment scoping. |
| MEM-29 | Semantic conflict recall | When a local embedding provider is configured, permit semantically similar paraphrases to enter candidate review; provider failure falls back to lexical matching. |
| MEM-30 | Human resolution | All detected pairs remain review candidates; no automated conflict resolution or approval. |
| MEM-31 | Extraction benchmark | Score predictions against one-to-one annotated expected claims and report precision, recall, F1, FP/FN, and evidence validity. |
| MEM-32 | Confidence calibration | Report Brier score, ECE, and bin-level empirical accuracy on annotated extraction results. |
| MEM-33 | Evidence quality | Require extraction evidence to be an exact candidate substring of at least 12 characters and three tokens. |
| MEM-34 | Confidence semantics | Prompt the extractor for a conservative claim-correctness probability and preserve the model-reported value as provenance; approval remains a separate state. |

### Success criteria

- The 40-memory/42-query retrieval corpus validates and produces repeatable ranking metrics using only local SQLite and optional local Ollama.
- Query categories are separately measurable so weak workload groups are visible rather than hidden by one overall average.
- A set of explicit opposing-policy examples and paraphrased examples are caught as candidate conflicts, while unrelated statements and disjoint environment scopes are not paired by tests.
- Conflict detection remains a review gate: no automatic resolution is introduced.
- The extraction benchmark can quantify missing claims, unsupported extractions, weak evidence quotes, and over/under-confidence against its annotated cases.
- Existing memory migration, approval, retrieval, CLI, evaluator, budget, and sandbox tests remain green.

### Evaluation boundaries and risks

- Both bundled memory-quality datasets are synthetic, manually curated fixtures, not production engineering traces or telemetry.
- Extraction matching uses explicit `match_terms` annotations. It is inspectable and deterministic but can miss valid paraphrases or overstate a match if annotations are too broad.
- Brier score and ECE describe only the evaluated sample. Ten cases and 30 expected claims do not establish population calibration.
- Contradiction detection remains heuristic. The dimensions are not a natural-language inference model and can miss context, exceptions, temporal changes, or domain-specific definitions.
- Embedding-based similarity can increase false positives as well as recall. Every pair still requires human inspection.
- Live extraction benchmarking sends each candidate to the configured LLM provider and incurs provider cost. It is opt-in and separate from CI.
