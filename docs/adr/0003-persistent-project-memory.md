# ADR 0003: Persistent project memory with explicit provenance

- **Status:** Accepted for v0.3
- **Date:** 2026-11-16

## Context

KALDRAX v0.2 can execute and independently evaluate one bounded task, but it does not retain project knowledge across runs. Replaying prior work without retrieving its relevant outcomes wastes context and repeats known failures. Memory must remain auditable, isolated by project, and safe to provide to an LLM executor.

## Decision

- Introduce \`MemoryStore\` and immutable \`MemoryRecord\` / \`MemoryMatch\` domain contracts behind the engine boundary.
- Use SQLite from the Python standard library as the first local persistence adapter. Store files under \`.kaldrax/\` by default; do not add a hosted database or vector dependency.
- Separate transient \`WorkingMemory\`, durable \`EPISODIC\` records, and reusable \`SEMANTIC\` records.
- Scope every memory record and retrieval request by \`project_id\`. Support project-shared records (\`agent_id=None\`) plus optional agent-private records; an agent-specific lookup sees its own and shared records only.
- Persist every completed run as an episodic record, including failures and iteration-limit outcomes. Preserve the originating \`run_id\` and event sequence numbers.
- Extract semantic knowledge conservatively from explicitly labeled \`Decision:\`, \`Pattern:\`, \`Lesson:\`, and \`Rule:\` lines in passing candidates only. Do not ask the model to manufacture facts in the initial release.
- Retrieve with deterministic lexical token-overlap ranking. Label this honestly; vector/embedding retrieval is deferred.
- Consolidate exact normalized duplicates on explicit operator request. Preserve the contributing run IDs, event sequence numbers, and tags in the canonical record.
- Extend the LLM executor through a memory-aware method while retaining the original \`Executor.execute\` protocol for existing integrations. Include prior candidate and feedback in working memory.
- Treat retrieved memories as untrusted historical data. Do not pass memory to the evaluator or let it alter task acceptance criteria.

## Consequences

- Memory survives process restarts and is inspectable in SQLite.
- Same-project tasks and agents can reuse prior outcomes without crossing project boundaries.
- The existing executor API remains compatible; only memory-aware executors consume retrieved memory.
- Memory is local to one database and is not a distributed coordination layer.
- Lexical retrieval may miss paraphrases; explicit-marker extraction may miss useful lessons that are not labeled.
- Exact deduplication does not reconcile contradictions, freshness, or semantic equivalence.
- Local memory can contain proprietary or sensitive artifacts and must be protected like run reports.
