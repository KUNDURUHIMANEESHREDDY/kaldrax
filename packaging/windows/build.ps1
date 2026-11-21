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
Write-Output "Built frozen engine: $executable"
