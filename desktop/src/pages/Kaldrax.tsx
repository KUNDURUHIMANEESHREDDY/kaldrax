import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { open } from "@tauri-apps/plugin-dialog";
import { Icon, type IconName } from "../components/Icons";
import {
  cancelOperation,
  getOperation,
  getRunReport,
  listRuns,
  startOfflineDemo,
  startTaskRun,
  verifyEngine,
  type EngineStatus,
  type OperationSnapshot,
  type RunReport,
  type RunStatus,
  type TaskRunRequest,
} from "../lib/engine";
import {
  MemoryPage, OperationPanel, RepositoryPage, SandboxPage, TeamRunsPage,
  type WorkflowSettings,
} from "./EngineWorkflows";

type Settings = WorkflowSettings;
const settingsKey = "kaldrax.desktop.settings.v2";
const defaultSettings: Settings = {
  enginePath: "",
  pythonExecutable: "python",
  projectId: "kaldrax-core",
  executorModel: "",
  evaluatorModel: "",
  plannerModel: "",
  reviewerModel: "",
  baseUrl: "",
  repositoryPath: "",
};
const navigation: { label: string; path: string; icon: IconName; group: string }[] = [
  { label: "Overview", path: "/", icon: "grid", group: "WORKSPACE" },
  { label: "Tasks", path: "/tasks", icon: "clipboard", group: "WORKSPACE" },
  { label: "Runs", path: "/runs", icon: "activity", group: "WORKSPACE" },
  { label: "Repository", path: "/repository", icon: "layers", group: "WORKSPACE" },
  { label: "Team runs", path: "/team", icon: "users", group: "EXECUTION" },
  { label: "Sandbox", path: "/sandbox", icon: "package", group: "EXECUTION" },
  { label: "Memory", path: "/memory", icon: "database", group: "INTELLIGENCE" },
  { label: "Settings", path: "/settings", icon: "settings", group: "SYSTEM" },
];

function loadSettings(): Settings {
  try {
    const saved = localStorage.getItem(settingsKey);
    if (saved) return { ...defaultSettings, ...(JSON.parse(saved) as Partial<Settings>) };
  } catch { /* Fall back to safe local defaults. */ }
  return defaultSettings;
}
function formatDate(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
function duration(report: RunReport): string {
  const times = report.events.map(event => Date.parse(event.timestamp)).filter(Number.isFinite);
  if (times.length < 2) return "—";
  return `${((Math.max(...times) - Math.min(...times)) / 1000).toFixed(2)}s`;
}
function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`kx-badge kx-badge--${status.replaceAll("_", "-")}`}>{status.replaceAll("_", " ")}</span>;
}
function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`kx-badge kx-badge--${tone.toLowerCase().replaceAll(" ", "-")}`}>{children}</span>;
}
function PageHeader({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return <div className="kx-page-head"><div><div className="kx-eyebrow">KALDRAX ENGINEERING</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>;
}
function EmptyState({ icon = "activity", title, detail, action }: { icon?: IconName; title: string; detail: string; action?: ReactNode }) {
  return <div className="kx-empty"><span className="kx-empty__glyph"><Icon name={icon} size={25}/></span><strong>{title}</strong><p>{detail}</p>{action}</div>;
}
function MetricCard({ label, value, note, icon }: { label: string; value: string; note: string; icon: IconName }) {
  return <article className="kx-metric"><div className="kx-metric__top"><span>{label}</span><span className="kx-metric__icon neutral"><Icon name={icon} size={17}/></span></div><strong>{value}</strong><small>{note}</small></article>;
}
function RunTable({ reports, onOpen }: { reports: RunReport[]; onOpen: (id: string) => void }) {
  return <div className="kx-table-wrap"><table className="kx-table"><thead><tr><th>Objective</th><th>Status</th><th>Iterations</th><th>Duration</th><th>Created</th></tr></thead><tbody>{reports.map(report => <tr key={report.run_id} onClick={() => onOpen(report.run_id)} className="kx-table-row" tabIndex={0} onKeyDown={event => { if (event.key === "Enter") onOpen(report.run_id); }}><td><div className="kx-task-cell"><span className="kx-task-id">{report.run_id.slice(0, 8)}</span><strong>{report.objective}</strong></div></td><td><StatusBadge status={report.status}/></td><td>{report.iterations}</td><td>{duration(report)}</td><td className="kx-muted">{formatDate(report.created_at)}</td></tr>)}</tbody></table></div>;
}
function OverviewPage({ reports, connected, busy, onDemo, onNewTask, onOpenRun, error }: {
  reports: RunReport[]; connected: boolean; busy: boolean; onDemo: () => void; onNewTask: () => void; onOpenRun: (id: string) => void; error: string;
}) {
  const passed = reports.filter(report => report.status === "passed").length;
  const failed = reports.filter(report => report.status === "failed").length;
  const limited = reports.filter(report => report.status === "limit_reached").length;
  return <>
    <PageHeader title="Overview" subtitle="Inspect real KALDRAX runs, independent evaluations and local engine health."
      action={<button className="kx-button kx-button--primary" onClick={onNewTask}><Icon name="plus" size={16}/> New task</button>}/>
    <div className={`kx-engine-status ${connected ? "is-connected" : "is-offline"}`}><span className="kx-status-dot"/><strong>{connected ? "Python engine connected" : "Python engine not connected"}</strong><span>{connected ? "Local CLI verified" : "Choose the KALDRAX source folder in Settings"}</span><span className="kx-strip-spacer"/><button className="kx-text-button" onClick={() => window.location.hash = "#/settings"}>Engine settings <Icon name="arrow-right" size={14}/></button></div>
    {error && <div className="kx-alert kx-alert--error" role="alert">{error}</div>}
    <div className="kx-metrics"><MetricCard label="Total runs" value={String(reports.length).padStart(2, "0")} note="Persisted reports" icon="activity"/><MetricCard label="Passed" value={String(passed).padStart(2, "0")} note="Independent evaluation passed" icon="check-circle"/><MetricCard label="Failed" value={String(failed).padStart(2, "0")} note="Execution or evaluation failure" icon="x"/><MetricCard label="Iteration limit" value={String(limited).padStart(2, "0")} note="Stopped at configured limit" icon="clock"/></div>
    <section className="kx-panel">
      <div className="kx-panel__head"><div><h2>Recent runs</h2><p>Loaded from the configured engine's .kaldrax/runs directory</p></div><button className="kx-text-button" onClick={() => window.location.hash = "#/runs"}>All runs <Icon name="arrow-right" size={14}/></button></div>
      {reports.length ? <RunTable reports={reports.slice(0, 6)} onOpen={onOpenRun}/> : <EmptyState title="No run reports yet" detail={connected ? "Run the offline demo to verify the engine bridge, or create an LLM-backed task." : "Connect the local Python engine to load persisted run reports."}/>}
    </section>
    <section className="kx-panel kx-demo-panel"><div><span className="kx-eyebrow">CREDENTIAL-FREE</span><h2>Try the offline engine demo</h2><p>Runs the actual Python demo executor, independent evaluator and SQLite memory path. This does not modify a repository.</p></div><button className="kx-button kx-button--primary" disabled={!connected || busy} onClick={onDemo}>{busy ? "Running demo…" : <><Icon name="arrow-right" size={15}/> Run offline demo</>}</button></section>
  </>;
}
function TaskBuilder({ settings, connected, apiKey, onRun, busy, error }: {
  settings: Settings; connected: boolean; apiKey: string; onRun: (request: Omit<TaskRunRequest, "enginePath" | "pythonExecutable">) => void;
  busy: boolean; error: string;
}) {
  const [objective, setObjective] = useState("");
  const [criteria, setCriteria] = useState([""]);
  const [maxIterations, setMaxIterations] = useState(3);
  const [agentId, setAgentId] = useState("");
  const [memoryLimit, setMemoryLimit] = useState(5);
  const cleaned = criteria.map(item => item.trim()).filter(Boolean);
  const criteriaUnique = new Set(cleaned.map(item => item.toLocaleLowerCase())).size === cleaned.length;
  const ready = connected && apiKey.trim() && settings.executorModel.trim() && settings.evaluatorModel.trim() && settings.executorModel.trim().toLocaleLowerCase() !== settings.evaluatorModel.trim().toLocaleLowerCase() && objective.trim() && cleaned.length > 0 && criteriaUnique && settings.projectId.trim() && maxIterations >= 1 && maxIterations <= 20;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onRun({
      objective,
      acceptanceCriteria: cleaned,
      maxIterations,
      projectId: settings.projectId,
      agentId: agentId.trim() || undefined,
      memoryLimit,
      apiKey,
      executorModel: settings.executorModel,
      evaluatorModel: settings.evaluatorModel,
      baseUrl: settings.baseUrl || undefined,
    });
  };
  return <>
    <PageHeader title="New engineering task" subtitle="Create a bounded task contract. The evaluator checks the original acceptance criteria independently."/>
    <form className="kx-task-form" onSubmit={submit}>
      <section className="kx-panel"><div className="kx-panel__head"><div><h2>Task objective</h2><p>Describe the deliverable the executor should produce.</p></div><span className="kx-step-index">01</span></div><label className="kx-field">Objective<textarea value={objective} onChange={event => setObjective(event.target.value)} rows={3} minLength={8} required placeholder="Describe the engineering outcome, constraints and expected deliverable…"/></label></section>
      <section className="kx-panel"><div className="kx-panel__head"><div><h2>Acceptance criteria</h2><p>Each criterion is evaluated separately. Keep criteria explicit and verifiable.</p></div><span className="kx-step-index">02</span></div><div className="kx-criteria-list">{criteria.map((criterion, index) => <div className="kx-criterion-row" key={index}><span className="kx-criterion-number">{String(index + 1).padStart(2, "0")}</span><input aria-label={`Acceptance criterion ${index + 1}`} value={criterion} onChange={event => setCriteria(items => items.map((item, itemIndex) => itemIndex === index ? event.target.value : item))} placeholder="e.g. Unit tests pass for the new behavior" required/><button type="button" className="kx-icon-button" aria-label="Remove criterion" disabled={criteria.length === 1} onClick={() => setCriteria(items => items.filter((_, itemIndex) => itemIndex !== index))}><Icon name="x" size={15}/></button></div>)}</div><button type="button" className="kx-add-criterion" onClick={() => setCriteria(items => [...items, ""])}><Icon name="plus" size={14}/> Add criterion</button></section>
      <section className="kx-panel"><div className="kx-panel__head"><div><h2>Execution limits</h2><p>Limits are enforced by the Python engine before and during execution.</p></div><span className="kx-step-index">03</span></div><div className="kx-form-grid"><label className="kx-field">Maximum iterations<input type="number" min={1} max={20} value={maxIterations} onChange={event => setMaxIterations(Number(event.target.value))}/><small>Allowed by the desktop bridge: 1–20</small></label><label className="kx-field">Project memory scope<input value={settings.projectId} readOnly/><small>Change the project ID in Settings.</small></label><label className="kx-field">Agent namespace (optional)<input value={agentId} onChange={event => setAgentId(event.target.value)} placeholder="primary"/></label><label className="kx-field">Retrieved memories<input type="number" min={1} max={20} value={memoryLimit} onChange={event => setMemoryLimit(Number(event.target.value))}/><small>Maximum approved memories supplied to the executor.</small></label></div></section>
      {!connected && <div className="kx-alert" role="status">Connect the Python engine in Settings before starting a run.</div>}
      {connected && (!apiKey || !settings.executorModel || !settings.evaluatorModel) && <div className="kx-alert" role="status">Configure an API key and two different model identifiers in Settings. The API key is kept in memory for this app session only.</div>}
      {!criteriaUnique && <div className="kx-alert" role="status">Acceptance criteria must be unique.</div>}
      {error && <div className="kx-alert kx-alert--error" role="alert">{error}</div>}
      <div className="kx-form-submit"><span>Task data and credentials are sent to your local Python engine. Provider requests may send task content to the configured model provider.</span><button className="kx-button kx-button--primary" type="submit" disabled={!ready || busy}>{busy ? "Starting run…" : <><Icon name="arrow-right" size={15}/> Run task</>}</button></div>
    </form>
  </>;
}
function RunsPage({ reports, onOpen }: { reports: RunReport[]; onOpen: (id: string) => void }) {
  const [filter, setFilter] = useState("all");
  const visible = filter === "all" ? reports : reports.filter(report => report.status === filter);
  return <><PageHeader title="Runs" subtitle="Persisted execution reports from the local KALDRAX engine."/><section className="kx-panel"><div className="kx-panel__head"><div><h2>Run history</h2><p>{reports.length} report{reports.length === 1 ? "" : "s"} available</p></div><select className="kx-filter" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All statuses</option><option value="passed">Passed</option><option value="failed">Failed</option><option value="limit_reached">Iteration limit</option></select></div>{visible.length ? <RunTable reports={visible} onOpen={onOpen}/> : <EmptyState title="No runs match this filter" detail="Try another status or start a new run from Tasks."/>}</section></>;
}
function RunDetailPage({ enginePath }: { enginePath: string }) {
  const { runId = "" } = useParams();
  const [loaded, setLoaded] = useState<{ id: string; report?: RunReport; error?: string } | null>(null);
  useEffect(() => {
    let active = true;
    getRunReport(enginePath, runId).then(report => {
      if (active) setLoaded({ id: runId, report });
    }).catch(reason => {
      if (active) setLoaded({ id: runId, error: reason instanceof Error ? reason.message : String(reason) });
    });
    return () => { active = false; };
  }, [enginePath, runId]);
  const current = loaded?.id === runId ? loaded : null;
  if (current?.error) return <><PageHeader title="Run report unavailable" subtitle="The selected report could not be loaded."/><div className="kx-alert kx-alert--error">{current.error}</div></>;
  const report = current?.report;
  if (!report) return <div className="kx-loading">Loading run report…</div>;
  return <>
    <PageHeader title="Run details" subtitle={report.objective} action={<StatusBadge status={report.status}/>}/>
    <div className="kx-run-summary"><div><small>RUN ID</small><strong className="mono">{report.run_id}</strong></div><div><small>ITERATIONS</small><strong>{report.iterations}</strong></div><div><small>CREATED</small><strong>{formatDate(report.created_at)}</strong></div><div><small>DURATION</small><strong>{duration(report)}</strong></div></div>
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Execution timeline</h2><p>Ordered events emitted by the engine</p></div><Badge>{report.events.length} events</Badge></div><div className="kx-event-list">{report.events.map(event => <article className="kx-event" key={event.sequence}><span className={`kx-event-marker ${event.event_type.includes("passed") || event.event_type.includes("completed") ? "success" : event.event_type.includes("failed") || event.event_type.includes("error") ? "danger" : ""}`}/><div className="kx-event-main"><div><strong>{event.event_type.replaceAll("_", " ")}</strong><time>{formatDate(event.timestamp)}</time></div><p>{event.message}</p></div><span className="kx-event-sequence">{String(event.sequence).padStart(2, "0")}</span></article>)}</div></section>
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Independent evaluations</h2><p>Each iteration is checked against the original acceptance criteria.</p></div></div>{report.evaluations.map((evaluation, index) => <article className="kx-evaluation-card" key={index}><div className="kx-evaluation-head"><strong>Iteration {index + 1}</strong><Badge tone={evaluation.passed ? "passed" : "failed"}>{evaluation.passed ? "Passed" : "Failed"}</Badge><span className="kx-muted">{evaluation.evaluator}</span></div><div className="kx-criteria-results">{evaluation.satisfied.map(item => <div className="kx-criteria-result is-satisfied" key={item}><Icon name="check-circle" size={15}/><span>{item}</span></div>)}{evaluation.missing.map(item => <div className="kx-criteria-result is-missing" key={item}><Icon name="x" size={15}/><span>{item}</span></div>)}</div>{evaluation.evidence.length > 0 && <div className="kx-evidence-list">{evaluation.evidence.map((evidence, evidenceIndex) => <blockquote key={evidenceIndex}><span>{evidence.criterion}</span><p>“{evidence.quote}”</p></blockquote>)}</div>}</article>)}</section>
    {report.budget && <section className="kx-panel"><div className="kx-panel__head"><div><h2>Provider usage</h2><p>Reported usage for this run. Cost is an estimate when rates are configured.</p></div></div><div className="kx-usage-grid"><div><small>Provider calls</small><strong>{report.budget.calls ?? 0}{report.budget.max_calls ? ` / ${report.budget.max_calls}` : ""}</strong></div><div><small>Input tokens</small><strong>{(report.budget.input_tokens ?? 0).toLocaleString()}</strong></div><div><small>Output tokens</small><strong>{(report.budget.output_tokens ?? 0).toLocaleString()}</strong></div><div><small>Total tokens</small><strong>{(report.budget.total_tokens ?? 0).toLocaleString()}</strong></div><div><small>Estimated cost</small><strong>{report.budget.estimated_cost_usd != null ? `$${report.budget.estimated_cost_usd.toFixed(4)}` : "Not configured"}</strong></div><div><small>Elapsed</small><strong>{report.budget.elapsed_seconds != null ? `${report.budget.elapsed_seconds}s` : "—"}</strong></div></div></section>}
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Final candidate</h2><p>Text artifact returned by the executor; not proof of repository changes.</p></div></div><pre className="kx-output">{report.final_output || "No candidate output was recorded."}</pre></section>
  </>;
}
function SettingsPage({ settings, onChange, apiKey, setApiKey, engineStatus, onVerify, busy, error }: {
  settings: Settings; onChange: (settings: Settings) => void; apiKey: string; setApiKey: (value: string) => void;
  engineStatus: EngineStatus | null; onVerify: () => void; busy: boolean; error: string;
}) {
  const [selecting, setSelecting] = useState(false);
  const selectFolder = async (target: "enginePath" | "repositoryPath") => {
    setSelecting(true);
    try {
      const selected = await open({ directory: true, multiple: false, title: target === "enginePath" ? "Select KALDRAX Python source" : "Select Git repository" });
      if (typeof selected === "string") onChange({ ...settings, [target]: selected });
    } finally { setSelecting(false); }
  };
  const update = (key: keyof Settings, value: string) => onChange({ ...settings, [key]: value });
  return <>
    <PageHeader title="Settings" subtitle="Connect the local Python control plane and optionally configure model providers."/>
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Local engine</h2><p>Choose the Python source checkout and interpreter used by the desktop bridge.</p></div><Badge tone={engineStatus ? "passed" : "failed"}>{engineStatus ? `v${engineStatus.engineVersion} connected` : "Not connected"}</Badge></div><label className="kx-field">Engine source folder<div className="kx-path-picker"><input value={settings.enginePath} onChange={event => update("enginePath", event.target.value)} placeholder="Choose the KALDRAX Python project folder"/><button type="button" className="kx-button kx-button--quiet" onClick={() => selectFolder("enginePath")} disabled={selecting}>{selecting ? "Opening…" : "Browse"}</button></div><small>Folder must contain pyproject.toml and src/kaldrax/cli.py.</small></label><label className="kx-field">Python executable<input value={settings.pythonExecutable} onChange={event => update("pythonExecutable", event.target.value)} placeholder="python"/></label><div className="kx-settings-actions"><button className="kx-button kx-button--primary" type="button" onClick={onVerify} disabled={busy || !settings.enginePath.trim()}>{busy ? "Checking…" : "Verify engine connection"}</button>{engineStatus && <span className="kx-muted">{engineStatus.enginePath}</span>}</div></section>
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Project memory scope</h2><p>Project ID isolates persistent memory. It is not a repository path.</p></div></div><label className="kx-field">Project ID<input value={settings.projectId} onChange={event => update("projectId", event.target.value)} placeholder="kaldrax-core"/></label></section>
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>LLM provider</h2><p>Only needed for live model-backed runs; offline and local workflows do not need provider credentials.</p></div></div><label className="kx-field">Model provider API key<input type="password" autoComplete="off" value={apiKey} onChange={event => setApiKey(event.target.value)} placeholder="Enter API key for this session"/><small>Use a key issued by your configured model provider, not a KALDRAX account key. It is kept in application memory only and is required only when making live model calls.</small></label><div className="kx-form-grid"><label className="kx-field">Executor / builder model<input value={settings.executorModel} onChange={event => update("executorModel", event.target.value)} placeholder="builder-model"/></label><label className="kx-field">Evaluator model<input value={settings.evaluatorModel} onChange={event => update("evaluatorModel", event.target.value)} placeholder="different-evaluator-model"/></label><label className="kx-field">Team planner model<input value={settings.plannerModel} onChange={event => update("plannerModel", event.target.value)} placeholder="planner-model"/></label><label className="kx-field">Team reviewer model<input value={settings.reviewerModel} onChange={event => update("reviewerModel", event.target.value)} placeholder="reviewer-model"/></label></div><label className="kx-field">OpenAI-compatible base URL (optional)<input value={settings.baseUrl} onChange={event => update("baseUrl", event.target.value)} placeholder="https://api.openai.com/v1"/><small>Leave blank to use the engine default.</small></label></section>
    <section className="kx-panel"><div className="kx-panel__head"><div><h2>Repository workspace</h2><p>Select a separate Git worktree for inspection and explicit file edits.</p></div></div><label className="kx-field">Repository folder<div className="kx-path-picker"><input value={settings.repositoryPath} onChange={event => update("repositoryPath", event.target.value)} placeholder="Choose a Git repository"/><button type="button" className="kx-button kx-button--quiet" onClick={() => selectFolder("repositoryPath")} disabled={selecting}>Browse</button></div><small>Repository operations are restricted to Git worktrees.</small></label></section>
    {error && <div className="kx-alert kx-alert--error" role="alert">{error}</div>}
    <p className="kx-settings-note">Non-secret settings are stored locally on this device. Provider keys are session-only in this desktop build. LLM-backed tasks send prompts and candidates to the configured provider. The offline demo does not require a provider.</p>
  </>;
}
function KaldraxShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const [navExpanded, setNavExpanded] = useState(false);
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [apiKey, setApiKey] = useState("");
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [reports, setReports] = useState<RunReport[]>([]);
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("");
  const [error, setError] = useState("");
  const [operation, setOperation] = useState<OperationSnapshot | null>(null);

  useEffect(() => { localStorage.setItem(settingsKey, JSON.stringify(settings)); }, [settings]);
  const refreshRuns = useCallback(async () => {
    if (!engineStatus) { setReports([]); return; }
    try { setReports(await listRuns(engineStatus.enginePath)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }, [engineStatus]);
  useEffect(() => {
    let active = true;
    if (!settings.enginePath.trim() || !settings.pythonExecutable.trim()) return;
    verifyEngine(settings.enginePath, settings.pythonExecutable).then(async status => {
      if (!active) return;
      setEngineStatus(status);
      setError("");
      try {
        const savedReports = await listRuns(status.enginePath);
        if (active) setReports(savedReports);
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : String(reason));
      }
    }).catch(reason => {
      if (!active) return;
      setEngineStatus(null);
      setReports([]);
      setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { active = false; };
  }, [settings.enginePath, settings.pythonExecutable]);

  const page = navigation.find(item => item.path === location.pathname);
  const title = page?.label ?? (location.pathname.startsWith("/runs/") ? "Run details" : "Overview");
  const verify = async () => {
    setBusy(true); setBusyLabel("verify"); setError("");
    try {
      const status = await verifyEngine(settings.enginePath, settings.pythonExecutable);
      setEngineStatus(status);
      setError("");
    } catch (reason) {
      setEngineStatus(null);
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally { setBusy(false); setBusyLabel(""); }
  };
  const launchDemo = async () => {
    if (!engineStatus) { setError("Connect the Python engine first."); return; }
    setBusy(true); setBusyLabel("demo"); setError("");
    try {
      const snapshot = await startOfflineDemo(engineStatus.enginePath, settings.pythonExecutable, settings.projectId);
      setOperation(snapshot);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); setBusyLabel(""); }
  };
  const launchTask = async (request: Omit<TaskRunRequest, "enginePath" | "pythonExecutable">) => {
    if (!engineStatus) { setError("Connect the Python engine in Settings."); return; }
    setBusy(true); setBusyLabel("task"); setError("");
    try {
      const snapshot = await startTaskRun({ ...request, enginePath: engineStatus.enginePath, pythonExecutable: settings.pythonExecutable });
      setOperation(snapshot);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); setBusyLabel(""); }
  };
  const cancelCurrentOperation = async () => {
    if (!operation) return;
    try { setOperation(await cancelOperation(operation.operationId)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  };
  const activeOperationId = operation?.operationId;
  const activeOperationStatus = operation?.status;
  useEffect(() => {
    if (!activeOperationId || !["running", "cancelling"].includes(activeOperationStatus ?? "")) return;
    let disposed = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const latest = await getOperation(activeOperationId);
        if (disposed) return;
        setOperation(latest);
        if (["completed", "failed", "cancelled"].includes(latest.status)) {
          if (latest.status === "completed") {
            await refreshRuns();
            const result = latest.result && typeof latest.result === "object" ? latest.result as Record<string, unknown> : {};
            if ((latest.kind === "offline_demo" || latest.kind === "task_run") && typeof result.run_id === "string") {
              navigate("/runs/" + result.run_id);
            }
          } else if (latest.error) {
            setError(latest.error);
          }
          return;
        }
      } catch (reason) {
        if (!disposed) setError(reason instanceof Error ? reason.message : String(reason));
      }
      if (!disposed) timer = window.setTimeout(poll, 250);
    };
    timer = window.setTimeout(poll, 180);
    return () => { disposed = true; if (timer) window.clearTimeout(timer); };
  }, [activeOperationId, activeOperationStatus, refreshRuns, navigate]);
  const operationRunning = operation?.status === "running" || operation?.status === "cancelling";
  const navigateToRun = (id: string) => navigate("/runs/" + id);
  const connected = Boolean(engineStatus);

  return <div className={`kx-app ${navExpanded ? "kx-app--nav-expanded" : ""}`}>
    <aside className="kx-rail" aria-label="Primary navigation">
      <NavLink to="/" className="kx-brand" aria-label="KALDRAX home"><span>K</span></NavLink>
      <NavLink to="/tasks" className="kx-rail-add" aria-label="Create task" title="Create task"><Icon name="plus" size={21}/><span className="kx-rail-label">New task</span></NavLink>
      <nav className="kx-rail-links">
        {["WORKSPACE", "EXECUTION", "INTELLIGENCE", "SYSTEM"].map(group => <div className="kx-rail-group" key={group}>
          {navExpanded && <span className="kx-rail-group-label">{group}</span>}
          {navigation.filter(item => item.group === group).map(item => <NavLink key={item.path} to={item.path} end={item.path === "/"} title={navExpanded ? "" : item.label} aria-label={item.label} className={({ isActive }) => `kx-rail-link ${isActive ? "active" : ""}`}><Icon name={item.icon} size={21}/><span className="kx-rail-label">{item.label}</span></NavLink>)}
        </div>)}
      </nav>
      <div className="kx-rail-spacer"/>
      <div className="kx-rail-footer"><span className="kx-rail-engine"><i/><span className="kx-rail-label">{connected ? `Engine v${engineStatus?.engineVersion}` : "Engine offline"}</span></span><span className="kx-avatar">KX</span></div>
      <button className="kx-rail-toggle" type="button" aria-label={navExpanded ? "Collapse sidebar" : "Expand sidebar"} aria-expanded={navExpanded} onClick={() => setNavExpanded(value => !value)}><Icon name={navExpanded ? "chevrons-left" : "chevrons-right"} size={17}/></button>
    </aside>
    <main className="kx-main">
      <header className="kx-topbar"><div className="kx-breadcrumb"><span>KALDRAX</span><Icon name="chevron-right" size={13}/><strong>{title}</strong></div><div className="kx-topbar__actions"><span className={`kx-engine-pill ${connected ? "online" : ""}`}><i/>{connected ? `Engine v${engineStatus?.engineVersion}` : "Engine offline"}</span><button className="kx-icon-button" aria-label="Notifications"><Icon name="bell" size={19}/></button><span className="kx-avatar kx-avatar--top">KX</span></div></header>
      <div className="kx-content">
        {operation && <OperationPanel operation={operation} onCancel={cancelCurrentOperation}/>}
        <Routes>
          <Route path="/" element={<OverviewPage reports={reports} connected={connected} busy={busy || operationRunning} onDemo={launchDemo} onNewTask={() => navigate("/tasks")} onOpenRun={navigateToRun} error={error}/>} />
          <Route path="/tasks" element={<TaskBuilder settings={settings} connected={connected} apiKey={apiKey} onRun={launchTask} busy={busy && busyLabel === "task" || operationRunning && operation?.kind === "task_run"} error={busyLabel === "task" ? error : ""}/>} />
          <Route path="/runs" element={<RunsPage reports={reports} onOpen={navigateToRun}/>} />
          <Route path="/runs/:runId" element={<RunDetailPage enginePath={settings.enginePath}/>} />
          <Route path="/settings" element={<SettingsPage settings={settings} onChange={setSettings} apiKey={apiKey} setApiKey={setApiKey} engineStatus={engineStatus} onVerify={verify} busy={busy && busyLabel === "verify"} error={error}/>} />
          <Route path="/team" element={<TeamRunsPage settings={settings} apiKey={apiKey} operation={operation} onOperationStarted={setOperation}/>} />
          <Route path="/sandbox" element={<SandboxPage settings={settings} operation={operation} onOperationStarted={setOperation}/>} />
          <Route path="/memory" element={<MemoryPage settings={settings}/>} />
          <Route path="/repository" element={<RepositoryPage settings={settings} onSettingsChange={setSettings}/>} />
          <Route path="*" element={<PageHeader title="Not found" subtitle="This route does not exist. Use the navigation rail to continue."/>}/>
        </Routes>
        <footer className="kx-footer"><span>KALDRAX Desktop</span><span>{connected ? `Python ${engineStatus?.engineVersion} · Tauri desktop` : "Local desktop · engine not connected"}</span><span>Reports and SQLite memory stay under the local engine folder</span></footer>
      </div>
    </main>
  </div>;
}
export default function Kaldrax() { return <KaldraxShell/>; }
