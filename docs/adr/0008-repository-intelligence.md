# ADR 0008: Repository Intelligence and Dependency Mapping

- Status: Accepted
- Date: 2026-11-16

## Context

The repository engineering coordinator previously received a bounded path manifest and source snapshot. This was enough to propose a unified diff, but it did not expose local dependency relationships, entry points, likely affected components, or relevant test files. A realistic multi-file change needs a structural map before the planner and builder choose a scope.

## Decision

Introduce a separate, read-only RepositoryIntelligenceAnalyzer that operates on the local Git root. It may inspect a dirty worktree because analysis does not write files; the existing repository-team patch workflow continues to require a clean checkout and immutable base HEAD.

- Detect source languages by suffix and common frameworks/build systems from project manifests and configuration files.
- Use Python's standard-library AST for imports, relative imports, top-level exports, and __main__ detection.
- Use bounded language-specific recognizers for JavaScript/TypeScript, Go, Rust, Java/Kotlin, C#, and C/C++.
- Resolve imports only when a local source target can be identified; preserve unresolved imports as per-file metadata rather than fabricating graph edges.
- Represent dependency direction as importer → imported file. Use strongly connected components to report cycles.
- For changed paths, walk reverse dependencies to identify transitive dependents and combine that set with conventional test-name matching to suggest relevant tests.
- Identify entry-point candidates from source conventions and package metadata.
- Enforce scan caps and exclude symlinks, binary/invalid text, credentials, runtime state, dependency/build outputs, and other private paths.
- Expose the report through kaldrax repo analyze; include the map in repository-team planner and builder context and persist the impact analysis in the run report.

## Consequences

- Planner and builder receive graph-based context rather than only a path listing. The final report records changed paths, affected components, candidate tests, and detected cycles.
- The standalone analysis command works on dirty worktrees and is read-only.
- The analyzer uses no third-party parsing dependency and remains usable offline.
- Python structure is syntax-aware; other-language extraction is heuristic, incomplete for advanced language semantics, and not a replacement for compilers or language servers.
- Dependency edges are limited to imports that resolve to files in the scanned repository. Test selection is a candidate set, not proof of exhaustive test coverage.
- Large repositories can exceed the file/size caps; skipped paths and scan warnings must remain visible to callers.
- Repository patching, Docker verification, reviewer approval, independent evaluation, and explicit apply semantics remain separate gates; intelligence never authorizes a write or test execution.

## Verification

The analyzer regression suite uses temporary Git repositories to validate Python AST behavior, JS/TS aliases, Go/Rust/C/C++ local dependencies, Java/.NET manifest detection, cycles, transitive impact, test selection, entry points, and secret/runtime exclusions.
