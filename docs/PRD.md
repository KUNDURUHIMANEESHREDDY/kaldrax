# KALDRAX v0.4 Product Requirements Document

**Status:** v0.4 implementation baseline
**Category:** Local-first Autonomous Engineering Infrastructure
**Release objective:** Improve project-memory retrieval, quality controls, and human oversight without introducing hosted infrastructure.

## Vision

KALDRAX is a local-first engineering application that learns from previous project runs while keeping execution policy, storage, and memory under local control. It should reuse traceable knowledge without treating unreviewed model output as fact.

## v0.4 goals

1. Add a pluggable embedding interface and optional loopback-only Ollama adapter.
2. Persist vectors and model identity in SQLite and support explicit reindexing after model changes.
3. Combine semantic cosine similarity and lexical relevance, then adjust by confidence and freshness.
4. Benchmark retrieval using Recall@k, mean reciprocal rank, and top-1 accuracy.
5. Add confidence, verification timestamp, expiry timestamp, and review status to memory records.
6. Require human approval before extracted semantic memories become active retrieval context.
7. Extract additional candidate-backed knowledge through a strict optional LLM extractor.
8. Detect explicit positive/negative contradictions and prevent approval until a human resolves them.
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
