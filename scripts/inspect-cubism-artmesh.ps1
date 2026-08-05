param(
    [Parameter(Mandatory = $true)][string]$DocumentTitle,
    [string]$MeshId = 'ArtMesh47',
    [string]$Output = 'temp/cubism-artmesh-reflection.txt'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $PSScriptRoot 'cubism_bridge'
$jdk = Join-Path $root 'temp\jdk17\jdk-17.0.20+8\bin'
$classes = Join-Path $root 'temp\cubism-reflection-classes'
$agentHash = (Get-FileHash (Join-Path $source 'CubismReflectionAgent.java') -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$jar = Join-Path $root "temp\cubism-reflection-agent-$agentHash.jar"
$manifest = Join-Path $root 'temp\cubism-reflection-manifest.mf'
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $root $Output))
New-Item -ItemType Directory -Force -Path $classes,(Split-Path -Parent $resolvedOutput) | Out-Null
@"
Manifest-Version: 1.0
Agent-Class: mugi.bridge.CubismReflectionAgent
Can-Redefine-Classes: false

"@ | Set-Content -LiteralPath $manifest -Encoding ascii
if (-not (Test-Path -LiteralPath $jar)) {
    & (Join-Path $jdk 'javac.exe') -encoding UTF-8 -d $classes (Join-Path $source 'AttachAgent.java') (Join-Path $source 'CubismReflectionAgent.java')
    if ($LASTEXITCODE -ne 0) { throw "javac failed: $LASTEXITCODE" }
    & (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .
    if ($LASTEXITCODE -ne 0) { throw "jar failed: $LASTEXITCODE" }
}
$process = Get-Process java -ErrorAction Stop | Where-Object MainWindowTitle -Like "*$DocumentTitle*" | Select-Object -First 1
if (-not $process) { throw "Cubism document not found: $DocumentTitle" }
& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent $($process.Id) $jar "$resolvedOutput|$DocumentTitle|$MeshId|readonly"
if ($LASTEXITCODE -ne 0) { throw "Cubism attach failed: $LASTEXITCODE" }
$deadline = (Get-Date).AddSeconds(20)
while (-not (Test-Path -LiteralPath $resolvedOutput)) {
    if ((Get-Date) -gt $deadline) { throw "Cubism did not write $resolvedOutput" }
    Start-Sleep -Milliseconds 250
}
Write-Host $resolvedOutput
