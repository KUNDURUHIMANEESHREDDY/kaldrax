use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::fs::{self, File};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::path::BaseDirectory;
use tauri::{AppHandle, Manager, State};

static OPERATION_SEQUENCE: AtomicU64 = AtomicU64::new(1);

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct AppInfo {
    app: &'static str,
    version: &'static str,
    platform: &'static str,
    arch: &'static str,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct EngineStatus {
    connected: bool,
    engine_path: String,
    python_executable: String,
    engine_version: String,
    data_path: String,
    bundled: bool,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct TaskRunRequest {
    engine_path: String,
    python_executable: String,
    objective: String,
    acceptance_criteria: Vec<String>,
    max_iterations: u8,
    project_id: String,
    agent_id: Option<String>,
    memory_limit: Option<u8>,
    api_key: String,
    executor_model: String,
    evaluator_model: String,
    base_url: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct TeamRunRequest {
    engine_path: String,
    python_executable: String,
    objective: String,
    acceptance_criteria: Vec<String>,
    project_id: String,
    agent_namespace: String,
    max_cycles: u8,
    api_key: String,
    planner_model: String,
    builder_model: String,
    reviewer_model: String,
    evaluator_model: String,
    base_url: Option<String>,
    workspace_path: Option<String>,
    #[serde(default)]
    apply_changes: bool,
    verify_module: Option<String>,
    sandbox_timeout_seconds: Option<u16>,
}

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct OperationSnapshot {
    operation_id: String,
    kind: String,
    status: String,
    message: String,
    progress: Vec<Value>,
    result: Option<Value>,
    error: Option<String>,
    started_at: String,
    finished_at: Option<String>,
    exit_code: Option<i32>,
}

struct Operation {
    snapshot: Mutex<OperationSnapshot>,
    child: Mutex<Option<Child>>,
    cancelled: AtomicBool,
    progress_path: PathBuf,
    stdout_path: PathBuf,
    stderr_path: PathBuf,
    cancel_file: Option<PathBuf>,
}

#[derive(Default)]
struct OperationManager {
    operations: Mutex<HashMap<String, Arc<Operation>>>,
}

#[tauri::command]
fn get_app_info() -> AppInfo {
    AppInfo {
        app: "KALDRAX",
        version: env!("CARGO_PKG_VERSION"),
        platform: std::env::consts::OS,
        arch: std::env::consts::ARCH,
    }
}

const PACKAGED_ENGINE_SENTINEL: &str = "__KALDRAX_PACKAGED_ENGINE__";

fn packaged_engine_executable(engine_root: &Path) -> PathBuf {
    engine_root.join("kaldrax-engine").join("kaldrax-engine.exe")
}

fn is_packaged_engine_root(engine_root: &Path) -> bool {
    packaged_engine_executable(engine_root).is_file()
}

fn packaged_engine_root(app: &AppHandle) -> Option<PathBuf> {
    let executable = app
        .path()
        .resolve("kaldrax-engine/kaldrax-engine.exe", BaseDirectory::Resource)
        .ok()
        .filter(|path| path.is_file())?;
    executable.parent()?.parent()?.canonicalize().ok()
}

fn validate_source_engine_path(engine_path: &str) -> Result<PathBuf, String> {
    let path = Path::new(engine_path)
        .canonicalize()
        .map_err(|_| "KALDRAX engine directory does not exist or cannot be opened.".to_string())?;
    if !path.is_dir()
        || !path.join("pyproject.toml").is_file()
        || !path.join("src").join("kaldrax").join("cli.py").is_file()
    {
        return Err(
            "Choose the KALDRAX Python source directory (it must contain pyproject.toml and src/kaldrax/cli.py)."
                .to_string(),
        );
    }
    Ok(path)
}

fn validate_engine_path(app: &AppHandle, engine_path: &str) -> Result<PathBuf, String> {
    let path = Path::new(engine_path)
        .canonicalize()
        .map_err(|_| "KALDRAX engine directory does not exist or cannot be opened.".to_string())?;
    if let Some(packaged_root) = packaged_engine_root(app) {
        if path != packaged_root {
            return Err(
                "This installation must use its bundled KALDRAX runtime; alternate engine paths are disabled."
                    .to_string(),
            );
        }
        return Ok(path);
    }
    validate_source_engine_path(engine_path)
}

fn python_command(python_executable: &str, engine_path: &Path) -> Command {
    let mut command = if python_executable == PACKAGED_ENGINE_SENTINEL {
        Command::new(packaged_engine_executable(engine_path))
    } else {
        let mut command = Command::new(python_executable);
        command.args(["-m", "kaldrax.cli"]);
        command
    };
    command.current_dir(engine_path);
    command
}

fn engine_command(
    app: &AppHandle,
    engine_path: &Path,
    python_executable: &str,
) -> Result<Command, String> {
    if let Some(packaged_root) = packaged_engine_root(app) {
        let requested_root = engine_path
            .canonicalize()
            .map_err(|_| "KALDRAX engine directory does not exist or cannot be opened.".to_string())?;
        if requested_root != packaged_root {
            return Err(
                "This installation must use its bundled KALDRAX runtime; alternate engine paths are disabled."
                    .to_string(),
            );
        }
        return Ok(python_command(PACKAGED_ENGINE_SENTINEL, &packaged_root));
    }

    let source_path = engine_path
        .to_str()
        .ok_or_else(|| "KALDRAX engine path is not valid UTF-8.".to_string())?;
    let source_root = validate_source_engine_path(source_path)?;
    if python_executable.trim().is_empty() {
        return Err("Enter a Python executable (for example, python).".to_string());
    }
    Ok(python_command(python_executable, &source_root))
}

fn engine_version(engine_path: &Path) -> String {
    if is_packaged_engine_root(engine_path) {
        return fs::read_to_string(engine_path.join("kaldrax-engine").join("version.txt"))
            .map(|value| value.trim().to_string())
            .unwrap_or_else(|_| "unknown".to_string());
    }
    let manifest = fs::read_to_string(engine_path.join("pyproject.toml")).unwrap_or_default();
    let version = manifest
        .lines()
        .skip_while(|line| line.trim() != "[project]")
        .skip(1)
        .take_while(|line| !line.trim().starts_with('['))
        .find_map(|line| {
            let (key, value) = line.split_once('=')?;
            (key.trim() == "version").then(|| {
                value
                    .trim()
                    .trim_matches('"')
                    .trim_matches('\'')
                    .to_string()
            })
        });
    version.unwrap_or_else(|| "unknown".to_string())
}

fn app_data_directory(app: &AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .app_data_dir()
        .map_err(|error| format!("Cannot locate KALDRAX application data directory: {error}"))?;
    fs::create_dir_all(&path)
        .map_err(|error| format!("Cannot create KALDRAX application data directory: {error}"))?;
    Ok(path)
}

fn state_directory(app: &AppHandle) -> Result<PathBuf, String> {
    let path = app_data_directory(app)?.join(".kaldrax");
    fs::create_dir_all(&path)
        .map_err(|error| format!("Cannot create KALDRAX state directory: {error}"))?;
    Ok(path)
}

fn memory_database(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(state_directory(app)?.join("memory.sqlite3"))
}

fn report_directory(app: &AppHandle) -> Result<PathBuf, String> {
    let path = state_directory(app)?.join("runs");
    fs::create_dir_all(&path)
        .map_err(|error| format!("Cannot create run history directory: {error}"))?;
    Ok(path)
}

fn migrate_legacy_state(
    app: &AppHandle,
    runtime_root: &Path,
    runtime_executable: &str,
    source_state_directory: &Path,
) -> Result<(), String> {
    let data_root = app_data_directory(app)?;
    let destination = state_directory(app)?;
    let output = engine_command(app, runtime_root, runtime_executable)?
        .arg("storage")
        .arg("migrate")
        .arg("--source")
        .arg(source_state_directory)
        .arg("--destination")
        .arg(&destination)
        .env("KALDRAX_DATA_DIR", &data_root)
        .output()
        .map_err(|error| format!("Could not migrate existing KALDRAX data: {error}"))?;
    if !output.status.success() {
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if detail.is_empty() {
            "Existing KALDRAX data could not be migrated. The original data was not deleted.".to_string()
        } else {
            format!("Existing KALDRAX data migration failed; the original data was not deleted: {detail}")
        });
    }
    Ok(())
}

fn cli_json(
    app: &AppHandle,
    engine_path: &Path,
    python_executable: &str,
    args: &[String],
    envs: &[(&str, &str)],
) -> Result<Value, String> {
    let data_root = app_data_directory(app)?;
    let mut command = engine_command(app, engine_path, python_executable)?;
    command
        .args(args)
        .env("KALDRAX_DATA_DIR", data_root);
    for (key, value) in envs {
        command.env(key, value);
    }
    let output = command
        .output()
        .map_err(|error| format!("Could not start KALDRAX: {error}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    match serde_json::from_str::<Value>(stdout.trim()) {
        Ok(value) => Ok(value),
        Err(_) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            if stderr.is_empty() {
                Err(format!(
                    "KALDRAX returned no valid JSON (process exit {}).",
                    output.status.code().unwrap_or(-1)
                ))
            } else {
                Err(stderr)
            }
        }
    }
}

fn parse_progress_file(path: &Path, offset: &mut usize, events: &mut Vec<Value>) -> Option<String> {
    let bytes = fs::read(path).ok()?;
    let mut latest = None;
    while *offset < bytes.len() {
        let remaining = &bytes[*offset..];
        let Some(end) = remaining.iter().position(|byte| *byte == b'\n') else {
            break;
        };
        let line = &remaining[..end];
        *offset += end + 1;
        if let Ok(value) = serde_json::from_slice::<Value>(line) {
            latest = value
                .get("message")
                .and_then(Value::as_str)
                .map(str::to_string);
            events.push(value);
        }
    }
    latest
}

fn now_timestamp() -> String {
    let seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or_default();
    format!("{seconds}")
}

fn start_cli_operation(
    app: &AppHandle,
    manager: &OperationManager,
    engine_path: &str,
    python_executable: &str,
    kind: &str,
    args: Vec<String>,
    envs: Vec<(String, String)>,
    cancel_file: Option<PathBuf>,
) -> Result<OperationSnapshot, String> {
    if python_executable.trim().is_empty() {
        return Err("Enter a Python executable (for example, python).".to_string());
    }
    let root = validate_engine_path(app, engine_path)?;
    let operation_id = format!(
        "op-{}-{}",
        now_timestamp(),
        OPERATION_SEQUENCE.fetch_add(1, Ordering::Relaxed)
    );
    let data_root = app_data_directory(app)?;
    let operation_dir = state_directory(app)?.join("operations").join(&operation_id);
    fs::create_dir_all(&operation_dir)
        .map_err(|error| format!("Cannot create operation workspace: {error}"))?;
    let progress_path = operation_dir.join("progress.jsonl");
    let stdout_path = operation_dir.join("stdout.json");
    let stderr_path = operation_dir.join("stderr.log");
    let stdout = File::create(&stdout_path)
        .map_err(|error| format!("Cannot create operation output: {error}"))?;
    let stderr = File::create(&stderr_path)
        .map_err(|error| format!("Cannot create operation log: {error}"))?;

    let mut args = args;
    if matches!(kind, "offline_demo" | "task_run" | "team_run") {
        args.push("--progress-jsonl".to_string());
        args.push(progress_path.to_string_lossy().into_owned());
    }
    let mut command = engine_command(app, &root, python_executable)?;
    command
        .args(args)
        .env("PYTHONUNBUFFERED", "1")
        .env("KALDRAX_DESKTOP_OPERATION_ID", &operation_id)
        .env("KALDRAX_DATA_DIR", &data_root)
        .stdout(Stdio::from(stdout))
        .stderr(Stdio::from(stderr));
    for (key, value) in &envs {
        command.env(key, value);
    }

    let child = command
        .spawn()
        .map_err(|error| format!("Could not start KALDRAX operation: {error}"))?;
    let started_at = now_timestamp();
    let snapshot = OperationSnapshot {
        operation_id: operation_id.clone(),
        kind: kind.to_string(),
        status: "running".to_string(),
        message: "Starting local KALDRAX operation.".to_string(),
        progress: Vec::new(),
        result: None,
        error: None,
        started_at,
        finished_at: None,
        exit_code: None,
    };
    let operation = Arc::new(Operation {
        snapshot: Mutex::new(snapshot.clone()),
        child: Mutex::new(Some(child)),
        cancelled: AtomicBool::new(false),
        progress_path: progress_path.clone(),
        stdout_path: stdout_path.clone(),
        stderr_path: stderr_path.clone(),
        cancel_file,
    });

    {
        let mut operations = manager
            .operations
            .lock()
            .map_err(|_| "Operation manager is unavailable.".to_string())?;
        operations.insert(operation_id, Arc::clone(&operation));
    }

    thread::spawn(move || {
        let mut progress_offset = 0usize;
        loop {
            if let Ok(mut current) = operation.snapshot.lock() {
                if let Some(message) = parse_progress_file(
                    &operation.progress_path,
                    &mut progress_offset,
                    &mut current.progress,
                ) {
                    current.message = message;
                }
            }
            let exit_status = match operation.child.lock() {
                Ok(mut child_slot) => match child_slot.as_mut() {
                    Some(child) => match child.try_wait() {
                        Ok(value) => value,
                        Err(error) => {
                            if let Ok(mut current) = operation.snapshot.lock() {
                                current.status = "failed".to_string();
                                current.error =
                                    Some(format!("Could not inspect process status: {error}"));
                                current.finished_at = Some(now_timestamp());
                            }
                            return;
                        }
                    },
                    None => None,
                },
                Err(_) => None,
            };
            if let Some(status) = exit_status {
                if let Ok(mut current) = operation.snapshot.lock() {
                    let _ = parse_progress_file(
                        &operation.progress_path,
                        &mut progress_offset,
                        &mut current.progress,
                    );
                    current.exit_code = status.code();
                    current.finished_at = Some(now_timestamp());
                    if operation.cancelled.load(Ordering::Relaxed) {
                        current.status = "cancelled".to_string();
                        current.message = "Operation cancelled.".to_string();
                    } else {
                        match fs::read_to_string(&operation.stdout_path)
                            .ok()
                            .and_then(|output| serde_json::from_str::<Value>(&output).ok())
                        {
                            Some(result) => {
                                current.status = "completed".to_string();
                                current.message = "KALDRAX operation completed.".to_string();
                                current.result = Some(result);
                            }
                            None => {
                                current.status = "failed".to_string();
                                current.error = Some(
                                    fs::read_to_string(&operation.stderr_path)
                                        .unwrap_or_else(|_| {
                                            format!(
                                                "KALDRAX returned no JSON report (exit {}).",
                                                status.code().unwrap_or(-1)
                                            )
                                        })
                                        .trim()
                                        .to_string(),
                                );
                                current.message = "KALDRAX operation failed.".to_string();
                            }
                        }
                    }
                }
                break;
            }
            thread::sleep(Duration::from_millis(120));
        }
    });

    Ok(snapshot)
}

#[tauri::command]
async fn verify_engine(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
) -> Result<EngineStatus, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let packaged_executable = packaged_engine_root(&app)
            .map(|root| packaged_engine_executable(&root))
            .filter(|path| path.is_file());

        let (path, runtime_executable, bundled) = if let Some(executable) = packaged_executable {
            let root = executable
                .parent()
                .and_then(Path::parent)
                .ok_or_else(|| "Bundled KALDRAX resource path is invalid.".to_string())?
                .canonicalize()
                .map_err(|error| format!("Cannot resolve bundled KALDRAX resources: {error}"))?;

            // Migrate state from a previously configured source checkout before switching to
            // the packaged runtime. Never treat the read-only resource directory as legacy data.
            if !engine_path.trim().is_empty() {
                if let Ok(legacy_root) = validate_source_engine_path(&engine_path) {
                    if legacy_root != root
                        && legacy_root.join("pyproject.toml").is_file()
                        && legacy_root.join(".kaldrax").is_dir()
                    {
                        migrate_legacy_state(
                            &app,
                            &root,
                            PACKAGED_ENGINE_SENTINEL,
                            &legacy_root.join(".kaldrax"),
                        )?;
                    }
                }
            }
            (root, PACKAGED_ENGINE_SENTINEL.to_string(), true)
        } else {
            if python_executable.trim().is_empty() {
                return Err("No bundled runtime was found. Choose a KALDRAX source checkout and Python executable.".to_string());
            }
            let root = validate_engine_path(&app, &engine_path)?;
            migrate_legacy_state(
                &app,
                &root,
                &python_executable,
                &root.join(".kaldrax"),
            )?;
            (root, python_executable, false)
        };

        let output = engine_command(&app, &path, &runtime_executable)?
            .arg("--help")
            .output()
            .map_err(|error| format!("Could not start KALDRAX: {error}"))?;
        if !output.status.success() {
            let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
            return Err(if detail.is_empty() {
                "KALDRAX engine health check failed.".to_string()
            } else {
                format!("KALDRAX engine health check failed: {detail}")
            });
        }
        Ok(EngineStatus {
            connected: true,
            engine_path: path.display().to_string(),
            python_executable: runtime_executable,
            engine_version: if bundled {
                engine_version(&path).replace("unknown", env!("CARGO_PKG_VERSION"))
            } else {
                engine_version(&path)
            },
            data_path: state_directory(&app)?.display().to_string(),
            bundled,
        })
    })
    .await
    .map_err(|error| format!("Engine check task failed: {error}"))?
}

#[tauri::command]
fn start_offline_demo(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    project_id: String,
    manager: State<'_, OperationManager>,
) -> Result<OperationSnapshot, String> {
    if project_id.trim().is_empty() {
        return Err("Project ID must not be empty.".to_string());
    }
    let _root = validate_engine_path(&app, &engine_path)?;
    let artifacts = report_directory(&app)?;
    let args = vec![
        "demo".to_string(),
        "--project".to_string(),
        project_id,
        "--artifacts".to_string(),
        artifacts.to_string_lossy().into_owned(),
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
        "--progress-jsonl".to_string(),
        state_directory(&app)?
            .join("operations")
            .join("pending-progress.jsonl")
            .to_string_lossy()
            .into_owned(),
    ];
    // start_cli_operation creates the unique operation directory; replace the
    // placeholder progress argument with a file beneath the engine's operations root.
    let mut args = args;
    let _ = args.pop();
    let _ = args.pop();
    start_cli_operation(
        &app,
        &manager,
        &engine_path,
        &python_executable,
        "offline_demo",
        args,
        Vec::new(),
        None,
    )
}

#[tauri::command]
fn start_task_run(
    app: AppHandle,
    request: TaskRunRequest,
    manager: State<'_, OperationManager>,
) -> Result<OperationSnapshot, String> {
    let _root = validate_engine_path(&app, &request.engine_path)?;
    if request.objective.trim().is_empty() {
        return Err("Objective is required.".to_string());
    }
    if request.acceptance_criteria.is_empty()
        || request
            .acceptance_criteria
            .iter()
            .any(|item| item.trim().is_empty())
    {
        return Err("Add at least one non-empty acceptance criterion.".to_string());
    }
    let mut unique = request.acceptance_criteria.clone();
    unique.sort();
    unique.dedup();
    if unique.len() != request.acceptance_criteria.len() {
        return Err("Acceptance criteria must be unique.".to_string());
    }
    if !(1..=20).contains(&request.max_iterations) {
        return Err("Maximum iterations must be between 1 and 20.".to_string());
    }
    if request.project_id.trim().is_empty() {
        return Err("Project ID is required.".to_string());
    }
    if request.api_key.trim().is_empty() {
        return Err("Provider API key is required for an LLM-backed run.".to_string());
    }
    if request.executor_model.trim().is_empty() || request.evaluator_model.trim().is_empty() {
        return Err("Configure both executor and evaluator models.".to_string());
    }
    if request
        .executor_model
        .eq_ignore_ascii_case(&request.evaluator_model)
    {
        return Err("Executor and evaluator must use different model identifiers.".to_string());
    }

    let mut args = vec![
        "run".to_string(),
        "--objective".to_string(),
        request.objective,
    ];
    for criterion in request.acceptance_criteria {
        args.push("--criterion".to_string());
        args.push(criterion);
    }
    args.extend([
        "--max-iterations".to_string(),
        request.max_iterations.to_string(),
        "--project".to_string(),
        request.project_id,
        "--memory-limit".to_string(),
        request.memory_limit.unwrap_or(5).clamp(1, 20).to_string(),
        "--artifacts".to_string(),
        report_directory(&app)?.to_string_lossy().into_owned(),
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
    ]);
    if let Some(agent_id) = request.agent_id.filter(|value| !value.trim().is_empty()) {
        args.push("--agent".to_string());
        args.push(agent_id);
    }
    let mut envs = vec![
        ("KALDRAX_API_KEY".to_string(), request.api_key),
        ("KALDRAX_MODEL".to_string(), request.executor_model),
        (
            "KALDRAX_EVALUATOR_MODEL".to_string(),
            request.evaluator_model,
        ),
    ];
    if let Some(base_url) = request.base_url.filter(|value| !value.trim().is_empty()) {
        envs.push(("KALDRAX_BASE_URL".to_string(), base_url));
    }
    start_cli_operation(
        &app,
        &manager,
        &request.engine_path,
        &request.python_executable,
        "task_run",
        args,
        envs,
        None,
    )
}

#[tauri::command]
fn start_team_run(
    app: AppHandle,
    request: TeamRunRequest,
    manager: State<'_, OperationManager>,
) -> Result<OperationSnapshot, String> {
    let _root = validate_engine_path(&app, &request.engine_path)?;
    if request.objective.trim().is_empty()
        || request.project_id.trim().is_empty()
        || request.agent_namespace.trim().is_empty()
    {
        return Err("Objective, project ID and agent namespace are required.".to_string());
    }
    if request.acceptance_criteria.is_empty()
        || request
            .acceptance_criteria
            .iter()
            .any(|item| item.trim().is_empty())
    {
        return Err("Add at least one non-empty acceptance criterion.".to_string());
    }
    if !(1..=5).contains(&request.max_cycles) {
        return Err("Maximum team cycles must be between 1 and 5.".to_string());
    }
    let models = [
        request.planner_model.trim(),
        request.builder_model.trim(),
        request.reviewer_model.trim(),
        request.evaluator_model.trim(),
    ];
    if models.iter().any(|model| model.is_empty()) {
        return Err("Configure all four team model roles.".to_string());
    }
    let mut distinct: Vec<String> = models
        .iter()
        .map(|model| model.to_ascii_lowercase())
        .collect();
    distinct.sort();
    distinct.dedup();
    if distinct.len() != 4 {
        return Err(
            "Planner, builder, reviewer and evaluator models must all be different.".to_string(),
        );
    }
    if request.api_key.trim().is_empty() {
        return Err("Provider API key is required for a team run.".to_string());
    }
    let mut args = vec![
        "team".to_string(),
        "--objective".to_string(),
        request.objective,
    ];
    for criterion in request.acceptance_criteria {
        args.push("--criterion".to_string());
        args.push(criterion);
    }
    args.extend([
        "--project".to_string(),
        request.project_id,
        "--agent-namespace".to_string(),
        request.agent_namespace,
        "--max-cycles".to_string(),
        request.max_cycles.to_string(),
        "--artifacts".to_string(),
        report_directory(&app)?.to_string_lossy().into_owned(),
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
    ]);
    if request.apply_changes
        && request
            .workspace_path
            .as_deref()
            .is_none_or(|value| value.trim().is_empty())
    {
        return Err("Applying repository changes requires a selected Git worktree.".to_string());
    }
    let mut repository_cancel_file: Option<PathBuf> = None;
    if let Some(workspace_path) = request
        .workspace_path
        .as_deref()
        .filter(|value| !value.trim().is_empty())
    {
        let workspace = Path::new(workspace_path)
            .canonicalize()
            .map_err(|_| "Selected repository directory does not exist.".to_string())?;
        if !workspace.is_dir() {
            return Err("Selected repository path must be a directory.".to_string());
        }
        let verify_module = request.verify_module.as_deref().unwrap_or("unittest");
        if !["unittest", "pytest", "compileall", "full"].contains(&verify_module) {
            return Err("Verification module must be full, unittest, pytest or compileall.".to_string());
        }
        let sandbox_timeout = request.sandbox_timeout_seconds.unwrap_or(120);
        if !(1..=120).contains(&sandbox_timeout) {
            return Err(
                "Repository sandbox timeout must be between 1 and 120 seconds.".to_string(),
            );
        }
        args.extend([
            "--workspace".to_string(),
            workspace.to_string_lossy().into_owned(),
            "--verify-module".to_string(),
            verify_module.to_string(),
            "--sandbox-timeout".to_string(),
            sandbox_timeout.to_string(),
        ]);
        let cancel_path = state_directory(&app)?.join("operations").join(format!(
            "repository-team-cancel-{}.flag",
            OPERATION_SEQUENCE.fetch_add(1, Ordering::Relaxed)
        ));
        if let Some(parent) = cancel_path.parent() {
            fs::create_dir_all(parent)
                .map_err(|error| format!("Cannot prepare repository cancellation: {error}"))?;
        }
        let _ = fs::remove_file(&cancel_path);
        args.extend([
            "--cancel-file".to_string(),
            cancel_path.to_string_lossy().into_owned(),
        ]);
        repository_cancel_file = Some(cancel_path);
        if request.apply_changes {
            args.push("--apply".to_string());
        }
    }
    let mut envs = vec![
        ("KALDRAX_API_KEY".to_string(), request.api_key),
        ("KALDRAX_PLANNER_MODEL".to_string(), request.planner_model),
        ("KALDRAX_MODEL".to_string(), request.builder_model),
        ("KALDRAX_REVIEWER_MODEL".to_string(), request.reviewer_model),
        (
            "KALDRAX_EVALUATOR_MODEL".to_string(),
            request.evaluator_model,
        ),
    ];
    if let Some(base_url) = request.base_url.filter(|value| !value.trim().is_empty()) {
        envs.push(("KALDRAX_BASE_URL".to_string(), base_url));
    }
    start_cli_operation(
        &app,
        &manager,
        &request.engine_path,
        &request.python_executable,
        "team_run",
        args,
        envs,
        repository_cancel_file,
    )
}

#[tauri::command]
fn start_sandbox_run(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    source_path: String,
    timeout_seconds: u8,
    memory_mb: u16,
    cpu_count: f32,
    pids_limit: u16,
    manager: State<'_, OperationManager>,
) -> Result<OperationSnapshot, String> {
    let _root = validate_engine_path(&app, &engine_path)?;
    if !(1..=120).contains(&timeout_seconds)
        || !(64..=1024).contains(&memory_mb)
        || !(0.25..=2.0).contains(&cpu_count)
        || !(16..=128).contains(&pids_limit)
    {
        return Err("Sandbox limits are outside the supported ranges.".to_string());
    }
    let selected = Path::new(&source_path)
        .canonicalize()
        .map_err(|_| "Selected Python file does not exist.".to_string())?;
    if !selected.is_file()
        || selected
            .extension()
            .and_then(|extension| extension.to_str())
            != Some("py")
    {
        return Err("Choose a single .py source file.".to_string());
    }
    let source =
        fs::read(&selected).map_err(|error| format!("Cannot read source file: {error}"))?;
    if source.len() > 1_000_000 {
        return Err("Source file exceeds the 1 MB sandbox limit.".to_string());
    }
    let operation_id = format!(
        "sandbox-{}-{}",
        now_timestamp(),
        OPERATION_SEQUENCE.fetch_add(1, Ordering::Relaxed)
    );
    let workspace = state_directory(&app)?.join("sandbox-inputs");
    fs::create_dir_all(&workspace)
        .map_err(|error| format!("Cannot create sandbox input folder: {error}"))?;
    let safe_source = workspace.join(format!("{operation_id}.py"));
    let cancel_file = workspace.join(format!("{operation_id}.cancel"));
    let _ = fs::remove_file(&cancel_file);
    fs::write(&safe_source, source)
        .map_err(|error| format!("Cannot stage sandbox source: {error}"))?;
    let mut args = vec![
        "sandbox".to_string(),
        "run-python".to_string(),
        safe_source.to_string_lossy().into_owned(),
        "--timeout".to_string(),
        timeout_seconds.to_string(),
        "--memory-mb".to_string(),
        memory_mb.to_string(),
        "--cpu-count".to_string(),
        cpu_count.to_string(),
        "--pids-limit".to_string(),
        pids_limit.to_string(),
        "--workspace-root".to_string(),
        state_directory(&app)?
            .join("sandbox")
            .to_string_lossy()
            .into_owned(),
        "--cancel-file".to_string(),
        cancel_file.to_string_lossy().into_owned(),
    ];
    let result = start_cli_operation(
        &app,
        &manager,
        &engine_path,
        &python_executable,
        "sandbox_run",
        std::mem::take(&mut args),
        Vec::new(),
        Some(cancel_file),
    );
    if result.is_err() {
        let _ = fs::remove_file(safe_source);
    }
    result
}

#[tauri::command]
fn get_operation(
    operation_id: String,
    manager: State<'_, OperationManager>,
) -> Result<OperationSnapshot, String> {
    let operations = manager
        .operations
        .lock()
        .map_err(|_| "Operation manager is unavailable.".to_string())?;
    let operation = operations
        .get(&operation_id)
        .ok_or_else(|| "Operation was not found or is no longer available.".to_string())?;
    let snapshot = operation
        .snapshot
        .lock()
        .map_err(|_| "Operation status is unavailable.".to_string())?
        .clone();
    Ok(snapshot)
}

#[tauri::command]
fn cancel_operation(
    operation_id: String,
    manager: State<'_, OperationManager>,
) -> Result<OperationSnapshot, String> {
    let operations = manager
        .operations
        .lock()
        .map_err(|_| "Operation manager is unavailable.".to_string())?;
    let operation = operations
        .get(&operation_id)
        .ok_or_else(|| "Operation was not found or is no longer available.".to_string())?;
    operation.cancelled.store(true, Ordering::Relaxed);
    if let Some(cancel_file) = operation.cancel_file.as_ref() {
        if let Some(parent) = cancel_file.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let _ = fs::write(cancel_file, b"cancel");
    } else if let Ok(mut child_slot) = operation.child.lock() {
        if let Some(child) = child_slot.as_mut() {
            let _ = child.kill();
        }
    }
    let mut snapshot = operation
        .snapshot
        .lock()
        .map_err(|_| "Operation status is unavailable.".to_string())?;
    snapshot.status = "cancelling".to_string();
    snapshot.message = "Cancellation requested.".to_string();
    Ok(snapshot.clone())
}

#[tauri::command]
fn list_runs(app: AppHandle, engine_path: String) -> Result<Vec<Value>, String> {
    let _root = validate_engine_path(&app, &engine_path)?;
    let directory = report_directory(&app)?;
    if !directory.exists() {
        return Ok(Vec::new());
    }
    let mut reports = Vec::new();
    for entry in
        fs::read_dir(&directory).map_err(|error| format!("Cannot read run history: {error}"))?
    {
        let entry = entry.map_err(|error| format!("Cannot inspect run report: {error}"))?;
        let report_path = entry.path();
        if report_path
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name.starts_with("team-") || name.starts_with("repo-team-"))
        {
            continue;
        }
        if report_path.extension().and_then(|value| value.to_str()) != Some("json") {
            continue;
        }
        let content = fs::read_to_string(&report_path)
            .map_err(|error| format!("Cannot read {}: {error}", report_path.display()))?;
        if let Ok(report) = serde_json::from_str::<Value>(&content) {
            reports.push(report);
        }
    }
    reports.sort_by(|left, right| {
        right
            .get("created_at")
            .and_then(Value::as_str)
            .cmp(&left.get("created_at").and_then(Value::as_str))
    });
    Ok(reports)
}

#[tauri::command]
fn list_team_runs(app: AppHandle, engine_path: String) -> Result<Vec<Value>, String> {
    let _root = validate_engine_path(&app, &engine_path)?;
    let directory = report_directory(&app)?;
    if !directory.exists() {
        return Ok(Vec::new());
    }
    let mut reports = Vec::new();
    for entry in
        fs::read_dir(&directory).map_err(|error| format!("Cannot read team history: {error}"))?
    {
        let entry = entry.map_err(|error| format!("Cannot inspect team report: {error}"))?;
        let path = entry.path();
        if path
            .file_name()
            .and_then(|name| name.to_str())
            .is_none_or(|name| !(name.starts_with("team-") || name.starts_with("repo-team-")))
            || path.extension().and_then(|value| value.to_str()) != Some("json")
        {
            continue;
        }
        let content = fs::read_to_string(&path)
            .map_err(|error| format!("Cannot read team report: {error}"))?;
        if let Ok(report) = serde_json::from_str::<Value>(&content) {
            reports.push(report);
        }
    }
    reports.sort_by(|left, right| {
        right
            .get("created_at")
            .and_then(Value::as_str)
            .cmp(&left.get("created_at").and_then(Value::as_str))
    });
    Ok(reports)
}

#[tauri::command]
fn get_run_report(app: AppHandle, engine_path: String, run_id: String) -> Result<Value, String> {
    if run_id.is_empty()
        || !run_id
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || character == '-')
    {
        return Err("Invalid run identifier.".to_string());
    }
    let _root = validate_engine_path(&app, &engine_path)?;
    let report_path = report_directory(&app)?.join(format!("{run_id}.json"));
    let canonical = report_path
        .canonicalize()
        .map_err(|_| "Run report was not found.".to_string())?;
    if !canonical.starts_with(report_directory(&app)?) {
        return Err("Run report path is outside the engine artifacts directory.".to_string());
    }
    let content = fs::read_to_string(&canonical)
        .map_err(|error| format!("Cannot read run report: {error}"))?;
    serde_json::from_str(&content).map_err(|error| format!("Run report JSON is invalid: {error}"))
}

#[tauri::command]
fn benchmark_review_state(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    reviewer: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if reviewer.trim().is_empty() {
        return Err("Reviewer identity is required.".to_string());
    }
    let args = vec![
        "memory".to_string(),
        "benchmark-review-state".to_string(),
        "--dataset".to_string(),
        "benchmarks/memory_retrieval_kaldrax_v1.json".to_string(),
        "--reviewer".to_string(),
        reviewer,
        "--session".to_string(),
        state_directory(&app)?.join("benchmark-reviews/memory_retrieval_kaldrax_v1.review.json").to_string_lossy().into_owned(),
        "--export-dir".to_string(),
        state_directory(&app)?.join("benchmark-exports").to_string_lossy().into_owned(),
        "--version".to_string(),
        "1.0.0".to_string(),
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn benchmark_review_update(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    reviewer: String,
    action: String,
    query_id: Option<String>,
    decision: Option<String>,
    memory_ids: Option<Vec<String>>,
    note: Option<String>,
    approval: Option<String>,
    privacy_confirmation: Option<String>,
    confirm_provider_data_egress: bool,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if reviewer.trim().is_empty() {
        return Err("Reviewer identity is required.".to_string());
    }
    if !["query", "dataset-approval", "privacy-approval", "auto-approve-proposals", "model-review"].contains(&action.as_str()) {
        return Err("Unsupported benchmark review action.".to_string());
    }
    let is_model_review = action == "model-review";
    if is_model_review && !confirm_provider_data_egress {
        return Err("Model review requires explicit confirmation that benchmark content will be sent to the configured provider.".to_string());
    }
    let mut args = vec![
        "memory".to_string(),
        "benchmark-review-update".to_string(),
        "--dataset".to_string(),
        "benchmarks/memory_retrieval_kaldrax_v1.json".to_string(),
        "--reviewer".to_string(),
        reviewer,
        "--session".to_string(),
        state_directory(&app)?.join("benchmark-reviews/memory_retrieval_kaldrax_v1.review.json").to_string_lossy().into_owned(),
        "--export-dir".to_string(),
        state_directory(&app)?.join("benchmark-exports").to_string_lossy().into_owned(),
        "--version".to_string(),
        "1.0.0".to_string(),
        "--action".to_string(),
        action,
    ];
    if let Some(value) = query_id.filter(|value| !value.trim().is_empty()) {
        args.extend(["--query-id".to_string(), value]);
    }
    if let Some(value) = decision {
        args.extend(["--decision".to_string(), value]);
    }
    if let Some(values) = memory_ids {
        for value in values {
            if value.trim().is_empty() {
                return Err("Memory IDs must not be empty.".to_string());
            }
            args.extend(["--memory-id".to_string(), value]);
        }
    }
    if let Some(value) = note {
        args.extend(["--note".to_string(), value]);
    }
    if let Some(value) = approval {
        args.extend(["--approval".to_string(), value]);
    }
    if let Some(value) = privacy_confirmation {
        args.extend(["--privacy-confirmation".to_string(), value]);
    }
    if is_model_review && confirm_provider_data_egress {
        args.push("--confirm-provider-data-egress".to_string());
    }
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn quality_review_state(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    reviewer: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if reviewer.trim().is_empty() {
        return Err("Reviewer identity is required.".to_string());
    }
    let args = vec![
        "memory".to_string(),
        "quality-review-state".to_string(),
        "--contradiction-dataset".to_string(),
        "benchmarks/memory_contradictions_v1.json".to_string(),
        "--extraction-dataset".to_string(),
        "benchmarks/memory_extraction_v1.json".to_string(),
        "--reviewer".to_string(),
        reviewer,
        "--session".to_string(),
        state_directory(&app)?.join("memory-quality-review.desktop.session.json").to_string_lossy().into_owned(),
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn quality_review_update(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    reviewer: String,
    action: String,
    kind: String,
    case_id: Option<String>,
    decision: Option<String>,
    expected_conflict: Option<bool>,
    expected_claims: Option<Value>,
    note: Option<String>,
    confirmation: Option<String>,
    approval: Option<String>,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if reviewer.trim().is_empty() {
        return Err("Reviewer identity is required.".to_string());
    }
    if !["case", "dataset-approval"].contains(&action.as_str()) {
        return Err("Unsupported quality review action.".to_string());
    }
    if !["contradiction", "extraction"].contains(&kind.as_str()) {
        return Err("Unsupported quality review dataset.".to_string());
    }
    let mut args = vec![
        "memory".to_string(),
        "quality-review-update".to_string(),
        "--contradiction-dataset".to_string(),
        "benchmarks/memory_contradictions_v1.json".to_string(),
        "--extraction-dataset".to_string(),
        "benchmarks/memory_extraction_v1.json".to_string(),
        "--reviewer".to_string(),
        reviewer,
        "--session".to_string(),
        state_directory(&app)?.join("memory-quality-review.desktop.session.json").to_string_lossy().into_owned(),
        "--export-dir".to_string(),
        state_directory(&app)?.join("memory-quality-exports").to_string_lossy().into_owned(),
        "--action".to_string(),
        action,
        "--kind".to_string(),
        kind,
    ];
    if let Some(value) = case_id.filter(|value| !value.trim().is_empty()) {
        args.extend(["--case-id".to_string(), value]);
    }
    if let Some(value) = decision {
        args.extend(["--decision".to_string(), value]);
    }
    if let Some(value) = expected_conflict {
        args.extend([
            "--expected-conflict".to_string(),
            value.to_string(),
        ]);
    }
    if let Some(value) = expected_claims {
        let serialized = serde_json::to_string(&value)
            .map_err(|error| format!("Cannot serialize reviewed extraction labels: {error}"))?;
        args.extend(["--expected-claims-json".to_string(), serialized]);
    }
    if let Some(value) = note {
        args.extend(["--note".to_string(), value]);
    }
    if let Some(value) = confirmation {
        args.extend(["--confirmation".to_string(), value]);
    }
    if let Some(value) = approval {
        args.extend(["--approval".to_string(), value]);
    }
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn memory_search(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    project_id: String,
    query: String,
    limit: u8,
    agent_id: Option<String>,
    include_pending: bool,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if project_id.trim().is_empty() || query.trim().is_empty() || !(1..=50).contains(&limit) {
        return Err("Project ID and query are required; limit must be 1–50.".to_string());
    }
    let mut args = vec![
        "memory".to_string(),
        "search".to_string(),
        "--project".to_string(),
        project_id,
        "--query".to_string(),
        query,
        "--limit".to_string(),
        limit.to_string(),
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
    ];
    if let Some(agent) = agent_id.filter(|value| !value.trim().is_empty()) {
        args.extend(["--agent".to_string(), agent]);
    }
    if include_pending {
        args.push("--include-pending".to_string());
    }
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn memory_conflicts(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    project_id: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if project_id.trim().is_empty() {
        return Err("Project ID is required.".to_string());
    }
    let args = vec![
        "memory".to_string(),
        "conflicts".to_string(),
        "--project".to_string(),
        project_id,
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn memory_review(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    memory_id: String,
    decision: String,
    reviewer: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if memory_id.trim().is_empty() || !["approve", "reject"].contains(&decision.as_str()) {
        return Err("A memory ID and approve/reject decision are required.".to_string());
    }
    let args = vec![
        "memory".to_string(),
        "review".to_string(),
        "--id".to_string(),
        memory_id,
        "--decision".to_string(),
        decision,
        "--reviewer".to_string(),
        if reviewer.trim().is_empty() {
            "local-user".to_string()
        } else {
            reviewer
        },
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn memory_resolve_conflict(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    conflict_id: String,
    keep_memory_id: String,
    reviewer: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if conflict_id.trim().is_empty() || keep_memory_id.trim().is_empty() {
        return Err("Conflict ID and the memory ID to keep are required.".to_string());
    }
    let args = vec![
        "memory".to_string(),
        "resolve-conflict".to_string(),
        "--conflict-id".to_string(),
        conflict_id,
        "--keep-memory-id".to_string(),
        keep_memory_id,
        "--reviewer".to_string(),
        if reviewer.trim().is_empty() {
            "local-user".to_string()
        } else {
            reviewer
        },
        "--memory-db".to_string(),
        memory_database(&app)?.to_string_lossy().into_owned(),
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn repository_status(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    repository_path: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    let args = vec![
        "repo".to_string(),
        "status".to_string(),
        "--root".to_string(),
        repository_path,
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn repository_files(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    repository_path: String,
    directory: String,
    limit: u16,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if !(1..=500).contains(&limit) {
        return Err("File limit must be between 1 and 500.".to_string());
    }
    let args = vec![
        "repo".to_string(),
        "files".to_string(),
        "--root".to_string(),
        repository_path,
        "--directory".to_string(),
        directory,
        "--limit".to_string(),
        limit.to_string(),
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn repository_read_file(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    repository_path: String,
    relative_path: String,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    let args = vec![
        "repo".to_string(),
        "read".to_string(),
        "--root".to_string(),
        repository_path,
        "--path".to_string(),
        relative_path,
    ];
    cli_json(&app, &root, &python_executable, &args, &[])
}

#[tauri::command]
fn repository_apply_file(
    app: AppHandle,
    engine_path: String,
    python_executable: String,
    repository_path: String,
    relative_path: String,
    content: String,
    expected_sha256: Option<String>,
) -> Result<Value, String> {
    let root = validate_engine_path(&app, &engine_path)?;
    if content.len() > 1_000_000 {
        return Err("Edited file exceeds the 1 MB limit.".to_string());
    }
    let staging = state_directory(&app)?.join("desktop-edits");
    fs::create_dir_all(&staging).map_err(|error| format!("Cannot stage file edit: {error}"))?;
    let sequence = OPERATION_SEQUENCE.fetch_add(1, Ordering::Relaxed);
    let staged_file = staging.join(format!("edit-{sequence}.txt"));
    fs::write(&staged_file, content).map_err(|error| format!("Cannot stage file edit: {error}"))?;
    let mut args = vec![
        "repo".to_string(),
        "apply".to_string(),
        "--root".to_string(),
        repository_path,
        "--path".to_string(),
        relative_path,
        "--content-file".to_string(),
        staged_file.to_string_lossy().into_owned(),
    ];
    if let Some(hash) = expected_sha256 {
        args.extend(["--expected-sha256".to_string(), hash]);
    }
    let result = cli_json(&app, &root, &python_executable, &args, &[]);
    let _ = fs::remove_file(staged_file);
    result
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(OperationManager::default())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_app_info,
            verify_engine,
            start_offline_demo,
            start_task_run,
            start_team_run,
            start_sandbox_run,
            get_operation,
            cancel_operation,
            list_runs,
            list_team_runs,
            get_run_report,
            memory_search,
            memory_conflicts,
            memory_review,
            memory_resolve_conflict,
            benchmark_review_state,
            benchmark_review_update,
            quality_review_state,
            quality_review_update,
            repository_status,
            repository_files,
            repository_read_file,
            repository_apply_file
        ])
        .run(tauri::generate_context!())
        .expect("error while building KALDRAX desktop application");
}


#[cfg(test)]
mod packaged_engine_tests {
    use super::*;

    #[test]
    fn packaged_runtime_uses_bundled_executable_without_python_module_prefix() {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock is available")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("kaldrax-packaged-engine-{unique}"));
        let engine_dir = root.join("kaldrax-engine");
        fs::create_dir_all(&engine_dir).expect("test engine directory is created");
        let executable = engine_dir.join("kaldrax-engine.exe");
        fs::write(&executable, b"test executable marker").expect("test executable is written");

        assert!(is_packaged_engine_root(&root));
        let command = python_command(PACKAGED_ENGINE_SENTINEL, &root);
        assert_eq!(
            command.get_program().to_string_lossy(),
            executable.to_string_lossy()
        );
        assert_eq!(
            command.get_args().count(),
            0,
            "packaged CLI must not receive the Python -m kaldrax.cli prefix"
        );

        fs::remove_dir_all(&root).expect("test engine directory is removed");
    }
}
