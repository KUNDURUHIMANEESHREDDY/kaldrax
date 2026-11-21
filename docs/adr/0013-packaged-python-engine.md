# ADR 0013: Package the Python Engine as a Windows Desktop Resource

- **Status:** Accepted for the Windows x64 packaging prototype
- **Date:** 2026-11-20

## Context

The desktop currently launches `python -m kaldrax.cli` from a separately installed Python interpreter and a user-selected source checkout. That is useful for development but does not meet the production installer requirement: a clean user machine should need neither Git, Python, nor a cloned KALDRAX repository.

The Rust bridge already owns process creation, bounded argument construction, stdout/stderr capture, progress journals, cancellation, and child lifecycle. Replacing this with an HTTP service or a webview shell API would expand the trust boundary and discard working process controls.

## Decision

For the first Windows x64 distribution prototype:

1. Build the CLI using a pinned Python 3.13 x64 toolchain and pinned PyInstaller into a one-folder (`--onedir`) executable distribution.
2. Keep the program as a console CLI entry point, with the existing `kaldrax` subcommands, JSON stdout contracts, and process exit codes.
3. Bundle the complete PyInstaller output directory inside the Tauri application resources and resolve it with Tauri's Rust `PathResolver`.
4. Launch the packaged executable directly from Rust using `std::process::Command`, fixed executable and argument vectors, and only the environment values required by that operation. Do not expose arbitrary process execution to the webview and do not add a webview shell permission.
5. Retain an explicit developer mode that runs a selected source checkout with a selected Python interpreter. Production packaged mode must use the bundled engine and must not silently fall back to an arbitrary system Python.
6. Move writable state to Tauri's app-data directory before the packaged runtime is considered usable. The install/resource directory is read-only product code, not a data directory.

## Rationale

- PyInstaller supports both one-folder and one-file output. Its current operating-mode documentation notes that one-file mode extracts to a temporary directory at launch and starts more slowly, and recommends validating one-folder mode first because it is easier to diagnose. One-folder output is therefore the safer first packaging target for an application whose process startup, native dependencies, and logs must be diagnosable.
- Tauri supports bundling resource directories and resolving their installed location through the Rust path resolver. The runtime can therefore remain a private native application resource rather than a webview-controlled executable path.
- Keeping process ownership in Rust preserves existing stdout/stderr capture and cancellation semantics while avoiding an additional shell capability in the webview.
- The current Python runtime has no mandatory third-party runtime dependencies in `pyproject.toml`; package-data still needs explicit frozen-build verification.

References:
- Tauri, [Embedding Additional Files](https://v2.tauri.app/develop/resources/).
- Tauri, [Embedding External Binaries](https://v2.tauri.app/develop/sidecar/).
- PyInstaller, [What PyInstaller Does and How It Does It](https://www.pyinstaller.org/en/stable/operating-mode.html).

## Consequences

- The frozen executable must be built on the target operating system and architecture; Windows x64 packaging is an explicit first release target, not evidence of macOS/Linux support.
- Build tooling and PyInstaller are development/build dependencies only. They are not added to KALDRAX's runtime dependency list.
- The app-data migration must land before package-runtime integration because the existing desktop writes under the source engine's `.kaldrax/` directory.
- Installer size, cold/warm startup, antivirus behavior, crash diagnostics, dependency collection, reproducibility, upgrade/uninstall behavior, and clean-machine installation remain measured prototype gates.
- If the one-folder prototype fails those gates, the decision must be revisited with measured evidence rather than switching to one-file by assumption.

## Packaging prototype implementation

- Build the frozen CLI from a clean Windows x64 CI runner with Python 3.13.17 and PyInstaller 6.22.3 pinned.
- Run `--help`, the offline demo with isolated SQLite/report paths, and the deterministic evaluator benchmark from the frozen directory; the benchmark invocation also proves the evaluator fixture was packaged.
- Record the build toolchain used by the CI prototype.

## Prototype verification evidence

- GitHub Actions run `44873532171` passed on commit `4a90000213a9a386e2e11c3c00b9e174443293b1`: Windows x64 frozen build, CLI help, offline demo, isolated SQLite and JSON report outputs, and deterministic evaluator benchmark using collected package data. Python 3.11 and 3.13 plus desktop lint/build also passed in the same workflow.
- The workflow uploaded the frozen engine directory and toolchain evidence. The archive size was 11,404,466 bytes; this is compressed CI artifact size, not MSI/NSIS installation size.
- The first workflow attempt failed only because the smoke script derived its default executable path incorrectly. The path was corrected, and the subsequent complete workflow passed. The build itself had succeeded in the failed attempt.

## Release verification still required

- Confirm writable state is redirected to the OS app-data location before launching the packaged runtime from the installed application.
- Build MSI and NSIS installers, install on a clean Windows runner without Python/Git, and verify first launch, offline demo, memory, reports, upgrade, and uninstall data-retention semantics.
- Verify no API key is needed for installation, first launch, offline demo, or deterministic operations.
- Record actual build size, startup measurements, hashes, and test evidence. Source-level configuration alone is not acceptance.