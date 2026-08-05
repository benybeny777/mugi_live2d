param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$DocumentTitle,
    [Parameter(Mandatory = $true)][string]$Plan,
    [Parameter(Mandatory = $true)][string]$Output
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$jdk = Join-Path $repo 'temp\jdk17\jdk-17.0.20+8\bin'
$source = Join-Path $PSScriptRoot 'cubism_bridge'
$build = Join-Path $repo 'temp\cubism-transfer-agent'
$classes = Join-Path $build 'classes'
$cubismLib = 'C:\Program Files\Live2D Cubism 5.3\app\lib'
$jsonSimple = Join-Path $cubismLib 'json-simple-1.1.jar'
$agentSource = Join-Path $source 'CubismApplyTransferAgent.java'
$agentHash = (Get-FileHash $agentSource -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$jar = Join-Path $build "cubism-transfer-agent-$agentHash.jar"
$manifest = Join-Path $build 'MANIFEST.MF'
$resolvedPlan = [IO.Path]::GetFullPath((Join-Path $repo $Plan))
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $repo $Output))
$log = "$resolvedOutput.agent.txt"

if (-not (Test-Path $resolvedPlan)) { throw "Transfer plan not found: $resolvedPlan" }
if (-not (Test-Path $jsonSimple)) { throw "Cubism json-simple library not found: $jsonSimple" }
New-Item -ItemType Directory -Force $classes | Out-Null
if (-not (Test-Path $jar)) {
@"
Agent-Class: mugi.bridge.CubismApplyTransferAgent
Can-Redefine-Classes: false
Can-Retransform-Classes: false

"@ | Set-Content -Path $manifest -Encoding ascii
    & (Join-Path $jdk 'javac.exe') -encoding UTF-8 -cp $jsonSimple -d $classes `
        (Join-Path $source 'AttachAgent.java') $agentSource
    if ($LASTEXITCODE -ne 0) { throw "javac failed with exit code $LASTEXITCODE" }
    & (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .
    if ($LASTEXITCODE -ne 0) { throw "jar failed with exit code $LASTEXITCODE" }
}

if (Test-Path $log) { Remove-Item -LiteralPath $log -Force }
$agentArgs = "$resolvedPlan|$resolvedOutput|$log|$DocumentTitle"
& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent `
    $ProcessId $jar $agentArgs
if ($LASTEXITCODE -ne 0) { throw "Cubism attach failed with exit code $LASTEXITCODE" }

$deadline = (Get-Date).AddSeconds(30)
while (-not (Test-Path $log)) {
    if ((Get-Date) -gt $deadline) { throw "Cubism did not finish within 30 seconds" }
    Start-Sleep -Milliseconds 200
}
$result = Get-Content -Path $log
if ($result[0] -ne 'status=ready') { throw ($result -join [Environment]::NewLine) }
$result | Write-Host
