param(
    [int]$ProcessId = 0,
    [Parameter(Mandatory = $true)][string]$DocumentTitle,
    [string]$Psd = 'work/psd/hiyori/mugi-hiyori-compatible-repaired.psd',
    [Parameter(Mandatory = $true)][string]$Output
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $PSScriptRoot 'cubism_bridge'
$jdk = Join-Path $root 'temp\jdk17\jdk-17.0.20+8\bin'
$cubismLib = 'C:\Program Files\Live2D Cubism 5.3\app\lib'
$build = Join-Path $root 'temp\cubism-psd-reimport-agent'
$classes = Join-Path $build 'classes'
$agentSource = Join-Path $source 'CubismPsdReimportAgent.java'
$hash = (Get-FileHash $agentSource -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$jar = Join-Path $build "cubism-psd-reimport-agent-$hash.jar"
$manifest = Join-Path $build 'MANIFEST.MF'
$resolvedPsd = [IO.Path]::GetFullPath((Join-Path $root $Psd))
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $root $Output))
$log = "$resolvedOutput.agent.txt"

if (-not (Test-Path -LiteralPath $resolvedPsd -PathType Leaf)) { throw "PSD not found: $resolvedPsd" }
New-Item -ItemType Directory -Force $classes, (Split-Path -Parent $resolvedOutput) | Out-Null
if (-not (Test-Path -LiteralPath $jar)) {
@"
Agent-Class: mugi.bridge.CubismPsdReimportAgent
Can-Redefine-Classes: false
Can-Retransform-Classes: false

"@ | Set-Content -LiteralPath $manifest -Encoding ascii
    & (Join-Path $jdk 'javac.exe') -encoding UTF-8 -cp "$cubismLib\*" -d $classes `
        (Join-Path $source 'AttachAgent.java') $agentSource
    if ($LASTEXITCODE -ne 0) { throw "javac failed: $LASTEXITCODE" }
    & (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .
    if ($LASTEXITCODE -ne 0) { throw "jar failed: $LASTEXITCODE" }
}

$process = if ($ProcessId) {
    Get-Process -Id $ProcessId -ErrorAction Stop
} else {
    Get-Process java -ErrorAction SilentlyContinue |
        Where-Object MainWindowTitle -Like "*$DocumentTitle*" |
        Select-Object -First 1
}
if (-not $process) { throw "Cubism document not found: $DocumentTitle" }
if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
if (Test-Path -LiteralPath $resolvedOutput) { throw "refusing to overwrite output: $resolvedOutput" }

& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent `
    $process.Id $jar "$resolvedPsd|$resolvedOutput|$log|$DocumentTitle"
if ($LASTEXITCODE -ne 0) { throw "Cubism attach failed: $LASTEXITCODE" }

$deadline = (Get-Date).AddSeconds(180)
while (-not (Test-Path -LiteralPath $log)) {
    if ((Get-Date) -gt $deadline) { throw 'Cubism PSD re-import timed out' }
    Start-Sleep -Milliseconds 250
}
$result = Get-Content -LiteralPath $log -Encoding utf8
if ($result[0] -ne 'status=ready') { throw ($result -join [Environment]::NewLine) }
$result | Write-Host
