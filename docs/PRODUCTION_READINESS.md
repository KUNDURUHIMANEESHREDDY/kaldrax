# KALDRAX Production Readiness

**Status:** Active engineering plan; not a claim that the current build is production-ready.
**Initial distribution target:** Windows x64 desktop, inferred from the current MSI/NSIS bundle configuration. Other platforms remain a later expansion unless the release target changes.

## Product boundary

KALDRAX is a local-first engineering application. The Python control plane, SQLite memory, reports, repository inspection, and deterministic workflows run locally. KALDRAX does not require a hosted KALDRAX account or service.

Hosted model providers are optional adapters. A provider-issued credential is required only when an operator deliberately starts a live model-backed workflow or enables hosted embeddings. The environment variable name KALDRAX_API_KEY is a compatibility/configuration name; the value is a key from the selected model provider, not a key issued by KALDRAX. Local/offline development and deterministic CI must remain credential-free.

## Current baseline

The repository already contains the v0.6 Python engine and a Tauri 2 + React desktop client:

- Bounded execution, separate reviewer/evaluator roles, shared call/token/time/cost budgets, and persisted run reports.
- Local SQLite project memory, retrieval and extraction evaluation, approval/conflict workflows, and immutable benchmark review exports.
- Repository intelligence, task DAG scheduling, checkpoint/resume and bounded replanning.
- Repository patch generation, file-scope enforcement, disposable Docker verification, reviewer/evaluator gates, and explicit patch application.
- Desktop workflows for offline demo, runs, memory, team execution, sandbox operations, and repository inspection/editing.

The latest credential-free CI run at the start of this plan (44872710002, commit eea0b6d) passed Python 3.11 and 3.13 tests, deterministic quality checks, the Python 3.13 Docker integration steps, desktop lint, and the Vite production build. The optional live-provider smoke test and tag-only memory release-threshold job were skipped. The CI workflow does not yet build and smoke-test the native Tauri installer.

## Release blockers and workstreams

### P0 — Self-contained desktop installation

**Current gap:** The desktop invokes python -m kaldrax.cli from an operator-selected source checkout. It requires Python 3.11+ and a separately installed KALDRAX checkout. The Tauri bundle does not currently include the engine or a Python runtime. This is a developer integration workflow, not a turnkey end-user installation.

**Acceptance:**
- A clean supported Windows machine can install and launch KALDRAX without Git, a pre-existing Python installation, or a separately cloned source repository.
- The installer includes a reproducible engine build and its runtime dependencies; the engine version matches the desktop version contract.
- The offline demo, local memory, report listing, and credential-free operations work immediately after installation.
- The packaged engine is invoked through fixed executable/argument paths, not shell-interpreted strings.
- MSI and NSIS packages are built in CI and tested on a clean Windows runner.
- A packaging failure prevents release artifact publication.

**Implementation sequence:** choose and document the engine packaging format; create a reproducible Windows build; connect the Rust bridge to the packaged engine while retaining an explicit developer mode; then smoke-test the installed application.

### P1 — Portable first-run and configuration

**Status:** First-run defaults no longer point to a developer-specific Windows checkout. Engine and repository paths start empty on fresh installations; existing saved user settings are preserved.

**Remaining acceptance:**
- First-run onboarding clearly distinguishes engine setup, repository selection, and optional provider configuration.
- No user-specific absolute paths appear in shipped defaults, examples, or release configuration.
- A missing engine, interpreter, Docker daemon, or provider credential produces a clear capability-specific state rather than a generic application failure.
- Provider credentials remain session-only until a separately reviewed secure-credential-storage design is approved.

### P2 — Application data lifecycle

**Current gap:** The desktop derives memory, run, operation, and review data paths from the selected engine checkout.

**Acceptance:**
- Desktop-owned persistent data lives in the operating system's application-data directory, not inside a source checkout or installer directory.
- Existing .kaldrax/ data can be discovered and migrated non-destructively, with a manifest and rollback-safe copy.
- Operators can back up, restore, export, and deliberately reset local data.
- Schema and artifact compatibility are versioned; interrupted migration never destroys the source data.

### P3 — Native integration and operational reliability

**Acceptance:**
- Windows packaged-app tests exercise actual Tauri IPC and the packaged engine; mocked browser IPC remains a supplemental UI test only.
- Process start, progress, cancellation, abnormal exit, app restart, and stale-operation recovery are tested.
- Reports and operation journals remain bounded and redact credentials.
- Repository patch apply remains gated by clean/base-commit checks, exact file scope, sandbox verification, reviewer approval, independent evaluation, and explicit operator confirmation.

### P4 — Security and privacy hardening

**Acceptance:**
- Review every Tauri command and capability; the webview receives only named, validated operations.
- Keep shell execution, filesystem access, and network egress deny-by-default outside explicitly scoped workflows.
- Preserve path traversal, symlink, secret-file, stale-hash, and file-size protections with negative regression tests.
- Verify provider credentials never enter localStorage, persisted settings, reports, progress journals, crash logs, or frontend bundles.
- Show the provider, destination, and data categories before any hosted request; no hosted request is sent by offline workflows.
- Document local data retention, backup, deletion, and provider data egress. This technical review is not a legal-compliance certification.

### P5 — Release engineering

**Acceptance:**
- CI builds, tests, and archives versioned MSI/NSIS artifacts from a clean source revision.
- Release artifacts include SHA-256 checksums, version/commit metadata, and a software-component inventory.
- Installer upgrade, repair, uninstall, and retained-user-data behavior are tested.
- Code signing and trusted update delivery are evaluated before public distribution.
- The strict memory release-threshold and live-provider validation jobs remain explicit, bounded, and separately credential-gated; they are not prerequisites for local/offline development.

## Dependency order

P0 packaging decision and build -> packaged-engine Rust integration -> P3 native smoke tests -> P2 app-data migration -> P4 security regression -> P5 release pipeline.

P1 portability is underway and can proceed independently. Provider configuration and live model-quality validation are deliberately deferred until the local product can be installed, launched, exercised, and verified without a provider key.

## Non-goals for the first desktop release

- Hosted KALDRAX accounts, remote control plane, multi-tenant service, or mandatory cloud database.
- Mandatory model-provider account or API key.
- Distributed multi-machine agent scheduling.
- Automatic deployment of generated repository changes.
- Treating model-generated review or evaluation as human approval.

## Decision record needed before packaging implementation

The packaging spike must compare a frozen Python sidecar (for example, a PyInstaller executable) with a portable CPython runtime plus packaged KALDRAX sources. The choice must be tested against startup time, installer size, Windows antivirus false positives, native module compatibility, crash diagnostics, and reproducibility before adopting it as the release architecture.