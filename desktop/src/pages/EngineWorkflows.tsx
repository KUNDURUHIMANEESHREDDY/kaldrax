import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { Icon } from "../components/Icons";
import {
  listTeamRuns,
  memoryConflicts,
  memoryResolveConflict,
  memoryReview,
  memorySearch,
  repositoryApplyFile,
  repositoryFiles,
  repositoryReadFile,
  repositoryStatus,
  startSandboxRun,
  startTeamRun,
  type MemoryConflict,
  type MemoryItem,
  type OperationSnapshot,
  type RepositoryFile,
  type RepositoryFileContent,
  type RepositoryStatus,
  type SavedTeamReport,
  type TeamReport,
  type RepositoryTeamReport,
} from "../lib/engine";

export interface WorkflowSettings {
  enginePath: string;
  pythonExecutable: string;
  projectId: string;
  executorModel: string;
  evaluatorModel: string;
  plannerModel: string;
  reviewerModel: string;
  baseUrl: string;
  repositoryPath: string;
}
export interface WorkflowProps {
  settings: WorkflowSettings;
  apiKey: string;
  operation: OperationSnapshot | null;
  onOperationStarted: (operation: OperationSnapshot) => void;
  onSettingsChange: (settings: WorkflowSettings) => void;
  onCancelOperation: () => void;
}

function Header({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return <div className="kx-page-head"><div><div className="kx-eyebrow">KALDRAX ENGINEERING</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>;
}
function Badge({ tone = "neutral", children }: { tone?: string; children: ReactNode }) {
  return <span className={`kx-badge kx-badge--${tone.replaceAll("_", "-")}`}>{children}</span>;
}
function Alert({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <div className={`kx-alert ${error ? "kx-alert--error" : ""}`} role={error ? "alert" : "status"}>{children}</div>;
}
function formatTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}
export function OperationPanel({ operation, onCancel }: { operation: OperationSnapshot | null; onCancel: () => void }) {
  if (!operation) return null;
  const running = operation.status === "running" || operation.status === "cancelling";
  const latest = operation.progress.at(-1) ?? {};
  const latestMessage = typeof latest.message === "string" ? latest.message : operation.message;
  return <section className="kx-panel kw-operation">
    <div className="kx-panel__head"><div><h2>Execution status</h2><p>{operation.kind.replaceAll("_", " ")} · {operation.operationId}</p></div><Badge tone={operation.status}>{operation.status}</Badge></div>
    <div className="kw-operation__message"><span className={`kw-live-dot ${running ? "is-live" : ""}`}/><strong>{latestMessage}</strong></div>
    {operation.progress.length > 0 && <div className="kw-progress-list">{operation.progress.slice(-5).map((event, index) => <div className="kw-progress-line" key={index}><span>{String(event.event_type ?? "event").replaceAll("_", " ")}</span><small>{String(event.message ?? "")}</small></div>)}</div>}
    {operation.error && <Alert error>{operation.error}</Alert>}
    {operation.status === "completed" && operation.kind === "team_run" && <div className="kw-operation__message"><strong>Team report saved. Review its plan, role trace and independent evaluation below.</strong></div>}
    <div className="kw-operation__foot"><small>Started {formatTime(operation.startedAt)}{operation.finishedAt ? ` · Finished ${formatTime(operation.finishedAt)}` : ""}</small>{running ? <button className="kx-button kx-button--quiet" onClick={onCancel} disabled={operation.status === "cancelling"}><Icon name="x" size={14}/>{operation.status === "cancelling" ? "Cancelling…" : "Cancel operation"}</button> : <Badge tone={operation.status}>{operation.status}</Badge>}</div>
  </section>;
}

export function MemoryPage({ settings }: Pick<WorkflowProps, "settings">) {
  const [query, setQuery] = useState(settings.projectId);
  const [includePending, setIncludePending] = useState(true);
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [conflicts, setConflicts] = useState<MemoryConflict[]>([]);
  const [activeTab, setActiveTab] = useState<"search" | "conflicts">("search");
  const [reviewer, setReviewer] = useState("local-user");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const search = useCallback(async (event?: FormEvent) => {
    event?.preventDefault();
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await memorySearch({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
        projectId: settings.projectId, query, limit: 30, includePending,
      });
      setItems(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }, [settings.enginePath, settings.pythonExecutable, settings.projectId, query, includePending]);
  const loadConflicts = useCallback(async () => {
    setBusy(true); setError(""); setNotice("");
    try {
      setConflicts(await memoryConflicts({
        enginePath: settings.enginePath,
        pythonExecutable: settings.pythonExecutable,
        projectId: settings.projectId,
      }));
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }, [settings.enginePath, settings.pythonExecutable, settings.projectId]);
  useEffect(() => {
    let cancelled = false;
    void memorySearch({
      enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
      projectId: settings.projectId, query, limit: 30, includePending,
    }).then((result) => {
      if (!cancelled) setItems(result);
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { cancelled = true; };
  }, [settings.enginePath, settings.pythonExecutable, settings.projectId, query, includePending]);

  useEffect(() => {
    if (activeTab !== "conflicts") return;
    let cancelled = false;
    void memoryConflicts({
      enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
      projectId: settings.projectId,
    }).then((result) => {
      if (!cancelled) setConflicts(result);
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { cancelled = true; };
  }, [activeTab, settings.enginePath, settings.pythonExecutable, settings.projectId]);
  const review = async (item: MemoryItem, decision: "approve" | "reject") => {
    if (!window.confirm(`${decision === "approve" ? "Approve" : "Reject"} this pending memory? This changes future retrieval eligibility.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await memoryReview({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
        memoryId: item.id, decision, reviewer,
      });
      const message = typeof result.error === "string" ? result.error : `Memory ${decision} action completed.`;
      await search();
      await loadConflicts();
      if (result.error) setError(message); else setNotice(message);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  const resolve = async (conflict: MemoryConflict, keepMemoryId: string) => {
    if (!window.confirm("Resolve this contradiction and supersede the other memory? This cannot be undone automatically.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await memoryResolveConflict({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
        conflictId: conflict.id, keepMemoryId, reviewer,
      });
      await loadConflicts();
      await search();
      setNotice("Conflict resolved. The selected memory remains active; the other is superseded.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  return <>
    <Header title="Project memory" subtitle="Search provenance-backed memory, review pending extraction and resolve contradictions explicitly."/>
    <div className="kx-engine-status is-connected"><span className="kx-status-dot"/><strong>Project scope</strong><span>{settings.projectId}</span><span className="kx-strip-spacer"/><label className="kw-reviewer">Reviewer <input value={reviewer} onChange={event => setReviewer(event.target.value)} /></label></div>
    <div className="kw-tabs" role="tablist" aria-label="Memory views"><button role="tab" aria-selected={activeTab === "search"} className={activeTab === "search" ? "active" : ""} onClick={() => setActiveTab("search")}>Search & review</button><button role="tab" aria-selected={activeTab === "conflicts"} className={activeTab === "conflicts" ? "active" : ""} onClick={() => setActiveTab("conflicts")}>Contradictions <span>{conflicts.length}</span></button></div>
    {error && <Alert error>{error}</Alert>}{notice && <Alert>{notice}</Alert>}
    {activeTab === "search" ? <section className="kx-panel">
      <form className="kw-memory-search" onSubmit={search}><input aria-label="Search project memory" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search approved project knowledge…"/><label><input type="checkbox" checked={includePending} onChange={event => setIncludePending(event.target.checked)}/> Include pending</label><button className="kx-button kx-button--primary" type="submit" disabled={busy}>{busy ? "Searching…" : "Search memory"}</button></form>
      {items.length === 0 ? <div className="kx-empty"><Icon name="database" size={24}/><strong>No matching memories</strong><p>Run a task to create episodic memory, or broaden the search query.</p></div> : <div className="kw-memory-list">{items.map(item => <article className="kw-memory-card" key={item.id}>
        <div className="kw-memory-card__head"><div><span className="kw-memory-type">{item.type} · {item.retrieval_method}</span><h3>{item.summary || item.content.slice(0, 120)}</h3></div><Badge tone={item.status}>{item.status}</Badge></div>
        <p>{item.content}</p>
        <div className="kw-memory-meta"><span>Confidence {Math.round(item.confidence * 100)}%</span><span>Retrieval score {item.score.toFixed(3)}</span><span>Source run {item.source_run_id?.slice(0, 8) ?? "—"}</span><span>Expires {formatTime(item.expires_at)}</span></div>
        {item.status === "pending" && <div className="kw-memory-actions"><button className="kx-button kx-button--quiet" onClick={() => review(item, "reject")} disabled={busy}>Reject</button><button className="kx-button kx-button--primary" onClick={() => review(item, "approve")} disabled={busy}>Approve memory</button></div>}
      </article>)}</div>}
    </section> : <section className="kx-panel"><div className="kx-panel__head"><div><h2>Open contradiction candidates</h2><p>Heuristic matches only. Human review is required before either side is superseded.</p></div><button className="kx-button kx-button--quiet" onClick={loadConflicts} disabled={busy}><Icon name="refresh" size={14}/> Refresh</button></div>
      {conflicts.length === 0 ? <div className="kx-empty"><Icon name="shield" size={24}/><strong>No open conflicts</strong><p>The engine found no unresolved contradiction candidates for this project.</p></div> : conflicts.map(conflict => <article className="kw-conflict-card" key={conflict.id}><div className="kw-conflict-card__head"><Badge tone="warning">Open conflict</Badge><span>{formatTime(conflict.created_at)}</span></div><p>{conflict.reason}</p><div className="kw-conflict-sides"><div><small>LEFT MEMORY</small><code>{conflict.left_memory_id}</code><button className="kx-button kx-button--quiet" disabled={busy} onClick={() => resolve(conflict, conflict.left_memory_id)}>Keep left</button></div><div><small>RIGHT MEMORY</small><code>{conflict.right_memory_id}</code><button className="kx-button kx-button--quiet" disabled={busy} onClick={() => resolve(conflict, conflict.right_memory_id)}>Keep right</button></div></div></article>)}
    </section>}
  </>;
}

export function TeamRunsPage({ settings, apiKey, operation, onOperationStarted }: Pick<WorkflowProps, "settings" | "apiKey" | "operation" | "onOperationStarted">) {
  const [objective, setObjective] = useState("");
  const [criteriaText, setCriteriaText] = useState("");
  const [maxCycles, setMaxCycles] = useState(2);
  const [agentNamespace, setAgentNamespace] = useState("team");
  const [useRepository, setUseRepository] = useState(false);
  const [applyChanges, setApplyChanges] = useState(false);
  const [verifyModule, setVerifyModule] = useState<"unittest" | "pytest" | "compileall" | "full">("unittest");
  const [sandboxTimeout, setSandboxTimeout] = useState(120);
  const [reports, setReports] = useState<SavedTeamReport[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    setError("");
    try {
      setReports(await listTeamRuns(settings.enginePath));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }, [settings.enginePath]);
  const result = operation?.kind === "team_run" && ["completed", "cancelled"].includes(operation.status) && operation.result
    ? asRecord(operation.result) : null;
  const repositoryResult = result && typeof result.base_commit === "string"
    ? result as unknown as RepositoryTeamReport : null;
  const standardResult = result && !repositoryResult
    ? result as unknown as TeamReport : null;
  const criteria = criteriaText.split("\n").map(value => value.trim()).filter(Boolean);
  const criteriaUnique = new Set(criteria.map(value => value.toLocaleLowerCase())).size === criteria.length;
  const models = [settings.plannerModel, settings.executorModel, settings.reviewerModel, settings.evaluatorModel].map(value => value.trim().toLowerCase());
  const distinctModels = models.every(Boolean) && new Set(models).size === 4;
  const canRun = Boolean(
    apiKey.trim() && objective.trim() && criteria.length && criteriaUnique &&
    maxCycles >= 1 && maxCycles <= 5 && distinctModels && agentNamespace.trim() &&
    (!useRepository || settings.repositoryPath.trim()) &&
    sandboxTimeout >= 1 && sandboxTimeout <= 120
  );
  useEffect(() => {
    let cancelled = false;
    void listTeamRuns(settings.enginePath).then((result) => {
      if (!cancelled) setReports(result);
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { cancelled = true; };
  }, [settings.enginePath, settings.pythonExecutable, operation?.status]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (applyChanges && !window.confirm(
      "The repository team will only apply its generated Git patch after sandbox verification, reviewer approval and independent evaluation pass. Apply the validated patch to the selected working tree? A clean Git working tree is required."
    )) return;
    setBusy(true); setError("");
    try {
      const snapshot = await startTeamRun({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
        objective, acceptanceCriteria: criteria, projectId: settings.projectId,
        agentNamespace, maxCycles, apiKey, plannerModel: settings.plannerModel,
        builderModel: settings.executorModel, reviewerModel: settings.reviewerModel,
        evaluatorModel: settings.evaluatorModel, baseUrl: settings.baseUrl || undefined,
        workspacePath: useRepository ? settings.repositoryPath : undefined,
        applyChanges: useRepository && applyChanges,
        verifyModule: useRepository ? verifyModule : undefined,
        sandboxTimeoutSeconds: useRepository ? sandboxTimeout : undefined,
      });
      onOperationStarted(snapshot);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  const reportCycles = (report: SavedTeamReport) => "base_commit" in report ? report.cycles.length : report.cycles;
  return <>
    <Header title="Team runs" subtitle="Run planner ? builder ? reviewer ? independent evaluator, optionally against a disposable Git-worktree snapshot."/>
    {error && <Alert error>{error}</Alert>}
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>New team run</h2><p>Four distinct models share one provider-call, token and time budget. Role execution is sequential.</p></div><Badge tone={canRun ? "passed" : "neutral"}>{canRun ? "Ready" : "Configuration required"}</Badge></div>
      <form className="kx-task-form" onSubmit={submit}>
        <label className="kx-field">Objective<textarea rows={2} value={objective} onChange={event => setObjective(event.target.value)} required placeholder="Describe the engineering outcome for the team?"/></label>
        <label className="kx-field">Acceptance criteria <small>One criterion per line; each must be unique.</small><textarea rows={4} value={criteriaText} onChange={event => setCriteriaText(event.target.value)} required placeholder={"Tests cover the requested behavior\nKnown risks are documented"}/></label>
        {!criteriaUnique && <Alert>Acceptance criteria must be unique.</Alert>}
        <div className="kx-form-grid"><label className="kx-field">Maximum cycles<input type="number" min={1} max={5} value={maxCycles} onChange={event => setMaxCycles(Number(event.target.value))}/></label><label className="kx-field">Agent namespace<input value={agentNamespace} onChange={event => setAgentNamespace(event.target.value)}/></label></div>
        <div className="kw-role-grid">{["Planner", "Builder", "Reviewer", "Evaluator"].map((role, index) => <div key={role}><small>{role}</small><strong>{[settings.plannerModel, settings.executorModel, settings.reviewerModel, settings.evaluatorModel][index] || "Not configured"}</strong></div>)}</div>
        {!apiKey && <Alert>Enter the provider API key in Settings. It is session-only and is not stored.</Alert>}
        {!distinctModels && <Alert>Configure four different model identifiers in Settings. Planner, builder, reviewer and evaluator must all be distinct.</Alert>}
        <section className="kw-repo-team-mode">
          <label className="kw-repo-team-mode__toggle">
            <input type="checkbox" checked={useRepository} onChange={event => { setUseRepository(event.target.checked); if (!event.target.checked) setApplyChanges(false); }}/>
            <span><strong>Work against a Git repository</strong><small>Generate a unified diff, verify it in a disposable Docker copy, review it and independently evaluate the result.</small></span>
          </label>
          {useRepository && <>
            <div className="kw-repo-team-mode__path"><small>SELECTED REPOSITORY</small><code>{settings.repositoryPath || "No repository selected ? configure it in Settings."}</code></div>
            <div className="kx-form-grid">
              <label className="kx-field">Verification command
                <select value={verifyModule} onChange={event => setVerifyModule(event.target.value as typeof verifyModule)}>
                  <option value="full">Full repository (pytest + compileall + desktop build)</option><option value="unittest">Python unittest</option><option value="pytest">pytest</option><option value="compileall">Python compileall</option>
                </select>
              </label>
              <label className="kx-field">Sandbox timeout (seconds)
                <input type="number" min={1} max={120} value={sandboxTimeout} onChange={event => setSandboxTimeout(Number(event.target.value))}/>
              </label>
            </div>
            <div className="kw-repo-team-mode__notice">
              The engine requires a clean Git working tree, captures a bounded source snapshot, excludes secret files, and tests only a disposable copy with Docker networking disabled. No repository file is changed in dry-run mode.
            </div>
            <label className="kw-repo-team-mode__apply">
              <input type="checkbox" checked={applyChanges} onChange={event => setApplyChanges(event.target.checked)}/>
              <span><strong>Apply the patch to this working tree after all gates pass</strong><small>Off by default. Applying requires successful sandbox verification, reviewer approval and independent evaluator PASS. The engine rechecks the base commit and clean worktree before applying. It does not commit or push.</small></span>
            </label>
          </>}
        </section>
        <div className="kx-form-submit"><span>{useRepository
          ? applyChanges
            ? "Explicit apply is enabled. KALDRAX will not modify the selected checkout unless all verification and review gates pass."
            : "Repository mode is a dry run. The selected checkout remains unchanged; the proposed patch and sandbox evidence are saved in the report."
          : "Planner, builder, reviewer and evaluator each create a separate trace. The workflow passes only when reviewer approval and the independent evaluator both pass."}
        </span><button className="kx-button kx-button--primary" type="submit" disabled={!canRun || busy}>{busy ? "Starting team?" : useRepository ? applyChanges ? "Verify and apply patch" : "Run repository dry-run" : "Start team run"}</button></div>
      </form>
    </section>
    {repositoryResult && <section className="kx-panel"><div className="kx-panel__head"><div><h2>Repository team result</h2><p>{repositoryResult.objective}</p></div><Badge tone={repositoryResult.cancelled ? "neutral" : repositoryResult.status}>{repositoryResult.cancelled ? "cancelled" : repositoryResult.status}</Badge></div>
      <div className="kw-repo-stats"><div><small>BASE COMMIT</small><strong>{repositoryResult.base_commit.slice(0, 12)}</strong></div><div><small>CHANGED FILES</small><strong>{repositoryResult.changed_files.length}</strong></div><div><small>CHECKOUT</small><strong>{repositoryResult.applied ? "Patch applied" : "Dry run only"}</strong></div></div>
      <p>{repositoryResult.summary}</p>
      <div className="kw-team-evaluation"><strong>Reviewer</strong><Badge tone={repositoryResult.reviewer_approved ? "passed" : "failed"}>{repositoryResult.reviewer_approved ? "Approved" : "Not approved"}</Badge>{repositoryResult.reviewer_findings.map((finding, index) => <p key={index}>{finding}</p>)}</div>
      <div className="kw-team-evaluation"><strong>Independent evaluator</strong><Badge tone={repositoryResult.evaluation?.passed ? "passed" : "failed"}>{repositoryResult.evaluation?.passed ? "Passed" : "Not passed"}</Badge>{repositoryResult.evaluation?.missing?.map(item => <p key={item}>Missing: {item}</p>)}</div>
      {repositoryResult.verification && <div className="kw-team-plan"><small>DISPOSABLE DOCKER VERIFICATION</small><pre>{JSON.stringify(repositoryResult.verification, null, 2)}</pre></div>}
      <div className="kw-team-plan"><small>CHANGED FILES</small><pre>{repositoryResult.changed_files.join("\n") || "No files changed."}</pre></div>
      <div className="kw-team-plan"><small>UNIFIED PATCH</small><pre>{repositoryResult.patch || "No patch generated."}</pre></div>
    </section>}
    {standardResult && <section className="kx-panel"><div className="kx-panel__head"><div><h2>Current team result</h2><p>{standardResult.objective}</p></div><Badge tone={standardResult.status}>{standardResult.status}</Badge></div><div className="kw-team-plan"><small>PLAN</small><pre>{standardResult.plan}</pre></div><div className="kw-team-trace">{standardResult.trace?.map(trace => <article key={trace.sequence}><div><Badge>{trace.role}</Badge><span>Cycle {trace.cycle}</span><small>{trace.agent_id}</small></div><p>{trace.output_excerpt}</p></article>)}</div><div className="kw-team-evaluation"><strong>Independent evaluation</strong><Badge tone={standardResult.evaluation?.passed ? "passed" : "failed"}>{standardResult.evaluation?.passed ? "Passed" : "Not passed"}</Badge>{standardResult.evaluation?.missing?.map(item => <p key={item}>Missing: {item}</p>)}</div></section>}
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Saved team runs</h2><p>{reports.length} persisted team report{reports.length === 1 ? "" : "s"}</p></div><button className="kx-text-button" onClick={() => void refresh()}>Refresh <Icon name="refresh" size={14}/></button></div>{reports.length ? <div className="kw-team-list">{reports.map(report => <article key={report.run_id}><div><strong>{report.objective}</strong><small>{report.run_id} ? {reportCycles(report)} cycles ? {formatTime(report.created_at)} ? {"base_commit" in report ? report.applied ? "patch applied" : "dry run" : "agent team"}</small></div><Badge tone={report.status}>{report.status}</Badge></article>)}</div> : <div className="kx-empty"><Icon name="users" size={24}/><strong>No team reports yet</strong><p>Configure the four distinct models and start a team run.</p></div>}</section>
  </>;
}

export function SandboxPage({ settings, operation, onOperationStarted }: Pick<WorkflowProps, "settings" | "operation" | "onOperationStarted">) {
  const [sourcePath, setSourcePath] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState(15);
  const [memoryMb, setMemoryMb] = useState(256);
  const [cpuCount, setCpuCount] = useState(1);
  const [pidsLimit, setPidsLimit] = useState(64);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const result = operation?.kind === "sandbox_run" ? asRecord(operation.result) : {};
  const chooseFile = async () => {
    const selected = await open({ multiple: false, directory: false, title: "Select Python file for sandbox", filters: [{ name: "Python", extensions: ["py"] }] });
    if (typeof selected === "string") setSourcePath(selected);
  };
  const run = async () => {
    if (!sourcePath) { setError("Select a Python file first."); return; }
    setBusy(true); setError("");
    try {
      const snapshot = await startSandboxRun({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable, sourcePath,
        timeoutSeconds, memoryMb, cpuCount, pidsLimit,
      });
      onOperationStarted(snapshot);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  return <>
    <Header title="Docker sandbox" subtitle="Execute one selected Python file in a disposable, network-isolated Docker container."/>
    {error && <Alert error>{error}</Alert>}
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Sandbox input</h2><p>Only the selected file is mounted. This is not a full repository test runner.</p></div><Badge>Python file only</Badge></div>
      <div className="kw-file-picker"><input readOnly value={sourcePath} placeholder="Select a .py file to execute"/><button className="kx-button kx-button--quiet" onClick={chooseFile}>Browse</button></div>
      <div className="kx-form-grid"><label className="kx-field">Timeout (seconds)<input type="number" min={1} max={120} value={timeoutSeconds} onChange={event => setTimeoutSeconds(Number(event.target.value))}/></label><label className="kx-field">Memory (MB)<input type="number" min={64} max={1024} value={memoryMb} onChange={event => setMemoryMb(Number(event.target.value))}/></label><label className="kx-field">CPU count<input type="number" min={0.25} max={2} step={0.25} value={cpuCount} onChange={event => setCpuCount(Number(event.target.value))}/></label><label className="kx-field">PID limit<input type="number" min={16} max={128} value={pidsLimit} onChange={event => setPidsLimit(Number(event.target.value))}/></label></div>
      <div className="kw-sandbox-guarantees"><span><Icon name="shield" size={15}/> Network disabled</span><span><Icon name="lock" size={15}/> Read-only root</span><span><Icon name="clock" size={15}/> Bounded timeout</span><span><Icon name="sliders" size={15}/> CPU / memory / PID limits</span></div>
      <div className="kx-form-submit"><span>Docker must be installed and running, and python:3.13-slim must already be available locally. The engine uses --pull=never.</span><button className="kx-button kx-button--primary" onClick={run} disabled={busy || !sourcePath}>{busy ? "Starting sandbox…" : "Run in sandbox"}</button></div>
    </section>
    {operation?.kind === "sandbox_run" && operation.status === "completed" && <section className="kx-panel"><div className="kx-panel__head"><div><h2>Sandbox result</h2><p>{String(result.container_image ?? "Container image unavailable")}</p></div><Badge tone={result.cancelled ? "failed" : result.timed_out ? "warning" : Number(result.exit_code) === 0 ? "passed" : "failed"}>{result.cancelled ? "Cancelled" : result.timed_out ? "Timed out" : `Exit ${String(result.exit_code)}`}</Badge></div><div className="kw-sandbox-result__stats"><span>Duration <b>{String(result.duration_ms ?? "—")} ms</b></span><span>Output truncated <b>{String(result.output_truncated ?? false)}</b></span></div><h3>stdout</h3><pre className="kx-output">{String(result.stdout ?? "(empty)")}</pre><h3>stderr</h3><pre className="kx-output kw-stderr">{String(result.stderr ?? "(empty)")}</pre></section>}
  </>;
}

export function RepositoryPage({ settings, onSettingsChange }: Pick<WorkflowProps, "settings" | "onSettingsChange">) {
  const [status, setStatus] = useState<RepositoryStatus | null>(null);
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [selected, setSelected] = useState<RepositoryFileContent | null>(null);
  const [editedContent, setEditedContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dirty = Boolean(selected && editedContent !== selected.content);
  const readStatus = useCallback((repoPath: string) => Promise.all([
    repositoryStatus({ enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable, repositoryPath: repoPath }),
    repositoryFiles({ enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable, repositoryPath: repoPath, directory: ".", limit: 300 }),
  ]), [settings.enginePath, settings.pythonExecutable]);

  const loadStatus = useCallback(async (repoPath = settings.repositoryPath) => {
    if (!repoPath.trim()) return;
    setBusy(true); setError("");
    try {
      const [snapshot, listing] = await readStatus(repoPath);
      setStatus(snapshot); setFiles(listing);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  }, [readStatus, settings.repositoryPath]);

  useEffect(() => {
    if (!settings.repositoryPath.trim()) return;
    let cancelled = false;
    void readStatus(settings.repositoryPath).then(([snapshot, listing]) => {
      if (!cancelled) { setStatus(snapshot); setFiles(listing); }
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { cancelled = true; };
  }, [readStatus, settings.repositoryPath]);
  const chooseRepository = async () => {
    const selectedPath = await open({ directory: true, multiple: false, title: "Select Git repository" });
    if (typeof selectedPath === "string") {
      onSettingsChange({ ...settings, repositoryPath: selectedPath });
      setSelected(null); setEditedContent("");
    }
  };
  const openFile = async (file: RepositoryFile) => {
    setBusy(true); setError(""); setNotice("");
    try {
      const loaded = await repositoryReadFile({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
        repositoryPath: settings.repositoryPath, relativePath: file.path,
      });
      setSelected(loaded); setEditedContent(loaded.content);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  const apply = async () => {
    if (!selected || !dirty) return;
    if (!window.confirm(`Apply changes to ${selected.path}? The current file will be backed up first.`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await repositoryApplyFile({
        enginePath: settings.enginePath, pythonExecutable: settings.pythonExecutable,
        repositoryPath: settings.repositoryPath, relativePath: selected.path,
        content: editedContent, expectedSha256: selected.sha256,
      });
      await openFile({ path: result.path, size: result.size });
      await loadStatus();
      setNotice(`Applied ${result.path}. Backup: ${result.backup_path ?? "new file"}.`);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  const discard = () => { if (selected) setEditedContent(selected.content); };
  return <>
    <Header title="Repository workspace" subtitle="Inspect a selected Git worktree and apply explicit, hash-checked single-file edits." action={<button className="kx-button kx-button--quiet" onClick={chooseRepository}><Icon name="layers" size={15}/> Change repository</button>}/>
    {!settings.repositoryPath && <Alert>Select a local Git repository to begin.</Alert>}
    {error && <Alert error>{error}</Alert>}{notice && <Alert>{notice}</Alert>}
    {status && <section className="kx-panel"><div className="kx-panel__head"><div><h2>Working tree</h2><p>{status.root}</p></div><Badge tone={status.clean ? "passed" : "warning"}>{status.clean ? "Clean" : "Uncommitted changes"}</Badge></div><div className="kw-repo-stats"><div><small>Branch</small><strong>{status.branch}</strong></div><div><small>HEAD</small><strong>{status.head}</strong></div><div><small>Changes</small><strong>{status.changes.length}</strong></div></div>{status.changes.length > 0 && <div className="kw-change-list">{status.changes.map(change => <div key={change.path}><code>{change.code}</code><span>{change.path}</span></div>)}</div>}</section>}
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Source files</h2><p>{files.length} supported text/code files · protected folders and secret files are excluded</p></div><button className="kx-button kx-button--quiet" onClick={() => loadStatus()} disabled={busy}><Icon name="refresh" size={14}/> Refresh</button></div><div className="kw-repo-browser"><div className="kw-file-list">{files.map(file => <button key={file.path} className={selected?.path === file.path ? "active" : ""} onClick={() => openFile(file)}><Icon name="file" size={14}/><span>{file.path}</span><small>{file.size.toLocaleString()} B</small></button>)}</div><div className="kw-editor"><div className="kw-editor__head"><strong>{selected?.path ?? "Select a file"}</strong>{selected && <span>SHA-256 {selected.sha256.slice(0, 12)}…</span>}</div>{selected ? <><textarea spellCheck={false} value={editedContent} onChange={event => setEditedContent(event.target.value)} aria-label="Repository file content"/><div className="kw-editor__actions"><span>{dirty ? "Unsaved edit" : "No local edits"} · {editedContent.length.toLocaleString()} characters</span><button className="kx-button kx-button--quiet" disabled={!dirty || busy} onClick={discard}>Discard</button><button className="kx-button kx-button--primary" disabled={!dirty || busy} onClick={apply}>Apply file edit</button></div></> : <div className="kx-empty"><Icon name="file" size={24}/><strong>No file selected</strong><p>Choose a file from the repository list to inspect or edit it.</p></div>}</div></div><p className="kw-repo-warning">Edits are explicit and limited to one UTF-8 text file at a time. A SHA-256 precondition prevents overwriting a file that changed after it was read. The engine creates a backup before an atomic replacement. This does not commit, push or run the repository's tests.</p></section>
  </>;
}
