# KALDRAX

**Autonomous Engineering Infrastructure**
*Build. Verify. Evolve.*

KALDRAX is an extensible framework for executing engineering tasks through bounded feedback loops, independently evaluating outputs against explicit acceptance criteria, and preserving evidence about each run.

## v0.2 capabilities

- Bounded execution with configurable iteration limits.
- Provider-neutral executor and evaluator interfaces.
- OpenAI-compatible LLM executor using Python's standard library.
- Separate-model LLM evaluator requiring verbatim evidence quotes for passing criteria.
- Offline deterministic evaluator using phrase boundaries rather than substring matches.
- Structured run events, per-criterion evidence, and persisted JSON reports.
- Offline CLI demonstration; LLM-backed CLI for configured providers.

## Quick start

Requires Python 3.11+.

```powershell
python -m pip install -e ".[dev]"
kaldrax demo
```

The demo runs offline and writes a JSON report under `.kaldrax/runs/`.

## LLM-backed run

Copy `.env.example` to `.env` and provide your provider settings. Export those variables in the shell before running KALDRAX; the CLI does not load `.env` automatically.

Required environment variables:

- `KALDRAX_API_KEY`
- `KALDRAX_MODEL` — executor model identifier
- `KALDRAX_EVALUATOR_MODEL` — a different model identifier for evaluation

Optional variables: `KALDRAX_BASE_URL` (defaults to OpenAI's `/v1` API base), `KALDRAX_TIMEOUT_SECONDS` (defaults to `60`), `KALDRAX_MAX_TOKENS` (defaults to `2048` per provider request), and `KALDRAX_TOKEN_PARAMETER` (defaults to `max_completion_tokens`; set to `max_tokens` for legacy-compatible endpoints).

```powershell
$env:KALDRAX_API_KEY = "..."
$env:KALDRAX_MODEL = "executor-model"
$env:KALDRAX_EVALUATOR_MODEL = "different-evaluator-model"
kaldrax run --objective "Implement a CSV parser" --criterion "unit tests pass" --criterion "README documents usage" --max-iterations 3
```

The API key is read from the environment and is not written to run reports. Each provider request has a timeout and output-token cap. The iteration limit bounds the number of executor/evaluator cycles; aggregate token or monetary accounting is not yet implemented.

## Development

```powershell
python -m pytest -q
```

## Evaluation guarantees and limitations

The offline evaluator checks literal phrases with token boundaries. It is deterministic but does not understand paraphrases or prove semantic correctness. The LLM evaluator judges each criterion separately and requires an exact quote from the candidate for every passing result. Quotes make judgments traceable to the candidate but do not prove that the evaluator interpreted the quote correctly. A passing result is not a substitute for running tests, security checks, or human review.

The executor produces text artifacts only. KALDRAX does not run arbitrary shell commands or code, spawn agents, provision workers, or deploy software. Do not treat model-generated claims about tests or deployments as verification evidence.

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [ADR 0001: Core stack](docs/adr/0001-core-stack.md)
- [ADR 0002: LLM execution and evidence evaluator](docs/adr/0002-llm-executor-and-evidence-evaluator.md)
- [Repository structure](docs/REPOSITORY_STRUCTURE.md)
