param(
    [int]$ProcessId = 0,
    [Parameter(Mandatory = $true)][string]$DocumentTitle,
    [Parameter(Mandatory = $true)][string]$Output,
    [string]$SourceMeshId = 'ArtMesh47',
    [string]$NewMeshId = 'ArtMeshHairUnderlay',
    [double]$Scale = 1.18,
    [double]$DrawOrderOffset = -10,
    [double]$RightExtent = 0.55
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $PSScriptRoot 'cubism_bridge'
$jdk = Join-Path $root 'temp\jdk17\jdk-17.0.20+8\bin'
$build = Join-Path $root 'temp\cubism-underlay-agent'
$classes = Join-Path $build 'classes'
$hashInput = ((Get-FileHash (Join-Path $source 'CubismDuplicateUnderlayAgent.java') -Algorithm SHA256).Hash + (Get-FileHash (Join-Path $source 'CubismDuplicateUnderlayAgentV12.java') -Algorithm SHA256).Hash)
$hashBytes = [Text.Encoding]::UTF8.GetBytes($hashInput)
$sha256 = [Security.Cryptography.SHA256]::Create()
try { $hash = ([BitConverter]::ToString($sha256.ComputeHash($hashBytes)) -replace '-', '').Substring(0,12).ToLowerInvariant() }
finally { $sha256.Dispose() }
$jar = Join-Path $build "cubism-underlay-$hash.jar"
$manifest = Join-Path $build 'MANIFEST.MF'
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $root $Output))
$log = "$resolvedOutput.agent.txt"
New-Item -ItemType Directory -Force $classes,(Split-Path -Parent $resolvedOutput) | Out-Null
if (-not (Test-Path $jar)) {
@"
Agent-Class: mugi.bridge.CubismDuplicateUnderlayAgentV12
Can-Redefine-Classes: false

"@ | Set-Content -LiteralPath $manifest -Encoding ascii
    & (Join-Path $jdk 'javac.exe') -encoding UTF-8 -d $classes (Join-Path $source 'AttachAgent.java') (Join-Path $source 'CubismDuplicateUnderlayAgent.java') (Join-Path $source 'CubismDuplicateUnderlayAgentV12.java')
    if ($LASTEXITCODE -ne 0) { throw "javac failed: $LASTEXITCODE" }
    & (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .
    if ($LASTEXITCODE -ne 0) { throw "jar failed: $LASTEXITCODE" }
}
$process = if ($ProcessId) { Get-Process -Id $ProcessId -ErrorAction Stop } else {
    Get-Process java -ErrorAction Stop | Where-Object MainWindowTitle -Like "*$DocumentTitle*" | Select-Object -First 1
}
if (-not $process) { throw "Cubism document not found: $DocumentTitle" }
if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log -Force }
$agentArgs = "$resolvedOutput|$log|$DocumentTitle|$SourceMeshId|$NewMeshId|$Scale|$DrawOrderOffset|$RightExtent"
& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent $($process.Id) $jar $agentArgs
if ($LASTEXITCODE -ne 0) { throw "Cubism attach failed: $LASTEXITCODE" }
$deadline = (Get-Date).AddSeconds(30)
while (-not (Test-Path -LiteralPath $log)) {
    if ((Get-Date) -gt $deadline) { throw "Cubism did not finish within 30 seconds" }
    Start-Sleep -Milliseconds 250
}
$content = Get-Content -LiteralPath $log -Raw
if ($content -notlike 'status=ready*') { throw $content }
Write-Host $content
