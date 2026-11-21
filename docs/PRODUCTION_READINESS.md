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

The baseline credential-free CI run (44872710002, commit eea0b6d) passed Python 3.11 and 3.13 tests, deterministic quality checks, the Python 3.13 Docker integration steps, desktop lint, and the Vite production build. The portable-default change (44873241896, commit d1a98a5) also passed both Python jobs and desktop lint/build. The optional live-provider smoke test and tag-only memory release-threshold job were skipped. CI now also builds and smoke-tests a frozen Windows engine prototype; it does not yet build or install the native Tauri MSI/NSIS installer.

## Release blockers and workstreams

### P0 — Self-contained desktop installation

**Implementation status:** The frozen Windows x64 CLI is configured as a Tauri resource alongside benchmark data. Rust resolves the executable from the application resource directory, locks packaged builds to that runtime, rejects alternate source/executable paths at the Tauri command boundary, and launches the bundled executable with fixed arguments. Source-checkout/Python execution remains available only when no packaged resource is present. Windows CI is being extended to build MSI/NSIS installers and install/smoke-test the NSIS package. These installer checks are not yet verified.

**Acceptance:**
- A clean supported Windows machine can install and launch KALDRAX without Git, a pre-existing Python installation, or a separately cloned source repository.
- The installer includes a reproducible engine build and its runtime dependencies; the engine version matches the desktop version contract.
- The offline demo, local memory, report listing, and credential-free operations work immediately after installation.
- The packaged engine is invoked through fixed executable/argument paths, not shell-interpreted strings.
- MSI and NSIS packages are built in CI and tested on a clean Windows runner.
- A packaging failure prevents release artifact publication.

**Prototype evidence:** The PyInstaller one-folder console build and credential-free CLI smoke test passed on a clean Windows x64 GitHub Actions runner (run 44873532171, commit 4a90000). The compressed frozen-engine workflow artifact was 11,404,466 bytes; this is not installed application size. The app-data migration foundation is implemented. The packaged executable/resource integration and native installer workflow have now been added, but their current CI run must pass before these changes count as verified.

### P1 — Portable first-run and configuration

**Status:** First-run defaults no longer point to a developer-specific Windows checkout. Engine and repository paths start empty on fresh installations; existing saved user settings are preserved.

**Remaining acceptance:**
- First-run onboarding clearly distinguishes bundled engine detection, developer source checkout, repository selection, and optional provider configuration. The UI auto-detects the packaged resource when present; this must be verified in an installed GUI session. Add a packaged-engine status path so end users no longer need to select source/Python.
- Add direct loopback Ollama support without a credential; remote HTTPS endpoints still require a provider-issued key. Live provider setup remains optional.
- No user-specific absolute paths appear in shipped defaults, examples, or release configuration.
- A missing engine, interpreter, Docker daemon, or provider credential produces a clear capability-specific state rather than a generic application failure.
- Provider credentials remain session-only until a separately reviewed secure-credential-storage design is approved.

### P2 — Application data lifecycle

**Implemented foundation:** Desktop operations now target the Tauri application-data directory under `.kaldrax/`. First engine verification invokes a non-destructive migration command: missing files are copied, SQLite is migrated through the online backup API, symlinks/special files are skipped, and a per-source idempotency marker is recorded. Existing checkout data is never deleted and destination files are never overwritten.

**Remaining acceptance:**
- Verify every Tauri command and CLI default uses the same OS application-data root, not a source checkout or installer directory. The native bridge paths and Python CLI defaults have been redirected; packaged-runtime mode still needs end-to-end verification.
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

## Packaging architecture decision

**Selected for the Windows x64 packaging prototype:** build the Python CLI as a PyInstaller one-folder (`--onedir`) console executable and include its complete output directory as a Tauri bundle resource. The Rust backend will launch the packaged executable directly through a fixed executable path and argument vector, preserving the existing native child-process progress/cancellation model. The webview will not receive a shell execution capability.

Use one-folder mode first rather than a one-file executable. PyInstaller documents that one-file mode extracts into a temporary directory at startup and starts more slowly; its documentation recommends validating one-folder mode first because it is easier to diagnose. The Tauri resource API supports bundling directories and resolving them from Rust. References: [Tauri resources](https://v2.tauri.app/develop/resources/), [Tauri sidecars](https://v2.tauri.app/develop/sidecar/), and [PyInstaller operating modes](https://www.pyinstaller.org/en/stable/operating-mode.html).

Prototype constraints:
- Build on a Windows x64 runner with a pinned Python 3.13 patch release and pinned PyInstaller version; do not cross-compile the frozen executable.
- Keep the executable as a console/CLI program so existing subcommands and structured JSON stdout continue to work.
- Include package data and verify help, version, offline demo, memory initialization/search, report creation, and exit-code behavior in the frozen output.
- Do not store SQLite data, reports, checkpoints, review sessions, logs, or backups beside the packaged executable. The app-data path migration is a prerequisite for using the runtime from a protected install directory.
- Keep a developer-source mode for local engineering. Packaged mode must not depend on a user-selected source checkout or system Python.
- Treat this as a prototype decision, not a release claim. Revisit only if a measured Windows build exposes unacceptable startup, size, compatibility, security, or antivirus issues.