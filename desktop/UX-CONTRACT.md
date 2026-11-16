# KALDRAX UX Contract

## Product context
- Audience: an engineer operating local Python KALDRAX projects and bounded execution runs.
- Primary jobs: verify the local engine, submit bounded tasks, inspect run evidence, review project memory, coordinate agent teams, inspect repositories, and explicitly apply guarded source edits.
- Active locale: English. Run timestamps use the host's local timezone.
- Accessibility target: WCAG 2.2 AA baseline.

## Source of truth
- Python engine: `C:\Users\himan\Projects\kaldrax`, branch `main`, commit `98d85f9` at completion of this integration.
- Product and architecture: engine repository `docs/PRD.md`, `docs/ARCHITECTURE.md`, `README.md`, CLI and typed run models.
- UI design: `DESIGN.md`.
- Runtime token/component source: `src/styles/kaldrax.css`.
- Python output: JSON run reports under `.kaldrax/runs/`, SQLite memory under `.kaldrax/memory.sqlite3`.

## Canonical UI map
| Capability | Canonical owner | Source of truth | States | Verification |
|---|---|---|---|---|
| Single navigation rail | `KaldraxShell` | Route table in `src/pages/Kaldrax.tsx` | Collapsed / expanded / mobile horizontal | Viewport + interaction QA |
| Engine connection | Settings + Rust `verify_engine` | Selected engine path + Python CLI | Checking / connected / error | Native IPC check |
| Task contract | `TaskBuilder` | v0.5 Python task model and `kaldrax run` | Incomplete / ready / submitting / error | Form validation + engine tests |
| Offline demo | Overview + Rust `run_offline_demo` | Actual CLI run report | Idle / running / success / error | Persisted report smoke |
| Run history | `RunsPage` | JSON files under `.kaldrax/runs/` | Loading / empty / populated / error | Report loading |
| Run detail | `RunDetailPage` | `RunReport`, events, evaluations, evidence, budget | Loading / populated / missing | Report fixture |
| Memory | `MemoryPage` + native memory commands | Project-scoped SQLite records and conflict table | Search / active / pending / conflict | CLI-backed actions |
| Team runs | `TeamRunsPage` + operation manager | Team report JSON + progress journal | Configured / running / completed / failed / cancelled | Python role tests + IPC contract |
| Repository team mode | `TeamRunsPage` + `RepositoryTeamCoordinator` | Clean Git snapshot, unified patch, Docker verification, reviewer and evaluator | Dry-run / applying / applied / blocked / cancelled | Python repository-team tests |
| Sandbox | `SandboxPage` + operation manager | `SandboxResult` | Configured / running / completed / cancelled / failed | Sandbox tests |
| Repository workspace | `RepositoryPage` + `RepositoryWorkspace` | Selected local Git worktree | Loading / clean / dirty / read / edit / stale hash / applied | Path/hash/backup tests |
| Operation progress | `OperationPanel` + Tauri operation manager | JSONL progress journal and process state | Running / cancelling / completed / failed / cancelled | Progress/cancel IPC contract |

## Task contract rules
- Objective is required and non-empty.
- Acceptance criteria are repeatable, required, non-empty and unique (case-insensitive in the UI).
- Maximum iterations must be 1–20 in the desktop form.
- Project ID is a memory isolation key, not a repository path.
- Optional agent ID and memory limit map to the v0.5 CLI options.
- Provider-backed runs require an API key, an executor model and a different evaluator model.
- Never store the provider key in LocalStorage, settings JSON, reports, or logs.

## Team workflow rules
- Planner, builder, reviewer and evaluator must use four distinct model identifiers.
- All roles share the run budget and execute sequentially.
- Repository mode requires a selected clean Git worktree and Docker. The engine captures a bounded snapshot and verifies a proposed unified patch in a disposable copy.
- Repository mode is dry-run by default. Applying requires a separate confirmation, successful sandbox verification, reviewer approval and independent evaluator PASS.
- The engine rechecks the base commit and clean worktree before patch application. It does not create commits or push branches.
- Cancellation is checked at role boundaries and inside the Docker workspace runner. A provider request already submitted may finish before the next cancellation check.

## Run presentation
- Terminal statuses come from the engine: `passed`, `failed`, `limit_reached`.
- Render ordered event sequence and timestamps from the report.
- Per-iteration evaluations show evaluator name, satisfied/missing criteria and exact evidence quotes.
- Final candidate is a text artifact; do not imply a normal task run patched repository files.
- Render usage fields only when a report provides them; label estimated cost as estimated.
- Do not invent live run state from a persisted terminal report.

## Memory review safeguards
- Memory search can include pending proposals for human review; active memories remain the default retrieval context for future runs.
- Pending semantic extractions require explicit human approval before retrieval.
- Conflicts require a human to choose which memory remains. The other record is superseded with provenance.
- Do not approve, reject, or resolve memory conflicts automatically.

## Repository editing safeguards
- File listing excludes secret/runtime/build directories and symlink entries.
- File reads are bounded to supported UTF-8 text files and include SHA-256.
- Replacing an existing file requires the hash from the last read; stale hashes are rejected.
- Existing files receive a backup under `.kaldrax/desktop-backups/` before an atomic replacement.
- Edits are single-file and operator-confirmed. There is no arbitrary shell command surface, automatic dependency installation, commit, push or deployment.

## Visual / interaction contract
- Preserve Runey-inspired geometry: one rounded near-black expandable rail, attached edge toggle, neutral workspace, white panels, subtle borders, compact top-right actions and black pill primary actions.
- No second contextual sidebar.
- Desktop rail: 84px collapsed, 260px expanded. Mobile rail remains horizontal and icon-only.
- Overview and Runs are driven by persisted JSON reports, not seeded metrics.
- Disabled/unavailable capabilities must explain why; no dead controls.
- Preserve empty, error, loading, offline, credential-missing, Docker-unavailable and partial states where relevant.
- Keyboard operation, visible focus, semantic labels, reduced-motion support and non-colour status cues are required.

## Local desktop security boundary
- The webview invokes only named Tauri commands; no arbitrary shell command API is exposed.
- Rust uses fixed Python module/CLI entry points and argument arrays, not shell-interpreted user command strings.
- Provider keys are passed to the Python child process through environment values for the current task and remain transient in UI session state.
- Task prompts and candidates can be sent to the configured LLM provider; disclose this before a run starts.
- Python owns orchestration, evaluation, memory and repository policy; the UI cannot override evaluator decisions.

## Verification record
- Python suite: 169 passed, 3 skipped. The symlink-backup test is skipped when the Windows host does not permit symlink creation.
- TypeScript/Vite production build: passed.
- Oxlint: 0 errors; 22 warnings remain, primarily in the pre-existing template and React effect patterns.
- Rust `cargo fmt --check` and `cargo check`: passed.
- Windows Tauri release build: passed; MSI and NSIS bundles produced.
- Earlier browser interaction QA validated desktop/mobile rail layout, run details and responsive overflow with a mocked Tauri IPC boundary. It does not replace a full native IPC end-to-end test.

## Known limits
- The Docker Sandbox screen runs one Python file; repository-team mode separately verifies a staged patch in a disposable Git-worktree copy.
- Repository team verification supports `unittest`, `pytest` or `compileall` inside Docker; it does not provision arbitrary dependencies or network access.
- Provider cancellation cannot guarantee that an already-submitted remote request is unprocessed or unbilled.
