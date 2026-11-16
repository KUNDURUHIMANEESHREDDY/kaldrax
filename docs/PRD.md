# KALDRAX v0.3 Product Requirements Document

**Status:** v0.3 implementation baseline
**Category:** Autonomous Engineering Infrastructure
**Release objective:** Add persistent project memory to bounded, independently evaluated model-backed execution.

## Vision

KALDRAX is infrastructure for specifying work, coordinating execution, evaluating artifacts against explicit contracts, and iterating safely when results fail. It is not merely a chat interface or AI coding wrapper.

## v0.2 goals (implemented)

1. Preserve the provider-neutral executor and evaluator ports.
2. Add an OpenAI-compatible chat-completions adapter without a runtime SDK dependency.
3. Add an LLM executor that receives the objective, criteria, iteration, and failed-criterion feedback.
4. Add an LLM evaluator configured with a different model identifier from the executor.
5. Require one evaluator result per criterion and verbatim candidate evidence for every positive judgment.
6. Derive run success from validated criterion results, never a model-provided aggregate verdict.
7. Improve offline deterministic matching to avoid substring false positives and preserve matched quotes.
8. Persist evaluator exceptions as explicit failed runs.
9. Keep the offline demo credential-free.

## v0.3 goals: persistent memory

1. Define typed memory records, retrieval matches, a memory-store port, and explicit per-run working memory.
2. Persist episodic run outcomes in local SQLite, including failed and iteration-limit outcomes.
3. Isolate all memory reads and writes by \`project_id\`.
4. Support project-shared records and optional agent-private records without exposing another agent's private records to an agent-scoped query.
5. Retrieve relevant memory before execution and expose it only through an optional memory-aware executor interface.
6. Include prior candidate and evaluator feedback in the next LLM executor iteration.
7. Extract semantic knowledge only from explicit reusable-knowledge markers in passing candidates.
8. Preserve source run IDs and event sequence numbers for every memory record.
9. Consolidate exact normalized duplicates while retaining their provenance.
10. Provide CLI operations to search and consolidate memory; keep offline demo operational without credentials.

## Non-goals

- Autonomous unrestricted shell or code execution.
- Multi-agent coordination, agent spawning, or distributed scheduling.
- Cloud worker provisioning, hosted memory, API, or web UI.
- Production deployment automation.
- A claim that LLM evaluation is objectively correct or fully independent.
- Embedding/vector retrieval, LLM-generated memory extraction, semantic contradiction resolution, or automatic expiry in v0.3.

## Functional requirements

| ID | Requirement | Acceptance |
|---|---|---|
| FR-01 | Task contract | Reject blank objective, empty/blank/duplicate criteria, and invalid iteration limit. |
| FR-02 | Pluggable executor | Engine depends on the executor protocol, not a provider implementation. |
| FR-03 | Pluggable evaluator | Evaluator receives only task contract and candidate. |
| FR-04 | LLM executor | OpenAI-compatible request uses configured model and carries retry feedback. |
| FR-05 | Independent model setting | CLI requires a non-empty evaluator model different from executor model. |
| FR-06 | Evidence-backed LLM evaluation | Require exact criterion coverage; accept positive criterion only with a verbatim quote from candidate. |
| FR-07 | Safe outcome derivation | Derive pass/fail from validated criterion rows, not model aggregate verdicts. |
| FR-08 | Deterministic fallback | Match whole phrases case-insensitively with token boundaries and record matched quote. |
| FR-09 | Bounded execution | Never exceed configured iterations; apply timeout and per-request output-token limit. |
| FR-10 | Explicit failures | Persist executor/evaluator errors as failed run events. |
| FR-11 | Provenance | Persist evaluations, evidence, ordered events, timestamps, and run identifier. |
| FR-12 | Offline demo | Demo runs without network or credentials. |
| MEM-01 | Working memory | Maintain retrieved memories, feedback, iteration, and prior/current candidates for one run only. |
| MEM-02 | Episodic persistence | Persist every completed run with project ID, run ID, outcome, and event provenance. |
| MEM-03 | Project isolation | Retrieval for one project never returns another project's records. |
| MEM-04 | Agent scope | An agent-scoped read returns its own and project-shared records, not another agent's private records. |
| MEM-05 | Memory-aware execution | Existing executor implementations remain compatible; memory-aware executors receive structured working context. |
| MEM-06 | Semantic extraction | Extract only explicit Decision/Pattern/Lesson/Rule lines from passing candidates. |
| MEM-07 | Evidence provenance | Every stored outcome/lesson references its source run and event sequence numbers. |
| MEM-08 | Retrieval | Deterministic lexical ranking is bounded by a configurable result limit. |
| MEM-09 | Consolidation | Exact duplicate merge preserves contributing source IDs, event sequences, and tags. |
| MEM-10 | Operator controls | CLI supports project memory search and consolidation. |

## Quality attributes

- **Safety:** no arbitrary command execution; retrieved memory is untrusted; memory cannot alter evaluator policy or acceptance criteria.
- **Reliability:** strict provider response validation, bounded requests, explicit failure events, and behavior tests.
- **Auditability:** criterion-level quotes, ordered run events, and source run/event provenance for memory.
- **Extensibility:** provider transport and memory persistence remain behind stable interfaces.
- **Portability:** Python 3.11+, standard-library runtime.
- **Cost control:** per-request output cap and iteration limit; aggregate token and monetary budgets remain open work.
- **Memory isolation:** every memory query and write is scoped by project; optional agent-private records are kept separate.

## v0.3 success metrics

- Project separation, agent visibility, persistence across process restart, and consolidation provenance have automated tests.
- A second run in the same project retrieves prior episodic/semantic context; a different project does not.
- The LLM executor prompt includes retrieved memory IDs and source provenance plus prior iteration output.
- Existing v0.2 tests and offline demo continue to pass without an API key.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Evaluator misinterprets evidence | Verbatim quote requirement; document probabilistic limitation; add deterministic checks for critical criteria. |
| Same model self-approves output | Require distinct model IDs; do not claim provider-level independence. |
| Provider hangs or returns oversized output | Per-request timeout and 4 MiB response cap. |
| Model usage becomes expensive | Per-request output cap and iteration limit; add aggregate token/cost accounting before higher autonomy. |
| Generated code is unsafe | Do not execute generated code in v0.3; sandboxing remains prerequisite. |
| Memory retrieval misses relevant knowledge | Lexical retrieval is an initial deterministic baseline; evaluate embeddings only with measured recall needs. |
| Memory stores stale or misleading lessons | Extract only explicit markers from passing outputs; keep provenance and document that human review is still required. |
| Similar facts are not text-identical | Consolidate exact normalized duplicates only; do not claim semantic conflict resolution. |
