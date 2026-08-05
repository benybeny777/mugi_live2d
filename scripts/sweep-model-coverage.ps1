# Render candidate models headlessly and measure their hair coverage defects.
# Headless is deliberate: it never touches the desktop, so a sweep can run while
# the machine is in use, and the result does not depend on window stacking.
param(
  [Parameter(Mandatory = $true)][string[]]$Candidate,
  [string]$ViewerBase = 'http://127.0.0.1:8765',
  [string]$ShotDir = 'temp/coverage-shots',
  [string]$Report = 'temp/coverage-report.json',
  [string]$Stage = '118,40,1220,510',
  [int]$Width = 1000,
  [int]$Height = 1400,
  [int]$LoadBudgetMs = 15000
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$shots = [IO.Path]::GetFullPath((Join-Path $root $ShotDir))
New-Item -ItemType Directory -Force $shots | Out-Null

$chrome = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw 'no Chromium browser found' }

$null = Invoke-WebRequest -Uri "$ViewerBase/viewer/index.html" -UseBasicParsing -TimeoutSec 10

$rendered = @()
foreach ($name in $Candidate) {
  $out = Join-Path $shots "$name.png"
  if (Test-Path $out) { Remove-Item $out -Force }
  $url = "$ViewerBase/viewer/index.html?static=1&model=/temp/$name/mugi.model3.json"
  # SwiftShader keeps WebGL working without a GPU, which headless Chrome lacks.
  # Chrome logs USB and GPU warnings to stderr; per AGENTS.md these must go to a
  # file rather than the pipeline, or PowerShell raises them as command failures.
  $chromeArgs = @(
    '--headless=new', '--disable-gpu', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
    "--virtual-time-budget=$LoadBudgetMs", "--window-size=$Width,$Height", "--screenshot=$out", $url
  )
  $stdout = Join-Path $shots "$name.chrome.out.log"
  $stderr = Join-Path $shots "$name.chrome.err.log"
  try {
    $run = Start-Process -FilePath $chrome -ArgumentList $chromeArgs -Wait -PassThru -NoNewWindow `
      -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  } catch [ArgumentException] {
    # Some managed runners inject both `Path` and `PATH`. Windows itself can
    # launch a process with that environment, but Start-Process first copies it
    # into a case-insensitive dictionary and throws on the duplicate key.
    # Direct invocation bypasses that dictionary; redirection still keeps noisy
    # Chrome GPU/USB warnings away from PowerShell's error stream.
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $chrome @chromeArgs 1> $stdout 2> $stderr
    $run = [pscustomobject]@{ ExitCode = $LASTEXITCODE }
    $ErrorActionPreference = $previousPreference
  }
  if (-not (Test-Path $out)) { throw "render failed: $name (exit $($run.ExitCode), see $stderr)" }
  Write-Host "rendered $name"
  $rendered += $out
}

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
& $python (Join-Path $root 'scripts\measure_render_coverage.py') @rendered --baseline $rendered[0] `
  --stage $Stage --report (Join-Path $root $Report)
if ($LASTEXITCODE -ne 0) { throw 'coverage measurement failed' }
