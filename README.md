# KALDRAX

**Autonomous Engineering Infrastructure**
*Build. Verify. Evolve.*

KALDRAX is an extensible framework for executing engineering tasks through bounded feedback loops, independently evaluating outputs against explicit acceptance criteria, and preserving evidence about each run.

It is designed to grow beyond a coding agent: the same infrastructure can coordinate software work, agent systems, workflows, and other engineered artifacts.

## v0.1

The first release establishes this execution contract:

**Task â†’ Executor â†’ Candidate â†’ Independent Evaluator â†’ Feedback â†’ Retry or Stop**

- Finite iteration limits.
- Executor/evaluator separation.
- Deterministic acceptance checks.
- Structured run events and JSON reports.
- Offline CLI demonstration.

## Quick start

Requires Python 3.11+.

```powershell
python -m pip install -e ".[dev]"
kaldrax demo
```

The demo writes a JSON run report under .kaldrax/runs/.

## Development

```powershell
python -m pytest
```

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture and technology decisions](docs/ARCHITECTURE.md)
- [Development log](docs/DEVELOPMENT_LOG.md)
- [ADR 0001: Core stack](docs/adr/0001-core-stack.md)
- [Repository structure](docs/REPOSITORY_STRUCTURE.md)

## Current limitations

The v0.1 evaluator uses case-insensitive substring checks. A passing result proves only that declared strings were found; it does not prove semantic correctness, software quality, or production readiness. The core does not yet run arbitrary code, connect to LLM providers, spawn agents, provision cloud workers, expose an API, or include a web UI.

## Principles

- Independent evaluation; producer never assigns its own verdict.
- Bounded execution; no unbounded recursive loops.
- Explicit evidence; preserve what ran and why it stopped.
- Safe defaults; no unrestricted command execution.
- Extensible interfaces; integrations must not own core policy.
