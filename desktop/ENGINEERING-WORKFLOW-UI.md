# KALDRAX Engineering Workflow UI

**Engine:** KALDRAX v0.6.0, local Python control plane.
**Desktop:** Tauri 2 + Rust; React 19 + TypeScript + Vite 8.
**Visual reference:** Runey-inspired single expandable rail, no second sidebar.

## Product job

A local-first engineering operator defines a bounded task, starts a run or team workflow, watches actual progress, inspects independent evaluation evidence, reviews project memory, runs isolated Python files and explicitly edits supported files in a selected Git worktree.

The Python engine remains the authority for execution, budgets, evaluation, memory policy and repository write safety. The webview calls fixed Tauri commands only.

## Connected surfaces

| Surface | Backing capability | Desktop behavior |
|---|---|---|
| Overview | persisted run artifacts | actual run counts, latest runs and offline demo |
| Tasks | Python recursive engine + separate evaluator | objective, acceptance criteria, iterations, memory scope, provider setup |
| Runs / detail | JSON run report | events, evaluation evidence, candidate, token/cost budget |
| Memory | SQLite memory CLI | search, pending/active status, approve/reject, conflicts and explicit keep-one-side resolution |
| Team runs | bounded planner-builder-reviewer-evaluator coordinator | distinct model roles, cycle limit, role trace, independent final evaluation, optional gated repository patch workflow |
| Sandbox | Docker single-file Python runner | selected .py file, timeout/memory/CPU/PID controls, stdout/stderr, cancellation |
| Repository | guarded local Git workspace adapter | status, supported text/code listing, SHA-256 read, backup-backed single-file edit; repository-team patch verification is a separate opt-in path |
| Settings | local desktop config | Python path, provider/model roles, project memory scope, repository path |

## Task contract

Fields map to the Python task and CLI: objective; one or more unique acceptance criteria; maximum iterations; project ID (memory isolation key, not a filesystem path); optional agent ID; and memory retrieval limit. LLM-backed runs require an API key, executor model and a different evaluator model. The key remains in application memory and is passed to the local Python child process; it is not written to LocalStorage or run reports.

## Team workflow

The desktop launches the bounded local sequence: planner → builder → reviewer → independent evaluator. Four distinct model identifiers and a cycle limit from 1 to 5 are required. The final report is a pass only when reviewer approval and the independent evaluator both pass. Team runs share configured call/token/time/cost budgets and write per-role provenance to project/agent-scoped memory.

Optional repository mode requires a clean selected Git worktree. The planner receives a bounded path manifest; the builder receives the allowed source snapshot and returns a unified diff. KALDRAX stages that patch against the complete safe tracked checkout, verifies a disposable copy in Docker, then requires reviewer approval and an independent evaluator PASS. The optional full profile runs the complete pytest suite, full staged Python compilation, desktop Oxlint, and the Vite production build. It requires a prebuilt offline image containing pytest, Node.js/npm, and locked desktop dependencies. Dry-run is the default. Applying requires a separate confirmation and a clean/base-commit recheck. It never commits or pushes.

## Memory safeguards

- Active and pending records are distinguished. Pending extracted semantic memory is not active retrieval context.
- Approve/reject is an explicit reviewer action.
- An open conflict blocks approval until a human chooses which side to retain.
- Conflict resolution supersedes the other memory with provenance.
- Every card presents confidence, freshness/retrieval score, source run, agent scope and expiry where available.
- Contradiction detection is heuristic; do not present candidates as proven logical contradictions.

## Operation progress and cancellation

The Rust operation manager starts only named Python CLI operations. Run/demo/team append per-operation JSONL events; the desktop tails the journal and shows current process status, recent events, final JSON output or stderr. Ordinary local operations can be cancelled through the operation manager. Sandbox cancellation writes a sentinel observed by the runner, which stops the named Docker container. Repository-team cancellation is checked after each role boundary, by the active Docker workspace runner, and immediately before patch application. A provider request already submitted may still complete before the next check. A persisted run report remains terminal; transient running/cancelling states belong to the desktop operation manager.

## Docker sandbox boundary

Sandbox runs one selected Python file in a disposable Docker container with network disabled, read-only root, dropped capabilities, non-root UID, resource/time/output limits and pull-never image behavior. It does not mount an entire repository, install arbitrary dependencies or run a whole-project test suite.

## Repository workspace boundary

The repository adapter requires an actual Git worktree. It exposes branch/HEAD/working-tree status, bounded listing of supported UTF-8 text/code files, and file reads with SHA-256. Apply requires the hash returned by the last read; a changed file is rejected. Before atomic replacement the engine creates a backup beneath the selected repo's ignored `.kaldrax/desktop-backups/` directory. It rejects path traversal, protected directories, secret-like files and symbolic links. Existing files require the SHA-256 from the last read; stale content is rejected.

The direct editor is a user-reviewed, single-file operation. Separately, optional repository-team mode can synthesize a bounded unified patch, verify it in a disposable Docker copy with one selected module (`unittest`, `pytest`, or `compileall`), and apply only after the reviewer/evaluator gates and explicit approval. It does not provision arbitrary dependencies, permit network access in the sandbox, commit, push or deploy.

## Desktop security boundary

- No arbitrary command or shell endpoint is exposed to the webview.
- Rust constructs fixed argument arrays and named environment values.
- Provider credentials remain transient in the UI session and child-process environment.
- User task prompts and candidate content may be sent to the configured model provider. A local OpenAI-compatible endpoint can be used where appropriate.
- Repository writes require an explicit action and a matching content hash.

## Verification record — 2026-11-16

- Final combined Python engine suite on the merged main tree: 174 passed, 4 skipped. Windows symlink-permission guard cases skip when the host does not permit symlink creation.
- Python `compileall`: passed.
- Direct repository CLI smoke in a temporary Git repo: status, listing, SHA-256 read, guarded file apply, backup creation and dirty status passed.
- Frontend TypeScript/Vite production build: passed.
- Oxlint: 0 errors; 22 warnings remain, mainly React effect/Fast Refresh patterns and existing template components.
- Rust `cargo fmt --check` and `cargo check`: passed.
- Windows Tauri release build and both bundles: passed. MSI 3.14 MiB; NSIS 2.12 MiB.
- Earlier Playwright workflow QA used mocked Tauri IPC and a real Python report shape. It is not a native Tauri IPC end-to-end run; the latest repo-team cancellation result badge was not separately re-run through browser automation.

The Python engine changes are pushed to GitHub main at merge commit `9bed4fdf497a83f6e75807c38b7e355b4c815637`. The desktop Downloads directory itself is not a Git checkout, so its UI source and Windows installer outputs remain local files.
