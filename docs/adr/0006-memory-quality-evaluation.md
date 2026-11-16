# ADR 0006: Memory quality evaluation and opposition-aware conflict candidates

- **Status:** Accepted
- **Date:** 2026-11-15
- **Scope:** Memory retrieval, contradiction candidate detection, extraction evaluation, and confidence measurement

## Context

The v0.4 memory foundation provided hybrid lexical/vector retrieval, human approval, exact evidence quotes, and a small five-query regression fixture. Three important quality gaps remained:

1. Five queries were too few and too narrow to reveal ranking failures across engineering workloads.
2. Conflict detection relied on explicit negation and near-identical token sets, missing common opposing policy concepts and paraphrases.
3. Extractor confidence was a model-provided 0–1 value with no quality benchmark or calibration measurement.

These capabilities need evaluation without introducing hosted vector infrastructure or storing benchmark data in a user's project memory database.

## Decisions

### Retrieval evaluation

- Add a versioned synthetic-curated dataset with 40 engineering memories and 42 relevance-judged queries across 15 workload categories.
- Validate unique memory IDs, nonempty queries/relevance lists, and references to known memory IDs.
- Run every benchmark in an isolated temporary SQLite database.
- Report Recall@k, Precision@k, NDCG@k, MRR, top-1 accuracy, and per-category breakdowns.
- Keep the existing five-query fixture as a small regression baseline.
- Keep local Ollama embeddings optional; lexical-only mode remains runnable without provider services.

### Contradiction candidate detection

- Move candidate analysis into a dedicated module independent of persistence.
- Detect opposing cues across availability, visibility, location, connectivity, execution mode, mutability, retention, membership, obligation, operation result, automation, transport security, and strictness.
- Require an opposing cue plus a minimum lexical subject-overlap score; when a local embedder is configured, permit high cosine similarity to identify paraphrased candidates.
- Exclude different explicit environment scopes and avoid comparisons between agent-private records belonging to different agents.
- Batch embedding requests and fall back to lexical similarity if embedding is unavailable or fails.
- Persist explainable diagnostics: conflict dimensions, subject Jaccard score, optional semantic cosine score.
- Continue to require an explicit human decision to resolve a candidate. Detection never changes memory status automatically.

### Extraction and confidence evaluation

- Define model confidence as a conservative estimated probability that the whole extracted claim is accurate, supported by candidate evidence, and durable.
- Strengthen evidence quotes to exact candidate substrings with a minimum 12 characters and three meaningful tokens.
- Retain the original model-reported score and a description of its meaning in memory metadata.
- Add a ten-case, 30-claim synthetic annotated extraction dataset with explicit match-term rubrics.
- Match predictions to expected claims one-to-one, then report precision, recall, F1, FP/FN, and quote-validity rate.
- Report Brier score and five-bin expected calibration error (ECE) over predictions, with per-bin sample count, mean confidence, empirical accuracy, and gap.
- Keep extraction benchmarking opt-in because it makes one configured model request per dataset case. It is not part of credential-free unit CI.

## Consequences

- Retrieval regressions become visible by engineering category instead of being summarized by five hand-picked queries.
- The broader retrieval corpus is still synthetic, manually curated data. It is a regression workload, not evidence of performance on real customer or production memory.
- Opposition-aware conflict detection should capture more practical policy changes, but remains vocabulary- and threshold-based. It is not a general natural-language inference or temporal-reasoning model.
- Embedding similarity can improve paraphrase recall but may create false positives. Human review remains mandatory.
- The extraction benchmark quantifies quality against an explicit, inspectable matching rubric. The rubric may miss valid paraphrases or produce broad matches; human-reviewed project data is still required.
- Brier and ECE calculated over 30 expected claims are descriptive sample estimates and cannot establish model-wide calibration.
- No database schema migration is required; conflict data continues to use the existing `memory_conflicts` table. Benchmark datasets and reports are separate from runtime project memory.


## Repository-grounded validation follow-up

- Add a second, source-backed retrieval dataset from the public KALDRAX main-branch snapshot `1b50f309c7cd2f9a0dc7ec444f12fc57c25cc7d9`, with 37 memories and 36 proposed queries.
- Preserve a source path and anchor for every memory. Exclude local SQLite data, runtime reports, credentials, environment values, private conversations, and private repositories.
- Mark every query judgment `assistant_proposed_pending_human_review` and privacy scope `pending_operator_signoff`. Assistant-created judgments are not human labels. A human must review every relevant-ID set and approve the source scope before any human-labeled or production claim.
- Add paired lexical-versus-hybrid evaluation on the exact same queries. Publish paired deltas only when local embedding indexing and query vectors succeed; a failed or absent provider must never be presented as a hybrid result.
- Run the repository corpus's lexical baseline in ordinary credential-free CI. Add the 10-case live extraction benchmark to the existing manual secret-gated provider job, with a 1,024-token completion cap and the shared run budget.
- The live provider job has not been dispatched as part of this decision; provider extraction results remain unmeasured until a configured manual run completes.
