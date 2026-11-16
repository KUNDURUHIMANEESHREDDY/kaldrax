const { chromium } = require("playwright-core");
const fs = require("node:fs");

(async () => {
  const report = JSON.parse(fs.readFileSync(
    "C:/Users/himan/Projects/kaldrax/.kaldrax/ui-smoke-runs/956bd054-9b77-4078-b347-a35f1f6a35d5.json",
    "utf8"
  ));
  const root = "C:/Users/himan/Projects/kaldrax";
  const initialMemory = {
    id: "mem-pending-1", type: "semantic", status: "pending", confidence: 0.72,
    score: 0.81, lexical_score: 0.8, semantic_score: null, freshness_score: 1,
    retrieval_method: "lexical", summary: "Use bounded execution for changes",
    content: "Decision: use bounded execution for repository changes.",
    source_run_id: report.run_id, source_event_sequences: [2, 4],
    agent_id: "team:builder", tags: ["decision"], metadata: {}
  };
  const teamReport = {
    run_id: "team-ui-1", project_id: "kaldrax-core", objective: "Implement a safe feature",
    status: "passed", cycles: 1, plan: "1. Inspect.\n2. Implement.\n3. Verify.",
    final_output: "Implementation complete.",
    evaluation: { passed: true, satisfied: ["tests pass"], missing: [], evaluator: "independent-judge", evidence: [] },
    cycle_results: [{ cycle: 1, reviewer_approved: true, reviewer_findings: [], evaluation_passed: true, missing_criteria: [] }],
    trace: [
      { sequence: 1, agent_id: "team:planner", role: "planner", cycle: 0, output_excerpt: "Plan", timestamp: new Date().toISOString() },
      { sequence: 2, agent_id: "team:builder", role: "builder", cycle: 1, output_excerpt: "Implementation", timestamp: new Date().toISOString() },
      { sequence: 3, agent_id: "team:reviewer", role: "reviewer", cycle: 1, output_excerpt: "Approved", timestamp: new Date().toISOString() }
    ],
    events: ["team_run_passed"], budget: {}, created_at: new Date().toISOString()
  };
  const browser = await chromium.launch({
    headless: true,
    executablePath: "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    args: ["--no-sandbox", "--disable-gpu"]
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("dialog", dialog => dialog.accept());

  await page.addInitScript(({ report, root, initialMemory, teamReport }) => {
    localStorage.setItem("kaldrax.desktop.settings.v2", JSON.stringify({
      enginePath: root, pythonExecutable: "python", projectId: "kaldrax-core",
      executorModel: "builder", evaluatorModel: "judge", plannerModel: "planner",
      reviewerModel: "reviewer", baseUrl: "", repositoryPath: root
    }));
    const state = { reviewed: false, resolved: false, applied: false, readContent: "print('before')\n", op: null };
    const running = (kind) => ({
      operationId: "op-ui-1", kind, status: "running", message: "Running",
      progress: [{ event_type: "iteration_started", message: "Iteration started.", sequence: 1 }],
      result: null, error: null, startedAt: String(Math.floor(Date.now() / 1000)), finishedAt: null, exitCode: null
    });
    const teamDone = {
      operationId: "op-ui-1", kind: "team_run", status: "completed", message: "Completed",
      progress: [{ event_type: "team_run_passed", message: "All roles passed.", sequence: 1 }],
      result: teamReport, error: null, startedAt: String(Math.floor(Date.now() / 1000)),
      finishedAt: String(Math.floor(Date.now() / 1000)), exitCode: 0
    };
    window.__qaState = state;
    window.__TAURI_INTERNALS__ = {
      invoke: async (command, args = {}) => {
        switch (command) {
          case "get_app_info":
            return { app: "KALDRAX", version: "0.1.0", platform: "windows", arch: "x86_64" };
          case "verify_engine":
            return { connected: true, enginePath: root, pythonExecutable: "python", engineVersion: "0.5.0" };
          case "list_runs": return [report];
          case "list_team_runs": return [teamReport];
          case "memory_search": return [initialMemory];
          case "memory_conflicts": return [{
            id: "conflict-1", left_memory_id: "mem-left", right_memory_id: "mem-right",
            reason: "Conflicting repository policy", status: "open", created_at: new Date().toISOString()
          }];
          case "memory_review":
            state.reviewed = true;
            return { id: args.memoryId, status: args.decision === "approve" ? "active" : "rejected" };
          case "memory_resolve_conflict":
            state.resolved = true;
            return { id: args.conflictId, status: "resolved", resolution: "kept=" + args.keepMemoryId };
          case "repository_status":
            return { root, branch: "main", head: "1b50f30", clean: false, status: "## main", changes: [{ code: " M", path: "src/main.py" }] };
          case "repository_files":
            return [{ path: "src/main.py", size: state.readContent.length }];
          case "repository_read_file":
            return { path: "src/main.py", content: state.readContent, sha256: "a".repeat(64), size: state.readContent.length };
          case "repository_apply_file":
            state.applied = true;
            state.readContent = args.content;
            return { path: args.relativePath, created: false, old_sha256: args.expectedSha256, new_sha256: "b".repeat(64), backup_path: root + "/.kaldrax/backups/main.py.bak", diff: "-before\n+after", size: args.content.length };
          case "start_team_run":
            state.op = running("team_run");
            return state.op;
          case "start_sandbox_run":
            state.op = running("sandbox_run");
            return state.op;
          case "get_operation":
            if (state.op?.kind === "team_run") return teamDone;
            if (state.op?.kind === "sandbox_run") return {
              ...state.op, status: "completed", message: "Sandbox completed.",
              result: { exit_code: 0, stdout: "sandbox output", stderr: "", duration_ms: 51,
                timed_out: false, cancelled: false, output_truncated: false, container_image: "python:3.13-slim" },
              finishedAt: String(Math.floor(Date.now() / 1000)), exitCode: 0
            };
            return state.op;
          case "cancel_operation":
            state.op = { ...state.op, status: "cancelled", message: "Operation cancelled." };
            return state.op;
          case "start_offline_demo":
            state.op = running("offline_demo"); return state.op;
          case "start_task_run":
            state.op = running("task_run"); return state.op;
          default:
            if (String(command).toLowerCase().includes("dialog") || String(command).includes("plugin:dialog")) {
              return root + "/candidate.py";
            }
            throw new Error("Unexpected Tauri IPC command: " + command);
        }
      }
    };
  }, { report, root, initialMemory, teamReport });

  await page.goto("http://127.0.0.1:1420/#/", { waitUntil: "networkidle" });
  await page.getByText("Python engine connected").waitFor();
  await page.screenshot({ path: "C:/Users/himan/Downloads/New folder (45)/qa2-overview.png" });

  await page.getByRole("link", { name: "Memory" }).click();
  await page.getByText("Use bounded execution for changes").waitFor();
  await page.getByRole("button", { name: "Approve memory" }).click();
  await page.getByText(/Memory approve action completed/).waitFor();
  await page.getByRole("tab", { name: /Contradictions/ }).click();
  await page.getByText("Conflicting repository policy").waitFor();
  await page.getByRole("button", { name: "Keep left" }).click();
  await page.getByText(/Conflict resolved/).waitFor();
  await page.screenshot({ path: "C:/Users/himan/Downloads/New folder (45)/qa2-memory.png" });

  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Provider API key").fill("qa-session-key");
  await page.getByRole("link", { name: "Team runs" }).click();
  await page.getByLabel("Objective").fill("Implement a safe feature");
  await page.getByLabel("Acceptance criteria").fill("Tests pass\nReview approves");
  await page.getByRole("button", { name: "Start team run" }).click();
  await page.getByText("Implementation").waitFor();
  await page.getByText("Independent evaluation", { exact: true }).waitFor();
  await page.screenshot({ path: "C:/Users/himan/Downloads/New folder (45)/qa2-team.png" });

  await page.getByRole("link", { name: "Sandbox" }).click();
  await page.getByRole("button", { name: "Browse" }).click();
  await page.waitForTimeout(250);
  if (!await page.locator(".kw-file-picker input").inputValue()) {
    throw new Error("Sandbox file picker did not populate the file path");
  }
  await page.getByRole("button", { name: "Run in sandbox" }).click();
  await page.getByText("sandbox output").waitFor();
  await page.screenshot({ path: "C:/Users/himan/Downloads/New folder (45)/qa2-sandbox.png" });

  await page.getByRole("link", { name: "Repository" }).click();
  await page.getByText("src/main.py").first().waitFor();
  await page.locator(".kw-file-list button").click();
  await page.getByLabel("Repository file content").fill("print('after')\n");
  await page.getByRole("button", { name: "Apply file edit" }).click();
  await page.getByText(/Applied src\/main.py/).waitFor();
  await page.screenshot({ path: "C:/Users/himan/Downloads/New folder (45)/qa2-repository.png" });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("http://127.0.0.1:1420/#/memory", { waitUntil: "networkidle" });
  await page.waitForTimeout(200);
  const mobile = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth }));
  await page.screenshot({ path: "C:/Users/himan/Downloads/New folder (45)/qa2-mobile.png" });

  const results = await page.evaluate(() => ({
    memoryApproval: window.__qaState.reviewed,
    memoryConflictResolution: window.__qaState.resolved,
    repositoryApply: window.__qaState.applied
  }));
  Object.assign(results, { mobile, pageErrors: errors });
  console.log(JSON.stringify(results, null, 2));
  await browser.close();
  if (!results.memoryApproval || !results.memoryConflictResolution || !results.repositoryApply || mobile.scrollWidth > mobile.viewport || errors.length) process.exitCode = 1;
})();
