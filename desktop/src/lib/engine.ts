import { invoke } from "@tauri-apps/api/core";

export type RunStatus = "passed" | "failed" | "limit_reached";
export type OperationStatus = "running" | "cancelling" | "completed" | "failed" | "cancelled";

export interface CriterionEvidence { criterion: string; quote: string; }
export interface RunEvaluation {
  passed: boolean;
  satisfied: string[];
  missing: string[];
  evaluator: string;
  evidence: CriterionEvidence[];
}
export interface RunEvent {
  sequence: number;
  event_type: string;
  message: string;
  timestamp: string;
}
export interface RunBudget {
  calls?: number; input_tokens?: number; output_tokens?: number; total_tokens?: number;
  estimated_cost_usd?: number; max_calls?: number; max_input_tokens?: number;
  max_output_tokens?: number; max_total_tokens?: number; max_cost_usd?: number | null;
  cost_is_estimated?: boolean; elapsed_seconds?: number; max_duration_seconds?: number;
}
export interface RunReport {
  run_id: string; objective: string; status: RunStatus; iterations: number;
  final_output: string; evaluations: RunEvaluation[]; events: RunEvent[];
  created_at: string; budget?: RunBudget;
}
export interface EngineStatus {
  connected: boolean; enginePath: string; pythonExecutable: string; engineVersion: string; dataPath: string; bundled: boolean;
}
export interface TaskRunRequest {
  enginePath: string; pythonExecutable: string; objective: string;
  acceptanceCriteria: string[]; maxIterations: number; projectId: string;
  agentId?: string; memoryLimit?: number; apiKey: string;
  executorModel: string; evaluatorModel: string; baseUrl?: string;
}
export interface TeamRunRequest {
  enginePath: string; pythonExecutable: string; objective: string;
  acceptanceCriteria: string[]; projectId: string; agentNamespace: string;
  maxCycles: number; apiKey: string; plannerModel: string; builderModel: string;
  reviewerModel: string; evaluatorModel: string; baseUrl?: string;
  workspacePath?: string; applyChanges?: boolean; verifyModule?: "unittest" | "pytest" | "compileall" | "full";
  sandboxTimeoutSeconds?: number;
}
export interface TeamTrace {
  sequence: number; agent_id: string; role: string; cycle: number;
  output_excerpt: string; timestamp: string;
}
export interface TeamCycle {
  cycle: number; reviewer_approved: boolean; reviewer_findings: string[];
  evaluation_passed: boolean; missing_criteria: string[];
}
export interface TeamReport {
  run_id: string; project_id: string; objective: string; status: RunStatus;
  cycles: number; plan: string; final_output: string;
  evaluation?: RunEvaluation | null; cycle_results: TeamCycle[];
  trace: TeamTrace[]; events: string[]; budget?: RunBudget; created_at: string;
}
export interface RepositoryTeamReport {
  run_id: string; project_id: string; objective: string; status: RunStatus;
  base_commit: string; plan: string; patch: string; summary: string;
  changed_files: string[]; verification?: Record<string, unknown> | null;
  reviewer_approved: boolean; reviewer_findings: string[];
  evaluation?: RunEvaluation | null; cycles: Array<Record<string, unknown>>;
  trace: TeamTrace[]; events: string[]; applied: boolean; cancelled?: boolean; budget?: RunBudget;
  created_at: string;
}
export type SavedTeamReport = TeamReport | RepositoryTeamReport;

export interface OperationSnapshot {
  operationId: string; kind: string; status: OperationStatus; message: string;
  progress: Array<Record<string, unknown>>; result?: Record<string, unknown> | unknown[] | null;
  error?: string | null; startedAt: string; finishedAt?: string | null; exitCode?: number | null;
}
export interface MemoryItem {
  id: string; type: "episodic" | "semantic"; status: string; confidence: number;
  expires_at?: string | null; score: number; lexical_score: number;
  semantic_score?: number | null; freshness_score: number; retrieval_method: string;
  summary: string; content: string; source_run_id?: string | null;
  source_event_sequences: number[]; agent_id?: string | null;
  tags: string[]; metadata: Record<string, unknown>;
}
export interface BenchmarkReviewMemory {
  id: string;
  category: string;
  content: string;
  summary: string;
  source: { path?: string; anchor?: string };
  tags: string[];
}
export interface BenchmarkReviewQuery {
  id: string;
  category: string;
  query: string;
  rationale: string;
  proposed_relevant: string[];
  relevant: string[];
  status: "pending" | "approved" | "modified" | "rejected" | "auto_approved" | "ai_reviewed" | "ai_abstained";
  decision_source?: "human" | "automated" | "ai_model" | null;
  ai_review?: {
    model: string;
    reviewed_at: string;
    decision: "accept" | "correct" | "abstain";
    model_decision: "accept" | "correct" | "abstain";
    confidence: number;
    confidence_threshold: number;
    rationale: string;
    evidence: Array<{ memory_id: string; start: number; end: number; quote_sha256: string }>;
    source_sha256: string;
    policy: string;
  } | null;
  reviewer?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
}
export interface BenchmarkReviewState {
  dataset_name: string;
  dataset_version: string;
  source_revision?: string | null;
  source_sha256: string;
  session_path: string;
  memories: BenchmarkReviewMemory[];
  queries: BenchmarkReviewQuery[];
  automation_runs: Array<{
    policy: string;
    triggered_by: string;
    triggered_at: string;
    source_sha256: string;
    query_ids: string[];
  }>;
  auto_approved_count: number;
  ai_review_runs: Array<{ policy: string; model: string; triggered_by: string; reviewed_at: string; source_sha256: string; query_ids: string[]; privacy_status: string }>;
  ai_reviewed_count: number;
  ai_abstained_count: number;
  ai_privacy_screening?: {
    policy: string; model: string; reviewed_at: string; triggered_by: string;
    source_sha256: string; status: string; decision: "clear" | "flag" | "abstain";
    summary: string; reviewed_memory_ids: string[];
    findings: Array<{ memory_id: string; category: string; severity: "low" | "medium" | "high"; rationale: string; start: number; end: number; quote_sha256: string }>;
    human_approval_status: "pending";
  } | null;
  ai_export_path?: string | null;
  dataset_approval: { status: string; reviewer?: string | null; reviewed_at?: string | null };
  privacy_screening: { status: string; scope: string; note: string; reviewer?: string | null; reviewed_at?: string | null };
  review_ready: boolean;
  benchmark_status: string;
  export_path?: string | null;
}
export interface QualityReviewCase {
  id: string;
  category: string;
  reviewed: boolean;
  review_status: string;
  reviewer?: string | null;
  reviewed_at?: string | null;
  note?: string | null;
  left?: string;
  right?: string;
  proposed_expected_conflict?: boolean;
  expected_conflict?: boolean;
  objective?: string;
  candidate?: string;
  proposed_expected?: Array<{ match_terms: string[] }>;
  expected?: Array<{ match_terms: string[] }>;
}
export interface QualityReviewDataset {
  name: string;
  version?: string | number;
  total: number;
  reviewed: number;
  review_ready: boolean;
  approval: { status: string; reviewer?: string | null; reviewed_at?: string | null };
  export_path?: string | null;
  cases: QualityReviewCase[];
}
export interface QualityReviewState {
  reviewer: string;
  session_path: string;
  source_hashes: Record<string, string>;
  contradiction: QualityReviewDataset;
  extraction: QualityReviewDataset;
  status: string;
}

export interface MemoryConflict {
  id: string; left_memory_id: string; right_memory_id: string;
  reason: string; status: string; created_at: string; resolution?: string | null;
}
export interface RepositoryStatus {
  root: string; branch: string; head: string; clean: boolean;
  status: string; changes: Array<{ code: string; path: string }>;
}
export interface RepositoryFile { path: string; size: number; }
export interface RepositoryFileContent {
  path: string; content: string; sha256: string; size: number;
}
export interface RepositoryApplyResult {
  path: string; created: boolean; old_sha256?: string | null; new_sha256: string;
  backup_path?: string | null; diff: string; size: number;
}

export async function verifyEngine(enginePath: string, pythonExecutable: string): Promise<EngineStatus> {
  return invoke<EngineStatus>("verify_engine", { enginePath, pythonExecutable });
}
export async function startOfflineDemo(enginePath: string, pythonExecutable: string, projectId: string): Promise<OperationSnapshot> {
  return invoke<OperationSnapshot>("start_offline_demo", { enginePath, pythonExecutable, projectId });
}
export async function startTaskRun(request: TaskRunRequest): Promise<OperationSnapshot> {
  return invoke<OperationSnapshot>("start_task_run", { request });
}
export async function startTeamRun(request: TeamRunRequest): Promise<OperationSnapshot> {
  return invoke<OperationSnapshot>("start_team_run", { request });
}
export async function startSandboxRun(input: {
  enginePath: string; pythonExecutable: string; sourcePath: string; timeoutSeconds: number;
  memoryMb: number; cpuCount: number; pidsLimit: number;
}): Promise<OperationSnapshot> {
  return invoke<OperationSnapshot>("start_sandbox_run", input);
}
export async function getOperation(operationId: string): Promise<OperationSnapshot> {
  return invoke<OperationSnapshot>("get_operation", { operationId });
}
export async function cancelOperation(operationId: string): Promise<OperationSnapshot> {
  return invoke<OperationSnapshot>("cancel_operation", { operationId });
}
export async function listRuns(enginePath: string): Promise<RunReport[]> {
  return invoke<RunReport[]>("list_runs", { enginePath });
}
export async function getRunReport(enginePath: string, runId: string): Promise<RunReport> {
  return invoke<RunReport>("get_run_report", { enginePath, runId });
}
export async function listTeamRuns(enginePath: string): Promise<SavedTeamReport[]> {
  return invoke<SavedTeamReport[]>("list_team_runs", { enginePath });
}
export async function memorySearch(input: {
  enginePath: string; pythonExecutable: string; projectId: string; query: string;
  limit: number; agentId?: string; includePending: boolean;
}): Promise<MemoryItem[]> {
  return invoke<MemoryItem[]>("memory_search", input);
}
export async function memoryConflicts(input: {
  enginePath: string; pythonExecutable: string; projectId: string;
}): Promise<MemoryConflict[]> {
  return invoke<MemoryConflict[]>("memory_conflicts", input);
}
export async function memoryReview(input: {
  enginePath: string; pythonExecutable: string; memoryId: string; decision: "approve" | "reject"; reviewer: string;
}): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>("memory_review", input);
}

export async function benchmarkReviewState(input: {
  enginePath: string; pythonExecutable: string; reviewer: string;
}): Promise<BenchmarkReviewState> {
  return invoke<BenchmarkReviewState>("benchmark_review_state", input);
}
export async function benchmarkReviewUpdate(input: {
  enginePath: string;
  pythonExecutable: string;
  reviewer: string;
  action: "query" | "dataset-approval" | "privacy-approval" | "auto-approve-proposals" | "model-review";
  queryId?: string;
  decision?: "approve" | "reject" | "modify";
  memoryIds?: string[];
  note?: string;
  approval?: "approve" | "reject";
  privacyConfirmation?: string;
  confirmProviderDataEgress?: boolean;
}): Promise<BenchmarkReviewState> {
  return invoke<BenchmarkReviewState>("benchmark_review_update", {
    enginePath: input.enginePath,
    pythonExecutable: input.pythonExecutable,
    reviewer: input.reviewer,
    action: input.action,
    queryId: input.queryId,
    decision: input.decision,
    memoryIds: input.memoryIds,
    note: input.note,
    approval: input.approval,
    privacyConfirmation: input.privacyConfirmation,
    confirmProviderDataEgress: input.confirmProviderDataEgress ?? false,
  });
}

export async function qualityReviewState(input: {
  enginePath: string; pythonExecutable: string; reviewer: string;
}): Promise<QualityReviewState> {
  return invoke<QualityReviewState>("quality_review_state", input);
}

export async function qualityReviewUpdate(input: {
  enginePath: string;
  pythonExecutable: string;
  reviewer: string;
  action: "case" | "dataset-approval";
  kind: "contradiction" | "extraction";
  caseId?: string;
  decision?: "approve" | "modify";
  expectedConflict?: boolean;
  expectedClaims?: Array<{ match_terms: string[] }>;
  note?: string;
  confirmation?: string;
  approval?: "approve" | "reject";
}): Promise<QualityReviewState> {
  return invoke<QualityReviewState>("quality_review_update", input);
}

export async function memoryResolveConflict(input: {
  enginePath: string; pythonExecutable: string; conflictId: string; keepMemoryId: string; reviewer: string;
}): Promise<Record<string, unknown>> {
  return invoke<Record<string, unknown>>("memory_resolve_conflict", input);
}
export async function repositoryStatus(input: {
  enginePath: string; pythonExecutable: string; repositoryPath: string;
}): Promise<RepositoryStatus> {
  return invoke<RepositoryStatus>("repository_status", input);
}
export async function repositoryFiles(input: {
  enginePath: string; pythonExecutable: string; repositoryPath: string; directory: string; limit: number;
}): Promise<RepositoryFile[]> {
  return invoke<RepositoryFile[]>("repository_files", input);
}
export async function repositoryReadFile(input: {
  enginePath: string; pythonExecutable: string; repositoryPath: string; relativePath: string;
}): Promise<RepositoryFileContent> {
  return invoke<RepositoryFileContent>("repository_read_file", input);
}
export async function repositoryApplyFile(input: {
  enginePath: string; pythonExecutable: string; repositoryPath: string; relativePath: string;
  content: string; expectedSha256?: string;
}): Promise<RepositoryApplyResult> {
  return invoke<RepositoryApplyResult>("repository_apply_file", input);
}
