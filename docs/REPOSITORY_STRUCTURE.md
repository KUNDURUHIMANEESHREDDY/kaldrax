# Repository Structure

\`\`\`text
kaldrax/
├── docs/
│   ├── adr/
│   │   ├── 0001-core-stack.md
│   │   ├── 0002-llm-executor-and-evidence-evaluator.md
│   │   └── 0003-persistent-project-memory.md
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
│   ├── memory.py
│   └── models.py
├── tests/
│   ├── test_cli.py
│   ├── test_engine.py
│   ├── test_evaluation.py
│   ├── test_llm.py
│   └── test_memory.py
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
└── README.md
\`\`\`

Runtime files are written under \`.kaldrax/\` by default: SQLite project memory and JSON run reports. They are local data, not source-controlled project files.

## Dependency direction

The engine depends on domain models and the executor/evaluator/memory interfaces. LLM transport depends only on the standard library and is injected into adapters. The CLI is an outer adapter. Provider integrations, remote workers, persistence adapters, and user interfaces must remain adapters around stable core policy.
