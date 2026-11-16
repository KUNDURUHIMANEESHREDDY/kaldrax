# ADR 0004: Local hybrid retrieval and reviewed memory intelligence

- **Status:** Accepted for v0.4
- **Date:** 2026-11-16

## Context

KALDRAX v0.3 persisted project memory but relied on lexical matching, explicit-marker extraction, and manual exact-duplicate consolidation. Semantic retrieval, freshness, approval workflows, and contradiction review are needed before memory can safely influence repeated engineering runs. KALDRAX v1 is local-first, so the memory upgrade must not require hosted vector infrastructure.

## Decision

- Add a provider-neutral EmbeddingProvider interface and a standard-library Ollama adapter using the local /api/embed endpoint. Reject non-loopback endpoints by default.
- Persist vectors and embedding model IDs in SQLite. Compare vectors only when model IDs match; require explicit reindexing after model changes.
- Combine lexical overlap and cosine similarity into a hybrid score, then scale by confidence and age-based freshness. If embedding calls fail, continue with lexical retrieval.
- Migrate v0.3 SQLite tables additively; retain existing memory records.
- Add confidence, pending/active/rejected/superseded/expired status, verification timestamp, and expiry timestamp.
- Set initial default expiry to 365 days for episodic records and 180 days for semantic records. Exclude expired records from retrieval and retain them for audit.
- Require human approval for newly extracted semantic knowledge. Rejected and pending records never enter default retrieval.
- Allow an optional LLM extractor after passing LLM-backed runs, but require exact supporting quotes copied from the candidate and store proposals as pending.
- Detect only high-overlap semantic records with explicit opposing polarity; do not treat heuristic matches as automatic truth. Approval is blocked until a human resolves a conflict.
- Resolve conflicts by retaining one record as active and superseding the other, with reviewer provenance.
- Add a versioned retrieval fixture and metrics for Recall@k, MRR, and top-1 accuracy. Benchmark in a temporary SQLite database.
- Keep all memory and embedding data local. No hosted vector database, external embedding provider, or required third-party package is introduced.

## Consequences

- KALDRAX can perform local semantic retrieval when Ollama is installed and running, while retaining lexical-only offline behavior.
- Confidence is a ranking hint, not a calibrated probability.
- The contradiction detector is intentionally narrow and must not be marketed as general semantic contradiction resolution.
- Human review reduces but does not eliminate the risk of misleading memory.
- Changing embedding models requires a reindex operation.
- The bundled retrieval fixture enables regression testing but is not sufficient evidence of production-quality recall.
- LLM extraction adds a provider request and must be included in cost expectations.
