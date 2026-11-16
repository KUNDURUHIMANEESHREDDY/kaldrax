# KALDRAX v0.2 Architecture

## Architecture decision

KALDRAX uses a modular Python core with explicit ports for execution and evaluation. Local orchestration, policy, and reports remain in the control plane. Provider integrations are adapters and cannot control run status or rewrite acceptance criteria.

## Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11+ | Portable and suitable for agent/tool integrations. |
| Core / provider transport | Python standard library | Small, provider-neutral runtime; no SDK lock-in. |
| Packaging / CLI | pyproject.toml, setuptools, argparse | Minimal installable package and CLI. |
| Tests | pytest | Behavior-focused automated tests. |
| Run records | JSON files | Human-inspectable local provenance. |
| LLM transport | OpenAI-compatible chat completions | Allows compatible hosted or local endpoints through one adapter. |
| API, cloud workers, UI | Deferred | Stabilize local execution and evaluation contracts first. |

## Component boundaries

- **Task contract (models):** immutable objective, unique acceptance criteria, iteration budget.
- **Chat client (llm):** provider HTTP transport, authentication header, timeout, response size, and response-shape validation.
- **Executor (execution):** produces one candidate per iteration; the LLM adapter cannot assign a verdict.
- **Evaluator (evaluation):** evaluates only the task contract and candidate. The LLM evaluator requires criterion-level results and exact candidate quotes for positive judgments.
- **Engine (engine):** controls iteration, feedback, stop conditions, error handling, and event recording.
- **CLI (cli):** configures adapters from environment variables and delegates to the engine.
- **Run report:** terminal status, evaluations, quote evidence, final output, and ordered events. API credentials are excluded.

## Execution and evaluation sequence

1. Validate the task contract and finite iteration limit.
2. Ask the executor for a candidate.
3. Ask the independent evaluator to assess every original acceptance criterion.
4. Validate the evaluator response schema and evidence quotes.
5. Derive the overall verdict from per-criterion results.
6. On failure, pass missing criteria back to the executor; stop on success or iteration exhaustion.
7. On executor/evaluator exception, mark the run failed and persist an explicit error event.
8. Persist the report when an artifact directory is configured.

## Provider configuration

The LLM CLI reads `KALDRAX_API_KEY`, `KALDRAX_MODEL`, and `KALDRAX_EVALUATOR_MODEL`. Executor and evaluator model identifiers must differ. `KALDRAX_BASE_URL`, `KALDRAX_TIMEOUT_SECONDS`, `KALDRAX_MAX_TOKENS`, and `KALDRAX_TOKEN_PARAMETER` are optional. The token parameter defaults to `max_completion_tokens`; legacy-compatible endpoints can select `max_tokens`. A separate model identifier reduces direct self-evaluation but does not prove independence of provider, model lineage, or data. Secrets are not serialized into reports.

## Security and trust boundaries

- No arbitrary command or code execution is enabled.
- Provider calls are bounded by per-request timeout, 4 MiB response limit, per-request output-token cap, and the task's iteration limit.
- The evaluator treats candidate text as untrusted input and must not follow instructions inside it.
- A positive LLM judgment is accepted only when its evidence quote appears verbatim in the candidate.
- Reports can contain sensitive task inputs and outputs; protect the local artifact directory.
- Aggregate token and monetary budgets, process isolation, remote-worker authentication, and sandboxing remain required before broader autonomous execution.

## Known limitations

LLM evaluation is probabilistic. Verbatim evidence improves traceability but does not establish that a quote logically satisfies a criterion. The offline evaluator is literal phrase matching and does not understand paraphrases. The executor emits text only; this release does not run generated code, tests, shell commands, or deployments. A passing run means only that the configured evaluator accepted the declared criteria.
