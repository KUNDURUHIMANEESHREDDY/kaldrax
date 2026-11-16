# Repository Structure

\`\`\`text
kaldrax/
├── benchmarks/
│   ├── memory_retrieval.json
│   ├── memory_retrieval_engineering_v2.json
│   └── memory_extraction_v1.json
├── src/kaldrax/data/
│   └── evaluator_cases.json
├── docs/
│   ├── adr/
│   │   ├── 0001-core-stack.md
│   │   ├── 0002-llm-executor-and-evidence-evaluator.md
│   │   ├── 0003-persistent-project-memory.md
│   │   ├── 0004-memory-intelligence.md
│   │   ├── 0005-budgeted-sandbox-agent-runtime.md
│   │   ├── 0006-memory-quality-evaluation.md
│   │   └── 0007-repository-engineering-loop.md
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT_LOG.md
│   └── REPOSITORY_STRUCTURE.md
├── src/kaldrax/
│   ├── __init__.py
│   ├── cli.py
│   ├── agents.py
│   ├── benchmark.py
│   ├── budgets.py
│   ├── sandbox.py
│   ├── workspace.py
│   ├── workspace_sandbox.py
│   ├── engineering.py
│   ├── embeddings.py
│   ├── engine.py
│   ├── evaluation.py
│   ├── execution.py
│   ├── llm.py
│   ├── memory.py
│   ├── memory_benchmarks.py
│   ├── memory_annotation.py
│   ├── memory_benchmark_comparison.py
│   ├── memory_contradictions.py
│   ├── memory_intelligence.py
│   ├── memory_quality.py
│   └── models.py
├── tests/
│   ├── test_agents.py
│   ├── test_benchmark.py
│   ├── test_budgets.py
│   ├── test_sandbox.py
│   ├── test_cli.py
│   ├── test_embeddings.py
│   ├── test_engine.py
│   ├── test_evaluation.py
│   ├── test_llm.py
│   ├── test_memory.py
│   ├── test_memory_benchmarks.py
│   ├── test_memory_annotation.py
│   ├── test_memory_benchmark_comparison.py
│   ├── test_memory_contradictions.py
│   ├── test_memory_intelligence.py
│   └── test_memory_quality.py
├── .env.example
├── .gitignore
├── .python-version
└── pyproject.toml
\`\`\`

Runtime files are stored under .kaldrax by default: SQLite project memory and JSON run reports. They are local data, not source-controlled application files.

## Dependency direction

The engine depends on domain models and the executor/evaluator/memory interfaces. Embedding and LLM transports are injected adapters. The CLI configures local storage and optional providers. Memory retrieval and extraction benchmarks use isolated datasets and temporary storage and do not mutate user project memory. Retrieval uses synthetic-curated relevance judgments; extraction uses an annotated match-term rubric.


GitHub Actions additionally runs evaluator acceptance regression tests, lexical-versus-hybrid memory comparison, a Docker single-file smoke case, and a repository-aware patch/test/review/apply integration case. The optional provider-smoke job requires manually configured repository secrets and variables.
