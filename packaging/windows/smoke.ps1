param(
  [string]$DistributionDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) '../../build/windows/kaldrax-engine')
)
$ErrorActionPreference = 'Stop'
$executable = Join-Path $DistributionDirectory 'kaldrax-engine.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
  throw "Frozen engine executable not found: $executable"
}

$help = & $executable --help 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $help -notmatch 'KALDRAX engineering harness') {
  throw "Frozen CLI help check failed (exit $LASTEXITCODE): $help"
}

$smokeRoot = Join-Path $env:RUNNER_TEMP 'kaldrax-frozen-engine-smoke'
if (Test-Path -LiteralPath $smokeRoot) {
  Remove-Item -LiteralPath $smokeRoot -Recurse -Force
}
$runs = Join-Path $smokeRoot 'runs'
$database = Join-Path $smokeRoot 'memory.sqlite3'
New-Item -ItemType Directory -Force -Path $runs | Out-Null

$demoOutput = & $executable demo --project packaging-smoke --artifacts $runs --memory-db $database 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
  throw "Frozen offline demo failed (exit $LASTEXITCODE): $demoOutput"
}
if (-not (Test-Path -LiteralPath $database -PathType Leaf)) {
  throw 'Frozen offline demo did not create its SQLite database.'
}
$reports = @(Get-ChildItem -LiteralPath $runs -Filter '*.json' -File)
if ($reports.Count -lt 1) {
  throw 'Frozen offline demo did not create a run report.'
}
foreach ($report in $reports) {
  Get-Content -LiteralPath $report.FullName -Raw | ConvertFrom-Json | Out-Null
}

$benchmarkOutput = & $executable benchmark-evaluator --mode deterministic --min-accuracy 0.80 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
  throw "Frozen deterministic evaluator benchmark failed. This can indicate missing packaged fixture data. Output: $benchmarkOutput"
}

Write-Output 'FROZEN_ENGINE_SMOKE_OK'
Write-Output 'Verified: CLI help, offline demo, SQLite persistence, JSON run report, bundled evaluator fixture, deterministic evaluator benchmark.'
