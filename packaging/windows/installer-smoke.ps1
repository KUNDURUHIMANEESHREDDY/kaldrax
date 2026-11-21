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
$runs = Join-Path $smokeRoot 'runs'
$data = Join-Path $smokeRoot 'data'
$database = Join-Path $smokeRoot 'memory.sqlite3'
New-Item -ItemType Directory -Force -Path $runs, $data | Out-Null
$env:KALDRAX_DATA_DIR = $data
Push-Location $resourceRoot
try {
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
Write-Output 'INSTALLED_TAURI_RESOURCE_SMOKE_OK'
Write-Output "Verified installer: $($installer.Name)"
Write-Output "Verified bundled CLI: $($engine.FullName)"
Write-Output 'Verified: install, executable discovery, version metadata, CLI help, offline demo, SQLite persistence, isolated app-data and JSON report.'
