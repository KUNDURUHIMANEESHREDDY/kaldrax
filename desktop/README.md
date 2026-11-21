# KALDRAX Desktop

KALDRAX Desktop is a local-first engineering control center built with React, TypeScript, Vite, Rust and Tauri 2. The Python package remains the authority for task contracts, execution policy, evaluation, budgets and project memory.

## Technology

- Desktop runtime: Rust + Tauri 2
- UI: React 19 + TypeScript + Vite 8
- Styling: CSS, Runey-inspired single expandable navigation rail
- Engine: local Python KALDRAX CLI/package
- Memory: local SQLite under the desktop OS application-data directory (`.kaldrax/memory.sqlite3`)
- Run artifacts: JSON reports under desktop OS application-data (`.kaldrax/runs/`)

## Requirements

- Node.js 20.19+ or 22.12+
- Rust stable toolchain
- Windows WebView2 Runtime
- Microsoft C++ Build Tools
- Python 3.11+ and a local KALDRAX source checkout are required only for desktop development mode. Packaged Windows MSI/NSIS installs carry the frozen engine and do not require a separate Python installation, Git checkout, Node.js or Rust toolchain.

## Prepare the Python engine

From the KALDRAX Python repository:

```powershell
python -m pip install -e ".[dev]"
python -m kaldrax.cli --help
python -m pytest -q
```

Packaged Windows builds auto-detect the bundled engine and benchmark resources at first launch. Development builds without those resources use the source integration: open Settings and select the KALDRAX project folder containing `pyproject.toml` and `src/kaldrax/cli.py`, then set the Python executable. The Windows build workflow creates MSI/NSIS installers and installs the NSIS package on a Windows runner to smoke-test the bundled CLI without calling system Python.

## Run the desktop app

From this directory:

```powershell
npm install
npm run desktop:dev
```

Browser-only preview (the native Tauri commands are not available in a normal browser):

```powershell
npm run dev
```

## Desktop workflows currently connected

### Engine connection
Settings verifies the packaged frozen CLI when installed, or the selected Python executable/source checkout in development mode. Packaged mode resolves the executable from Tauri's resource directory and launches it directly; no webview shell access is introduced.

### Offline demo
Overview can run the real Python CLI's credential-free demo. It uses the Python engine's deterministic demo executor/evaluator, persists a run report and SQLite episodic memory, then opens the resulting report.

### LLM-backed task
The Task Builder maps to the v0.5 task contract and CLI:
- objective
- one or more unique acceptance criteria
- maximum iterations (1–20 in the desktop form)
- project ID (memory isolation key, not a repository path)
- optional agent namespace
- memory retrieval limit

A key issued by the configured model provider, an executor model and a different evaluator model are required only for live LLM-backed tasks. This is not a KALDRAX service/account key. The offline demo, local SQLite memory and deterministic benchmarks do not require provider credentials. The provider key is held in React state for the current app session and passed to the local Rust bridge as a child-process environment value. It is not stored in LocalStorage or reports. LLM prompts and candidate content are sent to the configured provider. This integration currently accepts HTTPS provider endpoints; direct loopback Ollama support is not implemented yet. Offline workflows do not require a provider key.

### Run history and details
Runs are read from actual JSON files in the OS application-data directory under `.kaldrax/runs/`. Run detail displays the engine event sequence, iteration evaluations, criterion evidence quotes, final candidate and provider budget/usage when the report includes it. The candidate is a text artifact and does not imply repository files were changed.

## Connected workflow surfaces

### Memory review
The Memory screen searches project-scoped SQLite records, optionally includes pending semantic proposals, and supports explicit approve/reject actions. The Contradictions tab shows open candidate pairs and requires a human to choose which memory remains. Pending facts are not promoted automatically.

### Planner-builder-reviewer team
Team Runs uses four distinct model identifiers and the shared run budget. The normal workflow is planner → builder → reviewer → independent evaluator. Repository mode is optional and requires a selected clean Git worktree. It captures a bounded snapshot, asks the builder for a unified patch, verifies the staged patch in a disposable Docker copy, and runs reviewer/evaluator gates. Repository mode is a dry run by default. Applying requires a separate UI confirmation and only occurs after sandbox verification, reviewer approval and independent evaluation pass.

### Docker sandbox
The Sandbox screen runs one selected Python file in a disposable container with network disabled, read-only root, dropped capabilities, unprivileged UID, and CPU, memory, PID, timeout and output limits. The selected file is the only workspace input; this is not a full-project sandbox.

### Live progress and cancellation
Offline demo, LLM task, team and sandbox operations expose operation state. Python progress events are tailed from a local JSONL journal and polled by the desktop. Cancellation terminates local CLI tasks, and Docker cancellation kills the active container. For repository-team mode, cancellation is checked at role boundaries and by the workspace sandbox; an already-submitted provider request may still complete before the next cancellation check.

### Repository workspace
The Repository screen inspects a selected Git worktree, reports branch/HEAD/dirty status, lists supported text/code files, and reads individual UTF-8 files. Single-file edits require the current SHA-256, an explicit confirmation, an automatic backup and an atomic replacement. Secret/runtime/build directories and symlink paths are excluded or rejected.

### Remaining boundaries
The desktop does not expose arbitrary shell execution, dependency provisioning, automatic Git commits/pushes, or deployment. The single-file sandbox is not a full repository test runner. Repository-team mode can run a selected verification module in a disposable copy, but the live working tree is only changed after explicit approval and all acceptance gates pass.

## Commands

```powershell
npm run build
npm run lint
cargo check --manifest-path src-tauri/Cargo.toml
npm run desktop:build
```

Windows installers are generated under `src-tauri/target/release/bundle/` (MSI and NSIS).

## Design and UX decisions

- `DESIGN.md`: visual tokens, layout, typography and component guidance.
- `UX-CONTRACT.md`: navigation and interaction behavior.
- `ENGINEERING-WORKFLOW-UI.md`: v0.5 engine-to-desktop workflow contract and integration limits.

The product uses a single expandable near-black navigation rail. There is no second contextual sidebar.

## Integrated v0.6 workflows

The desktop now connects these v0.5 engine capabilities:
- Memory: search active/pending memories, approve/reject pending records, inspect open contradiction candidates and resolve a conflict by explicitly keeping one side.
- Team runs: submit a planner-builder-reviewer task with four distinct models, shared budget, per-role trace and independent final evaluation.
- Docker sandbox: select one .py file, configure timeout/memory/CPU/PID caps, inspect stdout/stderr/exit status, and cancel the operation.
- Live operations: task, offline demo, team and sandbox processes expose operation state; run/team progress is streamed from JSONL event journals and cancellable.
- Repository workspace: inspect a selected Git worktree, list/read supported text/code files and explicitly apply a single-file replacement. Existing files require the last-read SHA-256; backups are created before atomic writes.

Repository writes are operator-approved and single-file only. The desktop does not run arbitrary commands from a selected worktree, install its dependencies, run all project tests, create commits, push branches or deploy. The Docker sandbox still executes a single Python file rather than a complete project.


### Local application data

Desktop-owned state is stored under the operating system application-data directory in a `.kaldrax/` subdirectory, separate from the engine checkout and installer resources. On first engine verification, the desktop copies legacy `.kaldrax/` files from the selected checkout into the app-data directory. The original checkout data is not removed or overwritten. SQLite memory is copied with SQLite's backup API so committed WAL transactions are included. Existing destination files take precedence. A per-source migration marker makes the operation idempotent; symlinks and special files are skipped.


### Packaged Windows runtime

The MSI/NSIS bundle contains the PyInstaller one-folder CLI under the Tauri resource directory at `kaldrax-engine/`, plus benchmark datasets at `benchmarks/`. The native Rust bridge resolves the packaged executable through Tauri's resource path resolver and verifies that a packaged runtime request matches that resolved resource root. It launches the executable directly with a fixed argument vector; the webview is not granted arbitrary shell execution. When the packaged resource is absent, developer mode can use a selected source checkout and Python interpreter.

### Data migration

Desktop state lives in the platform application-data directory, not inside the install or engine resources. The first source-mode connection copies legacy checkout-local `.kaldrax/` state without deleting the source. SQLite is copied through the online backup API, existing destination files are not overwritten, symlinks/special files are skipped, and an idempotency marker is recorded. The installer smoke exercises an isolated data directory and does not use provider credentials.


### Windows runtime prerequisite

The packaged desktop includes the KALDRAX engine and benchmark resources and does not need a separate Python installation or source checkout. The default Tauri Windows bundle uses the WebView2 bootstrapper; recent Windows 10/11 releases include WebView2, but a machine missing it needs internet access for the bootstrapper. An offline WebView2 installer can be selected later at the cost of roughly 127 MB additional installer size.


### CI-verified Windows install

Windows CI builds both MSI and NSIS packages. The NSIS package is installed and smoke-tested with the bundled engine, including a migration from a legacy checkout, offline demo, SQLite/report persistence, and a first-run launch of the installed Tauri desktop. The GUI startup check verifies native engine detection through the webview but is not a visual or interactive UI test.
