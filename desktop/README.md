# KALDRAX Desktop

KALDRAX Desktop is a local-first engineering control center built with React, TypeScript, Vite, Rust and Tauri 2. The Python package remains the authority for task contracts, execution policy, evaluation, budgets and project memory.

## Technology

- Desktop runtime: Rust + Tauri 2
- UI: React 19 + TypeScript + Vite 8
- Styling: CSS, Runey-inspired single expandable navigation rail
- Engine: local Python KALDRAX CLI/package
- Memory: local SQLite under the Python engine's `.kaldrax/` directory
- Run artifacts: JSON reports under the Python engine's `.kaldrax/runs/` directory

## Requirements

- Node.js 20.19+ or 22.12+
- Rust stable toolchain
- Windows WebView2 Runtime
- Microsoft C++ Build Tools
- Python 3.11+
- A local KALDRAX Python checkout with its development extra installed

## Prepare the Python engine

From the KALDRAX Python repository:

```powershell
python -m pip install -e ".[dev]"
python -m kaldrax.cli --help
python -m pytest -q
```

The desktop's default engine folder is `C:\Users\himan\Projects\kaldrax`. Change it in Settings if your checkout lives elsewhere. The selected folder must contain `pyproject.toml` and `src/kaldrax/cli.py`.

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
Settings verifies the selected Python executable and engine checkout by running the fixed `python -m kaldrax.cli --help` command.

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

A provider API key, executor model and a different evaluator model are required. The API key is held in React state for the current app session and passed to the local Rust bridge as a child-process environment value. It is not stored in LocalStorage or reports. LLM prompts and candidate content are sent to the configured provider; use a local OpenAI-compatible endpoint if data must stay local.

### Run history and details
Runs are read from actual JSON files in `.kaldrax/runs/`. Run detail displays the engine event sequence, iteration evaluations, criterion evidence quotes, final candidate and provider budget/usage when the report includes it. The candidate is a text artifact and does not imply repository files were changed.

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
