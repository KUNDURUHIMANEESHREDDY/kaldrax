# KALDRAX

**Autonomous Engineering Infrastructure**
*Build. Verify. Evolve.*

KALDRAX executes engineering tasks through bounded feedback loops, evaluates candidate artifacts independently, and preserves evidence about each run. Its local control plane is designed to remain provider-neutral and auditable.

## v0.3 capabilities

- Bounded execution with configurable iteration limits.
- OpenAI-compatible LLM executor and separate evidence-backed LLM evaluator.
- Deterministic offline evaluator with phrase boundaries and quote evidence.
- Persistent SQLite memory scoped by project, with optional agent-private records and project-shared records.
- Per-run working memory containing retrieved memories, failed-criterion feedback, and the previous candidate.
- Automatic episodic memory for every completed run.
- Conservative semantic knowledge extraction from explicit \`Decision:\`, \`Pattern:\`, \`Lesson:\`, and \`Rule:\` lines in passing candidates.
- Deterministic lexical retrieval and exact-duplicate consolidation with source provenance.
- Structured run events, evidence, and JSON reports.

## Quick start

Requires Python 3.11+.

\`\`\`powershell
python -m pip install -e ".[dev]"
kaldrax demo
\`\`\`

The offline demo requires no credentials. Reports are written under \`.kaldrax/runs/\` and persistent memory is written to \`.kaldrax/memory.sqlite3\` by default. Both paths are ignored by Git.

## LLM-backed run

Copy \`.env.example\` to \`.env\` and provide your provider settings. Export those variables in the shell before running KALDRAX; the CLI does not load \`.env\` automatically.

Required environment variables:

- \`KALDRAX_API_KEY\`
- \`KALDRAX_MODEL\` — executor model identifier
- \`KALDRAX_EVALUATOR_MODEL\` — a different model identifier for evaluation

Optional variables: \`KALDRAX_BASE_URL\` (defaults to OpenAI's \`/v1\` API base), \`KALDRAX_TIMEOUT_SECONDS\` (defaults to \`60\`), \`KALDRAX_MAX_TOKENS\` (defaults to \`2048\` per provider request), and \`KALDRAX_TOKEN_PARAMETER\` (defaults to \`max_completion_tokens\`; set to \`max_tokens\` for legacy-compatible endpoints).

\`\`\`powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_MODEL = "executor-model"
$env:KALDRAX_EVALUATOR_MODEL = "different-evaluator-model"
kaldrax run --project kaldrax-core --agent primary --objective "Implement a CSV parser" --criterion "unit tests pass" --criterion "README documents usage" --max-iterations 3
\`\`\`

The API key is read from the environment and is not written to run reports or memory. Each provider request has a timeout and output-token cap. The iteration limit bounds the number of executor/evaluator cycles; aggregate token or monetary accounting is not yet implemented.

## Memory operations

Every run in a given project adds an episodic record, including failures and iteration-limit outcomes. A passing candidate may also create semantic records, but only from explicit reusable-knowledge markers:

\`\`\`text
Decision: Keep acceptance criteria immutable throughout a run.
Lesson: A failed evaluator result should feed only the missing criteria into the next iteration.
\`\`\`

Search a project's memories:

\`\`\`powershell
kaldrax memory search --project kaldrax-core --query "acceptance evaluator feedback"
\`\`\`

Search as a specific agent (the agent sees its own records plus project-shared records):

\`\`\`powershell
kaldrax memory search --project kaldrax-core --agent primary --query "evaluator feedback"
\`\`\`

Consolidate exact normalized duplicates while retaining source run IDs and event sequences:

\`\`\`powershell
kaldrax memory consolidate --project kaldrax-core
\`\`\`

\`--memory-db\` can override the default database path on \`demo\`, \`run\`, and \`memory\` commands. \`--project\` is the isolation boundary; use a stable, distinct project identifier for each codebase or workstream. \`--agent\` optionally scopes private records to one agent while allowing project-shared memory to remain visible.

## Memory model and limitations

- **Working memory** is transient and scoped to one engine run. It holds retrieved records, feedback, iteration number, and previous/current candidates.
- **Episodic memory** stores what happened during a run, with run and event provenance.
- **Semantic memory** stores explicitly marked lessons extracted from passing outputs, also with provenance.

Retrieval currently uses deterministic lexical token overlap, not embeddings or a vector database. Semantic extraction is intentionally rule-based; it does not ask an LLM to invent lessons. Consolidation merges exact normalized duplicates only and is invoked explicitly with the CLI. It does not infer that two differently worded facts mean the same thing, resolve contradictions, or automatically expire outdated knowledge.

Memory is local and project-scoped, not a distributed shared-memory service. Agent sharing is implemented through the shared project namespace and optional per-agent records. Separate agents/processes can use the same SQLite database, but concurrent distributed coordination and remote memory backends are not implemented. Treat memory content as untrusted historical input; the executor prompt explicitly warns against following instructions embedded in it.

## Evaluation guarantees and limitations

The offline evaluator checks literal phrases with token boundaries. It is deterministic but does not understand paraphrases or prove semantic correctness. The LLM evaluator judges each criterion separately and requires an exact quote from the candidate for every passing result. Quotes make judgments traceable to the candidate but do not prove that the evaluator interpreted the quote correctly. A passing result is not a substitute for running tests, security checks, or human review.

The executor produces text artifacts only. KALDRAX does not run arbitrary shell commands or code, spawn multiple agents, provision workers, or deploy software. Do not treat model-generated claims about tests or deployments as verification evidence.

Memory and run reports may contain sensitive project information. Protect \`.kaldrax/\` and any custom paths supplied through \`--memory-db\` or \`--artifacts\`.

## Development

\`\`\`powershell
python -m pytest -q
python -m compileall -q src tests
\`\`\`

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [ADR 0001: Core stack](docs/adr/0001-core-stack.md)
- [ADR 0002: LLM execution and evidence evaluator](docs/adr/0002-llm-executor-and-evidence-evaluator.md)
- [ADR 0003: Persistent project memory](docs/adr/0003-persistent-project-memory.md)
- [Repository structure](docs/REPOSITORY_STRUCTURE.md)
