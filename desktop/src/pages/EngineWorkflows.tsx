import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { Icon } from "../components/Icons";
import {
  benchmarkReviewState,
  benchmarkReviewUpdate,
  qualityReviewState,
  qualityReviewUpdate,
  listTeamRuns,
  memoryConflicts,
  type BenchmarkReviewState,
  type QualityReviewState,
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

function BenchmarkReviewPanel({
  settings,
  reviewer,
}: {
  settings: WorkflowSettings;
  reviewer: string;
}) {
  const [review, setReview] = useState<BenchmarkReviewState | null>(null);
  const [activeQueryId, setActiveQueryId] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!reviewer.trim()) {
      setError("Enter a reviewer identity before opening the benchmark review.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await benchmarkReviewState({
        enginePath: settings.enginePath,
        pythonExecutable: settings.pythonExecutable,
        reviewer,
      });
      setReview(result);
      setActiveQueryId(current => result.queries.some(query => query.id === current)
        ? current : result.queries[0]?.id ?? "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }, [settings.enginePath, settings.pythonExecutable, reviewer]);

  useEffect(() => { void refresh(); }, [refresh]);

  const activeQuery = review?.queries.find(query => query.id === activeQueryId) ?? null;
  useEffect(() => {
    if (!activeQuery) return;
    setSelectedIds(activeQuery.relevant);
    setNote(activeQuery.review_note ?? "");
  }, [activeQuery?.id, activeQuery?.status]);

  const update = async (input: {
    action: "query" | "dataset-approval" | "privacy-approval" | "auto-approve-proposals" | "model-review";
    queryId?: string;
    decision?: "approve" | "reject" | "modify";
    memoryIds?: string[];
    note?: string;
    approval?: "approve" | "reject";
    privacyConfirmation?: string;
    confirmProviderDataEgress?: boolean;
    successMessage: string;
  }) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await benchmarkReviewUpdate({
        enginePath: settings.enginePath,
        pythonExecutable: settings.pythonExecutable,
        reviewer,
        action: input.action,
        queryId: input.queryId,
        decision: input.decision,
        memoryIds: input.memoryIds,
        note: input.note,
        approval: input.approval,
        privacyConfirmation: input.privacyConfirmation,
        confirmProviderDataEgress: input.confirmProviderDataEgress,
      });
      setReview(result);
      setNotice(result.export_path
        ? "Validated, immutable benchmark export created: " + result.export_path
        : input.successMessage);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const reviewedCount = review?.queries.filter(query =>
    query.status === "approved" || query.status === "modified"
  ).length ?? 0;
  const autoApprovedCount = review?.queries.filter(query => query.status === "auto_approved").length ?? 0;
  const pendingCount = review?.queries.filter(query => query.status === "pending").length ?? 0;
  const aiReviewedCount = review?.ai_reviewed_count ?? 0;
  const aiAbstainedCount = review?.ai_abstained_count ?? 0;
  const modelReviewPendingCount = pendingCount + autoApprovedCount;
  const allQueries = Boolean(review?.review_ready);

  const runModelReview = () => {
    if (!review || (modelReviewPendingCount === 0 && review.ai_privacy_screening)) return;
    const confirmed = window.confirm(
      "KALDRAX will send copied memory content, summaries, categories, the declared privacy scope, and pending retrieval queries to the configured model endpoint. Source paths are not sent. The provider may process or retain this data under its own terms. Do not continue unless this transfer is permitted. Model decisions are exploratory only; this does not approve the dataset or privacy scope."
    );
    if (!confirmed) return;
    void update({
      action: "model-review",
      confirmProviderDataEgress: true,
      successMessage: "AI review completed. Model decisions and privacy findings are recorded as exploratory; human approval gates remain separate.",
    });
  };

  const autoApproveProposals = () => {
    if (pendingCount === 0) return;
    const confirmed = window.confirm(
      `Auto-accept all ${pendingCount} pending source proposals as machine-reviewed? This does not count as human review, approve the dataset, approve privacy, or enable a validated export.`
    );
    if (!confirmed) return;
    void update({
      action: "auto-approve-proposals",
      successMessage: `KALDRAX machine-accepted ${pendingCount} unchanged proposals. Human review and both approval gates remain separate.`,
    });
  };
  const privacyApproved = review?.privacy_screening.status === "approved";
  const datasetApproved = review?.dataset_approval.status === "approved";

  const approvePrivacy = () => {
    const confirmation = window.prompt(
      "Review the declared scope and every source-backed memory below. Type APPROVE to attest that you inspected the displayed source paths and copied content."
    );
    if (confirmation !== "APPROVE") return;
    void update({
      action: "privacy-approval",
      approval: "approve",
      privacyConfirmation: confirmation,
      successMessage: "Privacy review approved and recorded.",
    });
  };

  if (!review && busy) {
    return <section className="kx-panel"><div className="kx-loading">Loading source-backed benchmark review…</div></section>;
  }

  return <>
    {error && <Alert error>{error}</Alert>}
    {notice && <Alert>{notice}</Alert>}
    {review && <>
      <section className="kx-panel">
        <div className="kx-panel__head">
          <div>
            <h2>{review.dataset_name}</h2>
            <p>{review.queries.length} proposed retrieval queries · {review.memories.length} source-backed memories · source revision {review.source_revision ?? "unspecified"}</p>
          </div>
          <Badge tone={review.benchmark_status === "validated_exported" ? "passed" : "warning"}>
            {review.benchmark_status === "validated_exported"
              ? "Validated export"
              : review.benchmark_status === "ai_reviewed_exploratory"
                ? "AI-reviewed · exploratory only"
                : autoApprovedCount > 0 ? "Machine-reviewed · human sign-off pending" : "Human review pending"}
          </Badge>
        </div>
        <div className="kx-run-summary">
          <div><small>HUMAN-REVIEWED LABELS</small><strong>{reviewedCount} / {review.queries.length}</strong></div>
          <div><small>MACHINE-ACCEPTED</small><strong>{autoApprovedCount}</strong></div>
          <div><small>AI-REVIEWED</small><strong>{aiReviewedCount}</strong></div>
          <div><small>AI ABSTENTIONS</small><strong>{aiAbstainedCount}</strong></div>
          <div><small>DATASET APPROVAL</small><strong>{review.dataset_approval.status}</strong></div>
          <div><small>PRIVACY APPROVAL</small><strong>{review.privacy_screening.status}</strong></div>
          <div><small>REVIEW SESSION</small><strong>Resumable</strong></div>
        </div>
        <p className="kx-muted">Session: <code>{review.session_path}</code></p>
        <p className="kx-muted">Source SHA-256: <code>{review.source_sha256}</code></p>
        <div className="kx-settings-actions">
          <button className="kx-button kx-button--primary" onClick={runModelReview}
            disabled={busy || (modelReviewPendingCount === 0 && Boolean(review.ai_privacy_screening))}>
            Review with configured AI model
          </button>
          <button className="kx-button kx-button--quiet" onClick={() => void refresh()} disabled={busy}>
            <Icon name="refresh" size={14}/> Refresh review state
          </button>
        </div>
        {review.ai_export_path && <p className="kx-muted">AI-reviewed exploratory export: <code>{review.ai_export_path}</code></p>}
      </section>

      <section className="kx-panel">
        <div className="kx-panel__head">
          <div><h2>Review relevance labels</h2><p>Inspect each query, accept the proposed memory IDs, correct the set, or reject it. Changes reset dataset-level approval.</p></div>
          <Badge tone={allQueries ? "passed" : "neutral"}>{reviewedCount} human-reviewed</Badge>
        </div>
        {autoApprovedCount > 0 && <Alert>
          {autoApprovedCount} proposals were accepted automatically by KALDRAX. They remain machine-reviewed, not human-reviewed; confirm each proposal individually before dataset approval or export.
        </Alert>}
        {(aiReviewedCount > 0 || aiAbstainedCount > 0) && <Alert>
          The configured model has reviewed {aiReviewedCount} queries and abstained on {aiAbstainedCount}. These are AI judgments, not human ground truth. Review every rationale and evidence span before using the exploratory export.
        </Alert>}
        <div className="kx-settings-actions">
          <button
            className="kx-button kx-button--quiet"
            disabled={busy || pendingCount === 0}
            onClick={autoApproveProposals}
          >
            Auto-accept {pendingCount} pending proposals (machine-only)
          </button>
        </div>
        <div className="kw-tabs" role="tablist" aria-label="Benchmark query review">
          {review.queries.map(query => <button
            key={query.id}
            type="button"
            role="tab"
            aria-selected={query.id === activeQueryId}
            className={query.id === activeQueryId ? "active" : ""}
            onClick={() => setActiveQueryId(query.id)}
          >
            {query.id} · {query.status}
          </button>)}
        </div>
        {activeQuery && <>
          <div className="kw-memory-card">
            <div className="kw-memory-card__head">
              <div><span className="kw-memory-type">{activeQuery.category} · {activeQuery.id}</span><h3>{activeQuery.query}</h3></div>
              <Badge tone={activeQuery.status === "approved" || activeQuery.status === "modified" ? "passed" : "warning"}>
                {activeQuery.status === "auto_approved" ? "Machine accepted"
                  : activeQuery.status === "ai_reviewed" ? "AI reviewed"
                  : activeQuery.status === "ai_abstained" ? "AI abstained"
                  : activeQuery.status}
              </Badge>
            </div>
            {activeQuery.rationale && <p>{activeQuery.rationale}</p>}
            <p className="kx-muted">Proposed IDs: {activeQuery.proposed_relevant.join(", ")}</p>
            {activeQuery.review_note && <p>Previous review note: {activeQuery.review_note}</p>}
            {activeQuery.ai_review && <div className="kw-memory-meta">
              <span>Model: {activeQuery.ai_review.model}</span>
              <span>Decision: {activeQuery.ai_review.decision} · confidence {Math.round(activeQuery.ai_review.confidence * 100)}%</span>
              <span>{activeQuery.ai_review.rationale}</span>
              {activeQuery.ai_review.evidence.map(evidence => {
                const memory = review.memories.find(item => item.id === evidence.memory_id);
                return <span key={evidence.memory_id}>
                  Evidence {evidence.memory_id}: {memory?.content.slice(evidence.start, evidence.end) ?? "source span unavailable"}
                </span>;
              })}
            </div>}
          </div>
          <div className="kw-memory-list">
            {review.memories.map(memory => <label className="kw-memory-card" key={memory.id}>
              <div className="kw-memory-card__head">
                <div>
                  <span className="kw-memory-type">{memory.category} · {memory.id}</span>
                  <h3>{memory.summary || memory.content.slice(0, 120)}</h3>
                </div>
                <input
                  type="checkbox"
                  aria-label={"Mark " + memory.id + " relevant to " + activeQuery.id}
                  checked={selectedIds.includes(memory.id)}
                  onChange={event => setSelectedIds(current =>
                    event.target.checked
                      ? [...current, memory.id]
                      : current.filter(id => id !== memory.id)
                  )}
                />
              </div>
              <p>{memory.content}</p>
              <div className="kw-memory-meta">
                <span>Source: {memory.source.path ?? "unspecified"}{memory.source.anchor ? " · " + memory.source.anchor : ""}</span>
                <span>{memory.tags.join(", ")}</span>
              </div>
            </label>)}
          </div>
          <label className="kx-field">Review note (optional)
            <textarea rows={2} value={note} onChange={event => setNote(event.target.value)} placeholder="Explain why you changed or rejected the proposed relevance labels."/>
          </label>
          {selectedIds.length === 0 && <Alert>A validated relevance judgment must contain at least one memory ID. Use Reject to mark an invalid query proposal; it will block dataset approval until corrected.</Alert>}
          <div className="kx-settings-actions">
            <button className="kx-button kx-button--quiet" disabled={busy} onClick={() => void update({
              action: "query", queryId: activeQuery.id, decision: "reject", note,
              successMessage: "Query " + activeQuery.id + " rejected. Dataset approval remains blocked until it is corrected.",
            })}>Reject proposal</button>
            <button className="kx-button kx-button--quiet" disabled={busy || selectedIds.length === 0} onClick={() => void update({
              action: "query", queryId: activeQuery.id, decision: "modify",
              memoryIds: selectedIds, note,
              successMessage: "Corrected relevance IDs recorded for " + activeQuery.id + ".",
            })}>Save corrected IDs</button>
            <button className="kx-button kx-button--primary" disabled={busy} onClick={() => void update({
              action: "query", queryId: activeQuery.id, decision: "approve",
              successMessage: "Proposed relevance IDs approved for " + activeQuery.id + ".",
            })}>Approve proposed IDs</button>
          </div>
        </>}
      </section>

      <section className="kx-panel">
        <div className="kx-panel__head"><div><h2>Dataset annotation approval</h2><p>This is separate from the individual query decisions and from privacy approval.</p></div><Badge tone={datasetApproved ? "passed" : "warning"}>{review.dataset_approval.status}</Badge></div>
        {!allQueries && <Alert>Every query must be approved or corrected before dataset annotation approval. Rejected or pending queries keep this gate closed.</Alert>}
        {review.dataset_approval.reviewer && <p className="kx-muted">Recorded by {review.dataset_approval.reviewer} at {review.dataset_approval.reviewed_at}</p>}
        <div className="kx-settings-actions">
          <button className="kx-button kx-button--primary" disabled={busy || !allQueries || datasetApproved} onClick={() => void update({
            action: "dataset-approval", approval: "approve",
            successMessage: "Dataset annotation approval recorded.",
          })}>Approve reviewed annotations</button>
          <button className="kx-button kx-button--quiet" disabled={busy || datasetApproved} onClick={() => void update({
            action: "dataset-approval", approval: "reject",
            successMessage: "Dataset annotation approval rejected.",
          })}>Reject dataset</button>
        </div>
      </section>

      <section className="kx-panel">
        <div className="kx-panel__head"><div><h2>Independent privacy screening</h2><p>Review all source paths and the copied content below before signing off. Label approval does not imply privacy approval.</p></div><Badge tone={privacyApproved ? "passed" : "warning"}>{review.privacy_screening.status}</Badge></div>
        <p><strong>Declared scope:</strong> {review.privacy_screening.scope || "No scope description provided."}</p>
        {review.privacy_screening.note && <p>{review.privacy_screening.note}</p>}
        {review.ai_privacy_screening && <div className="kw-memory-card">
          <div className="kw-memory-card__head">
            <div><span className="kw-memory-type">AI SCREENING · {review.ai_privacy_screening.model}</span>
              <h3>{review.ai_privacy_screening.status}</h3></div>
            <Badge tone={review.ai_privacy_screening.status === "ai_screened_clear" ? "warning" : "danger"}>Advisory only</Badge>
          </div>
          <p>{review.ai_privacy_screening.summary}</p>
          <p className="kx-muted">AI screening is not privacy approval. Human privacy status remains {review.privacy_screening.status}.</p>
          {review.ai_privacy_screening.findings.map((finding, index) => {
            const memory = review.memories.find(item => item.id === finding.memory_id);
            return <p key={index}>
              <strong>{finding.severity.toUpperCase()} · {finding.category} · {finding.memory_id}</strong>
              {" — "}{finding.rationale}
              {memory ? " Evidence: " + memory.content.slice(finding.start, finding.end) : ""}
            </p>;
          })}
        </div>}
        <details className="kw-conflict-card">
          <summary>Inspect all {review.memories.length} copied memory records and their source paths</summary>
          <div className="kw-memory-list">
            {review.memories.map(memory => <article className="kw-memory-card" key={memory.id}>
              <span className="kw-memory-type">{memory.category} · {memory.id}</span>
              <p>{memory.content}</p>
              <div className="kw-memory-meta"><span>{memory.source.path ?? "unspecified"}</span><span>{memory.source.anchor ?? ""}</span></div>
            </article>)}
          </div>
        </details>
        {review.privacy_screening.reviewer && <p className="kx-muted">Recorded by {review.privacy_screening.reviewer} at {review.privacy_screening.reviewed_at}</p>}
        <div className="kx-settings-actions">
          <button className="kx-button kx-button--primary" disabled={busy || privacyApproved} onClick={approvePrivacy}>Review scope and approve privacy</button>
          <button className="kx-button kx-button--quiet" disabled={busy || privacyApproved} onClick={() => void update({
            action: "privacy-approval", approval: "reject",
            successMessage: "Privacy screening rejected. No validated benchmark export can be produced.",
          })}>Reject privacy scope</button>
        </div>
      </section>

      {review.export_path && <section className="kx-panel">
        <div className="kx-panel__head"><div><h2>Immutable benchmark export</h2><p>Both approval gates passed. This file is content-addressed and write-once.</p></div><Badge tone="passed">Validated</Badge></div>
        <code>{review.export_path}</code>
      </section>}
    </>}
    {!review && !busy && <section className="kx-panel"><div className="kx-empty"><Icon name="database" size={24}/><strong>Benchmark review unavailable</strong><p>Check that the KALDRAX source checkout contains the benchmark dataset and that the local Python engine is connected.</p></div></section>}
  </>;
}


function QualityBenchmarkReviewPanel({
  settings,
  reviewer,
}: {
  settings: WorkflowSettings;
  reviewer: string;
}) {
  const [review, setReview] = useState<QualityReviewState | null>(null);
  const [kind, setKind] = useState<"contradiction" | "extraction">("contradiction");
  const [activeCaseId, setActiveCaseId] = useState("");
  const [draftClaims, setDraftClaims] = useState("[]");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const refresh = useCallback(async () => {
    if (!reviewer.trim()) {
      setError("Enter a reviewer identity before opening the quality benchmark review.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await qualityReviewState({
        enginePath: settings.enginePath,
        pythonExecutable: settings.pythonExecutable,
        reviewer,
      });
      setReview(result);
      const current = result[kind];
      setActiveCaseId(id => current.cases.some(item => item.id === id)
        ? id : current.cases[0]?.id ?? "");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }, [settings.enginePath, settings.pythonExecutable, reviewer, kind]);

  useEffect(() => { void refresh(); }, [refresh]);

  const dataset = review?.[kind] ?? null;
  const activeCase = dataset?.cases.find(item => item.id === activeCaseId) ?? null;
  useEffect(() => {
    if (!activeCase || kind !== "extraction") return;
    setDraftClaims(JSON.stringify(activeCase.expected ?? [], null, 2));
  }, [activeCase?.id, activeCase?.reviewed, kind]);

  const update = async (input: {
    action: "case" | "dataset-approval";
    kind: "contradiction" | "extraction";
    caseId?: string;
    decision?: "approve" | "modify";
    expectedConflict?: boolean;
    expectedClaims?: Array<{ match_terms: string[] }>;
    confirmation?: string;
    approval?: "approve" | "reject";
    successMessage: string;
  }) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await qualityReviewUpdate({
        enginePath: settings.enginePath,
        pythonExecutable: settings.pythonExecutable,
        reviewer,
        action: input.action,
        kind: input.kind,
        caseId: input.caseId,
        decision: input.decision,
        expectedConflict: input.expectedConflict,
        expectedClaims: input.expectedClaims,
        confirmation: input.confirmation,
        approval: input.approval,
      });
      setReview(result);
      const currentDataset = result[input.kind];
      setNotice(currentDataset.export_path
        ? "Immutable human-reviewed export created: " + currentDataset.export_path
        : input.successMessage);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  };

  const approveDataset = () => {
    if (!dataset?.review_ready) return;
    const required = "APPROVE " + kind.toUpperCase();
    const confirmation = window.prompt(
      "Review every " + kind + " label and type " + required + " to attest that the dataset has been inspected."
    );
    if (confirmation !== required) return;
    void update({
      action: "dataset-approval",
      kind,
      approval: "approve",
      confirmation,
      successMessage: kind + " dataset approval recorded.",
    });
  };

  if (!review && busy) {
    return <section className="kx-panel"><div className="kx-loading">Loading contradiction and extraction review…</div></section>;
  }

  return <>
    {error && <Alert error>{error}</Alert>}
    {notice && <Alert>{notice}</Alert>}
    {review && <>
      <section className="kx-panel">
        <div className="kx-panel__head">
          <div>
            <h2>Memory quality-label review</h2>
            <p>Review the synthetic contradiction and extraction evaluation labels. Proposed labels are not trusted until a human approves each dataset.</p>
          </div>
          <Badge tone={review.status === "validated_exported" ? "passed" : "warning"}>
            {review.status === "validated_exported" ? "Reviewed exports" : "Human review pending"}
          </Badge>
        </div>
        <p className="kx-muted">Session: <code>{review.session_path}</code></p>
        <div className="kx-form-grid">
          <div><small>CONTRADICTION SOURCE SHA-256</small><p><code>{review.source_hashes.contradiction}</code></p></div>
          <div><small>EXTRACTION SOURCE SHA-256</small><p><code>{review.source_hashes.extraction}</code></p></div>
        </div>
        <div className="kw-tabs" role="tablist" aria-label="Quality benchmark datasets">
          <button type="button" role="tab" aria-selected={kind === "contradiction"} className={kind === "contradiction" ? "active" : ""} onClick={() => { setKind("contradiction"); setActiveCaseId(""); }}>
            Contradictions · {review.contradiction.reviewed}/{review.contradiction.total}
          </button>
          <button type="button" role="tab" aria-selected={kind === "extraction"} className={kind === "extraction" ? "active" : ""} onClick={() => { setKind("extraction"); setActiveCaseId(""); }}>
            Extraction · {review.extraction.reviewed}/{review.extraction.total}
          </button>
        </div>
      </section>

      {dataset && <>
        <section className="kx-panel">
          <div className="kx-panel__head">
            <div>
              <h2>{dataset.name}</h2>
              <p>{dataset.total} cases · {dataset.reviewed} reviewed · version {dataset.version ?? "unspecified"}</p>
            </div>
            <Badge tone={dataset.approval.status === "approved" ? "passed" : "warning"}>{dataset.approval.status}</Badge>
          </div>
          <div className="kw-tabs" role="tablist" aria-label={kind + " cases"}>
            {dataset.cases.map(item => <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === activeCaseId}
              className={item.id === activeCaseId ? "active" : ""}
              onClick={() => setActiveCaseId(item.id)}
            >
              {item.id} · {item.reviewed ? item.review_status : "pending"}
            </button>)}
          </div>
          {activeCase && <>
            <div className="kw-memory-card">
              <div className="kw-memory-card__head">
                <div><span className="kw-memory-type">{activeCase.category} · {activeCase.id}</span><h3>{kind === "contradiction" ? "Does this pair express a real conflict?" : activeCase.objective}</h3></div>
                <Badge tone={activeCase.reviewed ? "passed" : "warning"}>{activeCase.review_status}</Badge>
              </div>
              {kind === "contradiction" ? <>
                <p><strong>LEFT</strong></p><p>{activeCase.left}</p>
                <p><strong>RIGHT</strong></p><p>{activeCase.right}</p>
                <p>Proposed label: <strong>{String(activeCase.proposed_expected_conflict)}</strong></p>
                <p>Current reviewed label: <strong>{String(activeCase.expected_conflict)}</strong></p>
                <div className="kx-settings-actions">
                  <button className="kx-button kx-button--quiet" disabled={busy} onClick={() => void update({
                    action: "case", kind, caseId: activeCase.id, decision: "approve",
                    successMessage: "Proposed conflict label accepted for " + activeCase.id + ".",
                  })}>Accept proposed label</button>
                  <button className="kx-button kx-button--quiet" disabled={busy} onClick={() => void update({
                    action: "case", kind, caseId: activeCase.id, decision: "modify",
                    expectedConflict: true,
                    successMessage: "Conflict label set to true for " + activeCase.id + ".",
                  })}>Mark as conflict</button>
                  <button className="kx-button kx-button--quiet" disabled={busy} onClick={() => void update({
                    action: "case", kind, caseId: activeCase.id, decision: "modify",
                    expectedConflict: false,
                    successMessage: "Conflict label set to false for " + activeCase.id + ".",
                  })}>Mark as unrelated</button>
                </div>
              </> : <>
                <p><strong>Candidate</strong></p><p>{activeCase.candidate}</p>
                <p><strong>Proposed expected claims</strong></p>
                <pre className="kx-output">{JSON.stringify(activeCase.proposed_expected, null, 2)}</pre>
                <label className="kx-field">Reviewed expected claims (JSON)
                  <textarea rows={9} value={draftClaims} onChange={event => setDraftClaims(event.target.value)} spellCheck={false}/>
                </label>
                <div className="kx-settings-actions">
                  <button className="kx-button kx-button--quiet" disabled={busy} onClick={() => void update({
                    action: "case", kind, caseId: activeCase.id, decision: "approve",
                    successMessage: "Proposed extraction claims accepted for " + activeCase.id + ".",
                  })}>Accept proposed claims</button>
                  <button className="kx-button kx-button--primary" disabled={busy} onClick={() => {
                    try {
                      const expectedClaims = JSON.parse(draftClaims) as Array<{ match_terms: string[] }>;
                      void update({
                        action: "case", kind, caseId: activeCase.id, decision: "modify",
                        expectedClaims,
                        successMessage: "Corrected extraction claims saved for " + activeCase.id + ".",
                      });
                    } catch {
                      setError("Expected claims must be valid JSON.");
                    }
                  }}>Save corrected claims</button>
                </div>
              </>}
              {activeCase.reviewed && <p className="kx-muted">Reviewed by {activeCase.reviewer ?? "unknown"} at {formatTime(activeCase.reviewed_at)}{activeCase.note ? " · " + activeCase.note : ""}</p>}
            </div>
          </>}
        </section>

        <section className="kx-panel">
          <div className="kx-panel__head">
            <div><h2>Separate dataset approval</h2><p>Every case must have a human-reviewed label before this dataset can be approved and exported.</p></div>
            <Badge tone={dataset.approval.status === "approved" ? "passed" : "warning"}>{dataset.approval.status}</Badge>
          </div>
          {dataset.approval.reviewer && <p className="kx-muted">Approved by {dataset.approval.reviewer} at {formatTime(dataset.approval.reviewed_at)}</p>}
          {!dataset.review_ready && <Alert>Review all {dataset.total} cases before approving this dataset ({dataset.reviewed} currently reviewed).</Alert>}
          <div className="kx-settings-actions">
            <button className="kx-button kx-button--primary" disabled={busy || !dataset.review_ready || dataset.approval.status === "approved"} onClick={approveDataset}>Approve reviewed dataset</button>
            <button className="kx-button kx-button--quiet" disabled={busy || dataset.approval.status === "approved"} onClick={() => void update({
              action: "dataset-approval", kind, approval: "reject",
              successMessage: kind + " dataset approval rejected.",
            })}>Reject dataset</button>
            <button className="kx-button kx-button--quiet" disabled={busy} onClick={() => void refresh()}><Icon name="refresh" size={14}/> Refresh</button>
          </div>
          {dataset.export_path && <div className="kx-evidence-list"><p>Immutable export</p><code>{dataset.export_path}</code></div>}
        </section>
      </>}
    </>}
    {!review && !busy && <section className="kx-panel"><div className="kx-empty"><Icon name="database" size={24}/><strong>Quality review unavailable</strong><p>Check that the KALDRAX source checkout contains both evaluation datasets and that the local Python engine is connected.</p></div></section>}
  </>;
}

export function MemoryPage({ settings }: Pick<WorkflowProps, "settings">) {
  const [query, setQuery] = useState(settings.projectId);
  const [includePending, setIncludePending] = useState(true);
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [conflicts, setConflicts] = useState<MemoryConflict[]>([]);
  const [activeTab, setActiveTab] = useState<"search" | "conflicts" | "benchmark" | "quality-benchmark">("search");
  const [reviewer, setReviewer] = useState("");
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
    <div className="kw-tabs" role="tablist" aria-label="Memory views"><button role="tab" aria-selected={activeTab === "search"} className={activeTab === "search" ? "active" : ""} onClick={() => setActiveTab("search")}>Search & review</button><button role="tab" aria-selected={activeTab === "conflicts"} className={activeTab === "conflicts" ? "active" : ""} onClick={() => setActiveTab("conflicts")}>Contradictions <span>{conflicts.length}</span></button><button role="tab" aria-selected={activeTab === "benchmark"} className={activeTab === "benchmark" ? "active" : ""} onClick={() => setActiveTab("benchmark")}>Retrieval review</button><button role="tab" aria-selected={activeTab === "quality-benchmark"} className={activeTab === "quality-benchmark" ? "active" : ""} onClick={() => setActiveTab("quality-benchmark")}>Quality labels</button></div>
    {error && <Alert error>{error}</Alert>}{notice && <Alert>{notice}</Alert>}
    {activeTab === "search" ? <section className="kx-panel">
      <form className="kw-memory-search" onSubmit={search}><input aria-label="Search project memory" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search approved project knowledge…"/><label><input type="checkbox" checked={includePending} onChange={event => setIncludePending(event.target.checked)}/> Include pending</label><button className="kx-button kx-button--primary" type="submit" disabled={busy}>{busy ? "Searching…" : "Search memory"}</button></form>
      {items.length === 0 ? <div className="kx-empty"><Icon name="database" size={24}/><strong>No matching memories</strong><p>Run a task to create episodic memory, or broaden the search query.</p></div> : <div className="kw-memory-list">{items.map(item => <article className="kw-memory-card" key={item.id}>
        <div className="kw-memory-card__head"><div><span className="kw-memory-type">{item.type} · {item.retrieval_method}</span><h3>{item.summary || item.content.slice(0, 120)}</h3></div><Badge tone={item.status}>{item.status}</Badge></div>
        <p>{item.content}</p>
        <div className="kw-memory-meta"><span>Confidence {Math.round(item.confidence * 100)}%</span><span>Retrieval score {item.score.toFixed(3)}</span><span>Source run {item.source_run_id?.slice(0, 8) ?? "—"}</span><span>Expires {formatTime(item.expires_at)}</span></div>
        {item.status === "pending" && <div className="kw-memory-actions"><button className="kx-button kx-button--quiet" onClick={() => review(item, "reject")} disabled={busy}>Reject</button><button className="kx-button kx-button--primary" onClick={() => review(item, "approve")} disabled={busy}>Approve memory</button></div>}
      </article>)}</div>}
    </section> : activeTab === "conflicts" ? <section className="kx-panel"><div className="kx-panel__head"><div><h2>Open contradiction candidates</h2><p>Heuristic matches only. Human review is required before either side is superseded.</p></div><button className="kx-button kx-button--quiet" onClick={loadConflicts} disabled={busy}><Icon name="refresh" size={14}/> Refresh</button></div>
      {conflicts.length === 0 ? <div className="kx-empty"><Icon name="shield" size={24}/><strong>No open conflicts</strong><p>The engine found no unresolved contradiction candidates for this project.</p></div> : conflicts.map(conflict => <article className="kw-conflict-card" key={conflict.id}><div className="kw-conflict-card__head"><Badge tone="warning">Open conflict</Badge><span>{formatTime(conflict.created_at)}</span></div><p>{conflict.reason}</p><div className="kw-conflict-sides"><div><small>LEFT MEMORY</small><code>{conflict.left_memory_id}</code><button className="kx-button kx-button--quiet" disabled={busy} onClick={() => resolve(conflict, conflict.left_memory_id)}>Keep left</button></div><div><small>RIGHT MEMORY</small><code>{conflict.right_memory_id}</code><button className="kx-button kx-button--quiet" disabled={busy} onClick={() => resolve(conflict, conflict.right_memory_id)}>Keep right</button></div></div></article>)}
    </section> : activeTab === "benchmark" ? <BenchmarkReviewPanel settings={settings} reviewer={reviewer}/> : <QualityBenchmarkReviewPanel settings={settings} reviewer={reviewer}/>}
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
