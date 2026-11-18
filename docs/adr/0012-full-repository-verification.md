# ADR 0012: Full-Repository Verification

- Status: Accepted
- Date: 2026-11-18

## Context

Repository patch review used a bounded model-context snapshot as the source for the temporary staging workspace. The snapshot is deliberately limited to 240 files and 45 KB in total. That meant unrelated tracked test files, package metadata, and application modules could be absent from the Docker verification copy. A successful run could therefore describe a partial tree rather than the complete repository.

The coordinator also accepted one selected Python verification module per cycle. It did not have a named profile that paired full test discovery with source/test compilation.

## Decisions

### Separate prompt context from verification workspace

- Keep the bounded snapshot for model prompts and architecture context.
- Rebuild the staging workspace from all safe tracked Git-index entries, independently of the prompt snapshot.
- Copy tracked files with their executable bit preserved and apply the candidate diff to that full tracked tree.
- Never copy .git, KALDRAX runtime state, credentials/private paths, excluded dependency/build/runtime directories, or submodule contents into the sandbox.
- Fail closed on tracked symlinks, submodules, unsafe paths, missing tracked files, unsupported modes, or size-limit violations. Do not claim full verification against a partial tree.

The full staged checkout is bounded to 5,000 files, 20 MB per file, and 100 MB total. The Docker workspace copy uses the same bounds.

### Fixed full verification profile

The full profile runs three ordered stages against the staged full repository:

1. python -m pytest -q, using the repository's configured complete test discovery.
2. python -m compileall -q ., covering all staged Python files.
3. npm run lint and npm run build from desktop/, using Node.js 24 and locked preinstalled dependencies.

Compilation and desktop checks are attempted even when an earlier stage fails, unless cancellation or the shared timeout prevents them. The report records each stage separately, including command, exit code, duration, test count (for pytest), timeout, cancellation, truncation, image and bounded output. At least one passed test is required; zero-test or all-skipped green exits do not qualify. All three stages, reviewer approval and independent evaluator PASS are mandatory.

- Keep legacy single-module modes (unittest, pytest, compileall) available.
- Do not permit custom --verify-arg values to narrow the fixed full profile.
- Require a prebuilt image with pytest, Node.js 24/npm, and dependencies installed from desktop/package-lock.json. The image checks staged desktop/package.json and package-lock.json against hashes captured at image build time.
- Provide docker/verification.Dockerfile; runtime Docker execution uses --pull=never and network isolation.
- Before provider clients are created, verify Docker daemon availability, inspect the image locally, and run a constrained no-network probe for pytest, Node/npm, and prebuilt desktop dependencies. Missing infrastructure or packages must fail before model-provider calls.
- If the desktop manifest or lockfile changes, the operator must rebuild the image so verification dependencies match the candidate repository.
- The desktop exposes the same full profile through the repository workflow selector.

## Consequences

- The model's token/context budget no longer determines which tracked files are available during verification.
- Full verification is more expensive than a single module run and requires a larger but bounded sandbox workspace.
- Large repositories exceeding the file/byte caps, or repositories that require submodule contents or tracked symlinks, are rejected rather than partially tested.
- Private files and credential locations remain excluded even if tracked; tests that require secrets must be redesigned to use safe fixtures or explicitly provisioned non-secret configuration.
- Docker daemon and host kernel remain trusted parts of the sandbox boundary.

## Verification

Regression coverage is added for:
- staging a tracked test file omitted from the bounded prompt snapshot;
- rejection of tracked symlinks;
- fixed full-suite command selection, non-empty pytest results, and Docker/image/pytest preflight;
- running compilation after test failures;
- coordinator acceptance rejection for zero tests or compilation failure;
- CLI and desktop exposure of the full profile.

Build the local verification image before invoking the full profile:

~~~bash
docker build -f docker/verification.Dockerfile -t kaldrax-verification:full .
~~~

Automated test execution and hosted CI status must be recorded separately from source-level implementation.
