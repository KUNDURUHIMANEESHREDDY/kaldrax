$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$installerDirectory = Join-Path $repoRoot 'desktop/src-tauri/target/release/bundle/nsis'
$installer = Get-ChildItem -LiteralPath $installerDirectory -Filter '*.exe' -File |
  Where-Object { $_.Name -notmatch 'uninstall' } |
  Select-Object -First 1
if (-not $installer) {
  throw "NSIS installer was not produced in $installerDirectory"
}

$installRoot = Join-Path $env:RUNNER_TEMP 'kaldrax-installed-smoke'
if (Test-Path -LiteralPath $installRoot) {
  Remove-Item -LiteralPath $installRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $installRoot | Out-Null

$install = Start-Process -FilePath $installer.FullName -ArgumentList @('/S', "/D=$installRoot") -Wait -PassThru
if ($install.ExitCode -ne 0) {
  throw "NSIS silent install failed with exit code $($install.ExitCode)"
}

$engine = Get-ChildItem -LiteralPath $installRoot -Filter 'kaldrax-engine.exe' -File -Recurse |
  Select-Object -First 1
if (-not $engine) {
  throw 'Installed application does not contain the bundled KALDRAX engine executable.'
}
$resourceRoot = $engine.Directory.Parent.FullName
$versionPath = Join-Path $engine.Directory.FullName 'version.txt'
if (-not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
  throw 'Installed engine version metadata was not found.'
}

$help = & $engine.FullName --help 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $help -notmatch 'KALDRAX engineering harness') {
  throw "Installed frozen CLI help check failed (exit $LASTEXITCODE): $help"
}

$smokeRoot = Join-Path $env:RUNNER_TEMP 'kaldrax-installed-runtime-smoke'
if (Test-Path -LiteralPath $smokeRoot) {
  Remove-Item -LiteralPath $smokeRoot -Recurse -Force
}
$legacyState = Join-Path $smokeRoot 'legacy-checkout/.kaldrax'
$applicationData = Join-Path $smokeRoot 'app-data'
$destinationState = Join-Path $applicationData '.kaldrax'
$legacyRuns = Join-Path $legacyState 'runs'
New-Item -ItemType Directory -Force -Path $legacyRuns, $applicationData | Out-Null
$legacyReport = Join-Path $legacyRuns 'legacy-run.json'
Set-Content -LiteralPath $legacyReport -Value '{"run_id":"legacy-run"}' -NoNewline
$env:KALDRAX_DATA_DIR = $applicationData
Push-Location $resourceRoot
try {
  $migrationOutput = & $engine.FullName storage migrate --source $legacyState --destination $destinationState 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) {
    throw "Packaged engine legacy-state migration failed (exit $LASTEXITCODE): $migrationOutput"
  }
  $migration = $migrationOutput | ConvertFrom-Json
  if ($migration.status -ne 'migrated' -or $migration.files_copied -ne 1) {
    throw "Packaged engine returned unexpected migration result: $migrationOutput"
  }
  if (-not (Test-Path -LiteralPath (Join-Path $destinationState 'runs/legacy-run.json'))) {
    throw 'Packaged engine did not copy the legacy report into application data.'
  }
  if (-not (Test-Path -LiteralPath $legacyReport)) {
    throw 'Packaged engine migration removed the legacy source report.'
  }

  $runs = Join-Path $smokeRoot 'runs'
  $data = Join-Path $smokeRoot 'data'
  $database = Join-Path $smokeRoot 'memory.sqlite3'
  New-Item -ItemType Directory -Force -Path $runs, $data | Out-Null
  $demo = & $engine.FullName demo --project installer-smoke --artifacts $runs --memory-db $database 2>&1 | Out-String
  if ($LASTEXITCODE -ne 0) {
    throw "Installed frozen offline demo failed (exit $LASTEXITCODE): $demo"
  }
} finally {
  Pop-Location
}
if (-not (Test-Path -LiteralPath $database -PathType Leaf)) {
  throw 'Installed engine did not create its isolated SQLite database.'
}
$reports = @(Get-ChildItem -LiteralPath $runs -Filter '*.json' -File)
if ($reports.Count -lt 1) {
  throw 'Installed engine did not create a JSON run report.'
}
foreach ($report in $reports) {
  Get-Content -LiteralPath $report.FullName -Raw | ConvertFrom-Json | Out-Null
}
# Launch the installed Tauri desktop and wait for its first-run engine probe.
# The probe creates <app-data>/.kaldrax/runs only after the webview calls the
# named native engine-verification and run-history commands.
$desktopAppData = Join-Path $env:APPDATA 'dev.kaldrax.desktop'
if (Test-Path -LiteralPath $desktopAppData) {
  Remove-Item -LiteralPath $desktopAppData -Recurse -Force
}
$desktopExecutable = Get-ChildItem -LiteralPath $installRoot -Filter '*.exe' -File -Recurse |
  Where-Object { $_.Name -notmatch 'kaldrax-engine|uninstall' } |
  Select-Object -First 1
if (-not $desktopExecutable) {
  throw 'Installed KALDRAX desktop executable was not found.'
}

$desktopProcess = Start-Process -FilePath $desktopExecutable.FullName -PassThru
$nativeStartupVerified = $false
try {
  $deadline = (Get-Date).AddSeconds(25)
  $nativeRunsDirectory = Join-Path $desktopAppData '.kaldrax/runs'
  while ((Get-Date) -lt $deadline) {
    $desktopProcess.Refresh()
    if ($desktopProcess.HasExited) {
      throw "Installed KALDRAX desktop exited during startup (exit $($desktopProcess.ExitCode))."
    }
    if (Test-Path -LiteralPath $nativeRunsDirectory -PathType Container) {
      $nativeStartupVerified = $true
      break
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $nativeStartupVerified) {
    throw 'Installed Tauri desktop did not complete its bundled-engine first-run probe and create app-data run history.'
  }
} finally {
  $desktopProcess.Refresh()
  if (-not $desktopProcess.HasExited) {
    Stop-Process -Id $desktopProcess.Id -Force
    Wait-Process -Id $desktopProcess.Id -Timeout 10 -ErrorAction SilentlyContinue
  }
}

Write-Output 'INSTALLED_TAURI_GUI_STARTUP_OK'
Write-Output "Verified desktop executable: $($desktopExecutable.FullName)"
Write-Output "Verified Tauri app data: $desktopAppData"

Write-Output 'INSTALLED_TAURI_RESOURCE_SMOKE_OK'
Write-Output "Verified installer: $($installer.Name)"
Write-Output "Verified bundled CLI: $($engine.FullName)"
Write-Output 'Verified: install, Tauri GUI startup, resource auto-detection, native engine health check, app-data initialization, CLI help, bundled legacy migration without system Python, source preservation, offline demo, SQLite persistence and JSON report.'
