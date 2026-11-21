$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$distRoot = Join-Path $repoRoot 'build/windows'
$workRoot = Join-Path $repoRoot 'build/pyinstaller'
$specRoot = Join-Path $workRoot 'spec'

New-Item -ItemType Directory -Force -Path $distRoot, $workRoot, $specRoot | Out-Null
$outputDirectory = Join-Path $distRoot 'kaldrax-engine'
if (Test-Path $outputDirectory) {
  Remove-Item -LiteralPath $outputDirectory -Recurse -Force
}

Push-Location $repoRoot
try {
  python -m PyInstaller --clean --noconfirm --onedir --console `
    --name kaldrax-engine `
    --distpath $distRoot `
    --workpath $workRoot `
    --specpath $specRoot `
    --paths (Join-Path $repoRoot 'src') `
    --collect-data kaldrax `
    (Join-Path $PSScriptRoot 'entrypoint.py')
  if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}

$executable = Join-Path $outputDirectory 'kaldrax-engine.exe'
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
  throw "Frozen KALDRAX executable was not produced at $executable"
}
$manifestPath = Join-Path $repoRoot 'pyproject.toml'
$versionPath = Join-Path $outputDirectory 'version.txt'
python -c "import sys, tomllib; from pathlib import Path; version = tomllib.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version']; Path(sys.argv[2]).write_text(version, encoding='utf-8')" $manifestPath $versionPath
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $versionPath -PathType Leaf)) {
  throw 'Could not write KALDRAX engine version metadata'
}
$engineVersion = (Get-Content -LiteralPath $versionPath -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($engineVersion)) {
  throw 'KALDRAX engine version metadata is empty'
}
Write-Output "Built frozen engine $engineVersion - $executable"
