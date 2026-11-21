# Production Security Review — Desktop Packaging and Local State

**Review scope:** Windows frozen-engine packaging, Tauri runtime selection, desktop application-data isolation and legacy-state migration.  
**Review status:** Focused source review; not a full application penetration test or compliance certification. The app-data migration and Windows frozen-engine prototype have passing CI evidence. The new Tauri resource integration and installer build/smoke checks are pending the CI run for this commit.  
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
| Packaged engine selection | Rust resolves the executable through Tauri's resource resolver and compares the canonical root against the resource root before accepting a packaged runtime path. | Rust unit test for bundled executable command construction is included; the new Windows installer smoke step is pending CI execution. |
| Process execution | Rust launches the packaged executable directly with an argument vector; it does not construct a shell command or expose a webview shell permission. | Native bridge implementation; packaged-engine unit test is included and pending CI execution. |
| Developer mode | The Python source checkout must contain the expected project manifest and CLI entry point. The interpreter is operator-configured. | Existing engine validation plus desktop source-mode workflow. |
| Writable-state separation | Tauri obtains the OS application-data directory and sets `KALDRAX_DATA_DIR` for engine child processes. | Python and Tauri source changes; CI test coverage for CLI data-root routing. |
| Legacy migration | Migration validates non-nested source/destination before writes, rejects symlink roots/markers, copies only regular files, does not overwrite destination files, and does not delete the source. | Python regression tests for nested-path non-mutation, symlink rejection, idempotency and destination precedence. |
| SQLite consistency | Memory DB migration uses SQLite's online backup API and omits WAL/SHM/journal sidecars from generic copying. | Regression test with a committed WAL transaction. |
| Provider credential handling | Provider key remains in frontend session state and is passed only for provider-backed operations; it is not persisted to localStorage or run reports. Hosted provider use is not part of installer smoke tests. | Existing desktop configuration contract and credential-free CI. |

## Residual risks and required work

| Priority | Finding | Risk | Required follow-up |
|---|---|---|---|
| P1 | Developer mode accepts an operator-configured Python executable. | A compromised webview or untrusted local configuration could request a different executable in developer mode. This is an intentional developer capability, but remains privileged. | Keep developer mode clearly separated from installed mode; consider an explicit trusted-executable approval and a backend-held runtime selection rather than trusting repeated webview arguments. |
| P1 | Legacy migration can copy a large state tree. | First connection may take a long time or consume significant disk space; the current migration has no user preview or configurable size cap. | Add a preflight summary/size cap, progress reporting, and user-selectable migration. Do not delete the source automatically. |
| P1 | Model-provider credentials are session-only but are passed to child processes as environment values. | Environment variables may be visible to same-user process inspection or included by future diagnostic code if mishandled. | Keep provider calls optional; add explicit egress review and central secret redaction for reports, logs, crash diagnostics and progress events before expanding live-provider support. |
| P1 | Backup, restore, export and explicit reset are not complete. | Users may not be able to recover or deliberately remove local state through the UI. | Implement versioned, integrity-checked backup/restore/export/reset with confirmation and rollback-safe behavior. |
| P2 | The installer smoke verifies an installed engine resource and credential-free CLI execution, not a full interactive GUI session. | Tauri resource discovery and startup may still fail in a user session despite engine-resource smoke passing. | Add a Windows UI launch/IPC smoke or automate a test command through the actual installed Tauri application. |
| P2 | Installer upgrade, repair and uninstall retention behavior are not yet verified. | User data could be lost or duplicated during lifecycle operations. | Test MSI/NSIS upgrade/repair/uninstall on clean Windows VMs and assert application-data retention policy. |
| P2 | Installer signing and update delivery are not implemented. | Users cannot independently verify publisher identity or update provenance. | Define signing key custody, signed artifacts, update manifest verification and rollback strategy before public distribution. |

## Explicit non-claims

- Passing unit tests or installer smoke is not a penetration test.
- A model privacy screen does not guarantee a dataset contains no sensitive information.
- Provider-side retention and training policies are controlled by the configured provider, not by KALDRAX.
- The current packaged build target is Windows x64; this review does not establish macOS or Linux installer support.
