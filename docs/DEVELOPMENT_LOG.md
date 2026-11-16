# KALDRAX Development Log

This file records implementation decisions, changes, commands, verification, and outstanding risks. Append an entry for every meaningful engineering session.

## 2026-11-16 â€” v0.1 core engine baseline

### Decisions
- Work directly on GitHub main; no feature branches or pull requests unless project owner changes this rule.
- Python 3.11+ with standard-library runtime; pytest for development tests.
- Keep executor and evaluator behind separate interfaces.
- Bound every recursive run with an explicit iteration limit.
- Persist inspectable JSON run reports locally.
- Defer API, UI, provider integrations, cloud workers, and arbitrary sandboxed execution until core contracts are proven.

### Changes
- Added complete v0.1 PRD and architecture baseline.
- Added accepted ADR for the Python/provider-neutral core stack.
- Established src-layout package, CLI, tests, docs, and future integration directories.
- Added task, evaluation, event, and run-report domain models.
- Added pluggable executor protocol and offline example executor.
- Added independent deterministic acceptance-criteria evaluator.
- Added bounded recursive engine, JSON report persistence, and CLI demo.
- Added explicit executor-exception reporting and persistence.
- Added tests for retry-to-pass, iteration exhaustion, evaluator behavior, invalid task contracts, and executor errors.

### Commands and results
- python --version â€” Python 3.11.9
- python -m pytest --version â€” pytest 9.1.1
- python -m pytest -q â€” 5 passed
- python -m pip install -e . --no-deps â€” succeeded
- kaldrax demo --artifacts .kaldrax\verification-run-final â€” passed in 2 iterations; JSON report persisted
- git diff --check â€” passed

### Demo evidence
- First demo run ID: e7028e2b-54e9-475a-a3df-98f68b69fdd0
- Final verification run ID: 66391915-7f9d-4b92-8642-35f50a6c6b5a
- First iteration failed all three declared criteria.
- Second iteration satisfied all three criteria.
- Terminal status: passed.

### Risks / follow-up
- Substring evaluator is basic and must not be marketed as semantic verification.
- Add wall-clock, token, and monetary budgets before connecting paid model providers.
- Add process isolation before supporting untrusted code execution.
- Define versioned worker protocol before cloud execution.
- Current execution adapter is an offline example, not a real model-backed agent.
