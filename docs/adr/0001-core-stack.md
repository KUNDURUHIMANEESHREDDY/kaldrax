# ADR 0001: Python modular core with provider-neutral ports

- **Status:** Accepted for v0.1
- **Date:** 2026-11-16

## Context

KALDRAX must prove execution and evaluation semantics before choosing model providers, distributed infrastructure, or UI frameworks. Early provider lock-in would make the core harder to test and evolve.

## Decision

Use Python 3.11+, standard-library runtime modules, setuptools packaging, argparse CLI, JSON local run records, and pytest for development. Keep execution behind an Executor protocol and evaluation behind a separate evaluator interface.

## Consequences

- Core runs offline and is deterministic to test.
- No runtime provider dependency is introduced.
- HTTP API, remote workers, database, UI, container sandbox, and LLM integrations remain later decisions.
- Initial evaluator is deliberately narrow and must be replaced or complemented before claiming semantic verification.
