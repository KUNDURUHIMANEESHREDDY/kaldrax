# Repository Structure

\`\`\`text
kaldrax/
├── benchmarks/
│   └── memory_retrieval.json
├── docs/
│   ├── adr/
│   │   ├── 0001-core-stack.md
│   │   ├── 0002-llm-executor-and-evidence-evaluator.md
│   │   ├── 0003-persistent-project-memory.md
│   │   └── 0004-memory-intelligence.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT_LOG.md
│   └── REPOSITORY_STRUCTURE.md
├── src/kaldrax/
│   ├── __init__.py
│   ├── cli.py
│   ├── embeddings.py
│   ├── engine.py
│   ├── evaluation.py
│   ├── execution.py
│   ├── llm.py
│   ├── memory.py
│   ├── memory_benchmarks.py
│   ├── memory_intelligence.py
│   └── models.py
├── tests/
│   ├── test_cli.py
│   ├── test_embeddings.py
│   ├── test_engine.py
│   ├── test_evaluation.py
│   ├── test_llm.py
│   ├── test_memory.py
│   ├── test_memory_benchmarks.py
│   └── test_memory_intelligence.py
├── .env.example
├── .gitignore
├── .python-version
└── pyproject.toml
\`\`\`

Runtime files are stored under .kaldrax by default: SQLite project memory and JSON run reports. They are local data, not source-controlled application files.

## Dependency direction

The engine depends on domain models and the executor/evaluator/memory interfaces. Embedding and LLM transports are injected adapters. The CLI configures local storage and optional providers. Benchmark execution uses an isolated temporary database and does not mutate user project memory.
