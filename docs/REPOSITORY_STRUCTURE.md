# Repository Structure

```text
kaldrax/
â”œâ”€â”€ .github/                 # GitHub automation and contribution workflows (future)
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ adr/                 # Accepted architecture decision records
â”‚   â”œâ”€â”€ PRD.md               # Product requirements and release scope
â”‚   â”œâ”€â”€ ARCHITECTURE.md      # Components, boundaries, trust model, roadmap
â”‚   â”œâ”€â”€ DEVELOPMENT_LOG.md   # Decisions, changes, commands, verification, risks
â”‚   â””â”€â”€ REPOSITORY_STRUCTURE.md
â”œâ”€â”€ examples/                # Runnable integrations and examples (future)
â”œâ”€â”€ src/
â”‚   â””â”€â”€ kaldrax/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ cli.py            # CLI adapter
â”‚       â”œâ”€â”€ engine.py         # Bounded recursive orchestrator
â”‚       â”œâ”€â”€ evaluation.py     # Independent deterministic evaluator
â”‚       â”œâ”€â”€ execution.py      # Executor port and offline example
â”‚       â””â”€â”€ models.py         # Task, evaluation, event, run report
â”œâ”€â”€ tests/                   # Behavior-focused automated tests
â”œâ”€â”€ .gitignore
â”œâ”€â”€ .python-version
â”œâ”€â”€ pyproject.toml            # Package metadata, CLI entry point, dev tools
â””â”€â”€ README.md
```

## Dependency direction

The engine depends on domain models and the executor/evaluator interfaces. The CLI is an outer adapter. Provider integrations, HTTP APIs, remote workers, persistence backends, and web UI must be adapters around the stable core rather than sources of core policy.
