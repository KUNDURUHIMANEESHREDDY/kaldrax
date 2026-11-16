# Repository Structure

```text
kaldrax/
├── docs/
│   ├── adr/
│   │   ├── 0001-core-stack.md
│   │   └── 0002-llm-executor-and-evidence-evaluator.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT_LOG.md
│   └── REPOSITORY_STRUCTURE.md
├── src/kaldrax/
│   ├── __init__.py
│   ├── cli.py
│   ├── engine.py
│   ├── evaluation.py
│   ├── execution.py
│   ├── llm.py
│   └── models.py
├── tests/
│   ├── test_cli.py
│   ├── test_engine.py
│   ├── test_evaluation.py
│   └── test_llm.py
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
└── README.md
```

## Dependency direction

The engine depends on domain models and the executor/evaluator interfaces. LLM transport depends only on the standard library and is injected into adapters. The CLI is an outer adapter. Provider integrations, HTTP APIs, remote workers, persistence backends, and web UI must remain adapters around stable core policy.
