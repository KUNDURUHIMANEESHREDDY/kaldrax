# Production Security Review — Desktop Packaging and Local State

**Review scope:** Windows frozen-engine packaging, Tauri runtime selection, desktop application-data isolation and legacy-state migration.  
**Review status:** Focused source review; not a full application penetration test or compliance certification. The app-data migration and Windows frozen-engine prototype have passing CI evidence. The first Tauri integration run failed during native Rust compilation because a benchmark action string was reused after being moved into CLI arguments. This compile failure was corrected; installer build and installed-resource smoke remain unverified until the rerun completes.  
**Date:** 2026-11-20

## Assets and trust boundaries

- User data: SQLite memory, run reports, review sessions/exports, checkpoints, sandbox workspaces and operation journals.
- Workspace data: files in a separately selected Git worktree, including potentially sensitive repository content.
- Runtime: the frozen Python CLI packaged as a Tauri resource.
- Credentials: model-provider keys, which remain optional and session-only in the current desktop UI.
- Trust boundaries: webview to Tauri commands; Rust process manager to CLI child process; CLI to local filesystem; CLI to optional model provider; repository workspace to patch/sandbox operations.

## Controls implemented in this change set

| Surface | Control | Verification evidence |
|---|---|---|
| Packaged engine selection | Rust resolves the executable through Tauri's resource resolver and compares the canonical root against the resource root before accepting a packaged runtime path. | Rust native packaged-engine test passed; installed Tauri GUI startup also exercised packaged resource discovery and native command invocation. |
| Process execution | Rust launches the packaged executable directly with an argument vector; it does not construct a shell command or expose a webview shell permission. | Native bridge implementation; native Rust test and installed GUI startup smoke passed. |
| Developer mode | The Python source checkout must contain the expected project manifest and CLI entry point. The interpreter is operator-configured. | Existing engine validation plus desktop source-mode workflow. |
| Writable-state separation | Tauri obtains the OS application-data directory and sets `KALDRAX_DATA_DIR` for engine child processes. | Python and Tauri source changes; Python 3.11/3.13 and installed GUI first-run app-data smoke passed. |
| Legacy migration | Migration validates non-nested source/destination before writes, rejects symlink roots/markers, copies only regular files, does not overwrite destination files, and does not delete the source. | Python regression tests for nested-path non-mutation, symlink rejection, idempotency and destination precedence; installed NSIS smoke verifies source-preserving migration through the bundled CLI. |
| SQLite consistency | Memory DB migration uses SQLite's online backup API and omits WAL/SHM/journal sidecars from generic copying. | Regression test with a committed WAL transaction. |
| Provider credential handling | Provider key remains in frontend session state and is passed only for provider-backed operations; it is not persisted to localStorage or run reports. Hosted provider use is not part of installer smoke tests. | Existing desktop configuration contract and credential-free CI. |

## Residual risks and required work

| Priority | Finding | Risk | Required follow-up |
|---|---|---|---|
| P1 | Developer mode accepts an operator-configured Python executable. | A compromised webview or untrusted local configuration could request a different executable in developer mode. This is an intentional developer capability, but remains privileged. | Keep developer mode clearly separated from installed mode; consider an explicit trusted-executable approval and a backend-held runtime selection rather than trusting repeated webview arguments. |
| P1 | Legacy migration can copy a large state tree. | First connection may take a long time or consume significant disk space; the current migration has no user preview or configurable size cap. | Add a preflight summary/size cap, progress reporting, and user-selectable migration. Do not delete the source automatically. |
| P1 | Model-provider credentials are session-only but are passed to child processes as environment values. | Environment variables may be visible to same-user process inspection or included by future diagnostic code if mishandled. | Keep provider calls optional; add explicit egress review and central secret redaction for reports, logs, crash diagnostics and progress events before expanding live-provider support. |
| P1 | Backup, restore, export and explicit reset are not complete. | Users may not be able to recover or deliberately remove local state through the UI. | Implement versioned, integrity-checked backup/restore/export/reset with confirmation and rollback-safe behavior. |
| P2 | The GUI startup smoke launches the installed Tauri process and observes the first-run native engine probe via app-data creation, but does not assert rendered UI content, accessibility, or user click-through. | UI layout/interaction regressions remain possible. | Add automated visual/interaction tests or a controlled user-session acceptance run. |
| P2 | Installer upgrade, repair and uninstall retention behavior are not yet verified. | User data could be lost or duplicated during lifecycle operations. | Test MSI/NSIS upgrade/repair/uninstall on clean Windows VMs and assert application-data retention policy. |
| P2 | Installer signing and update delivery are not implemented. | Users cannot independently verify publisher identity or update provenance. | Define signing key custody, signed artifacts, update manifest verification and rollback strategy before public distribution. |

## Explicit non-claims

- Passing unit tests or installer smoke is not a penetration test.
- A model privacy screen does not guarantee a dataset contains no sensitive information.
- Provider-side retention and training policies are controlled by the configured provider, not by KALDRAX.
- The current packaged build target is Windows x64; this review does not establish macOS or Linux installer support.


## Packaged process selection hardening

Packaged builds enforce the resource-root boundary for all Tauri commands. When a bundled resource is present, the Rust command builder ignores the webview-supplied Python executable and launches only the executable resolved from Tauri's resource directory. Alternate engine paths are rejected. The prior source checkout is inspected only by a separate read-only validator for migration; migration execution itself uses the bundled CLI. Developer mode remains available only in builds without packaged resources.


## Installed GUI startup verification

The Windows installer smoke now starts the installed Tauri executable and waits for first-run engine verification/run-history initialization to create the Tauri application-data `.kaldrax/runs` directory. This exercises the bundled resource resolver and native command path through the running webview at startup, although it does not assert rendered UI content or perform interactive click-through testing. CI verification of this extension is pending.


## Windows GUI-startup evidence update

Windows CI run `44877341111` passed the installed Tauri GUI startup smoke. The installed main executable remained running while the first-run webview triggered the bundled engine health check and created the OS app-data run-history directory. The test does not cover visual correctness, accessibility, interactive flows, or install/upgrade/uninstall retention.
