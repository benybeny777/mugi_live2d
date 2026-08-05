param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$DocumentTitle,
    [Parameter(Mandatory = $true)][string]$Metadata,
    [Parameter(Mandatory = $true)][string]$Output
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$jdk = Join-Path $repo 'temp\jdk17\jdk-17.0.20+8\bin'
$source = Join-Path $PSScriptRoot 'cubism_bridge'
$cubismLib = 'C:\Program Files\Live2D Cubism 5.3\app\lib'
$build = Join-Path $repo 'temp\cubism-composite-hair-agent'
$classes = Join-Path $build 'classes'
$agentSource = Join-Path $source 'CubismCompositeHairAgent.java'
$hash = (Get-FileHash $agentSource -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$jar = Join-Path $build "cubism-composite-hair-agent-$hash.jar"
$manifest = Join-Path $build 'MANIFEST.MF'
$resolvedMetadata = [IO.Path]::GetFullPath((Join-Path $repo $Metadata))
$resolvedOutput = [IO.Path]::GetFullPath((Join-Path $repo $Output))
$log = "$resolvedOutput.agent.txt"
$metadataObject = [IO.File]::ReadAllText($resolvedMetadata, [Text.Encoding]::UTF8) | ConvertFrom-Json
$uv = $metadataObject.uv
$box = $metadataObject.source_bbox

New-Item -ItemType Directory -Force $classes,(Split-Path -Parent $resolvedOutput) | Out-Null
if (-not (Test-Path $jar)) {
@"
Agent-Class: mugi.bridge.CubismCompositeHairAgent
Can-Redefine-Classes: false
Can-Retransform-Classes: false

"@ | Set-Content -Path $manifest -Encoding ascii
    & (Join-Path $jdk 'javac.exe') -encoding UTF-8 -cp "$cubismLib\*" -d $classes `
        (Join-Path $source 'AttachAgent.java') $agentSource
    if ($LASTEXITCODE -ne 0) { throw "javac failed with exit code $LASTEXITCODE" }
    & (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .
    if ($LASTEXITCODE -ne 0) { throw "jar failed with exit code $LASTEXITCODE" }
}

if (Test-Path $resolvedOutput) { throw "refusing to overwrite output: $resolvedOutput" }
if (Test-Path $log) { Remove-Item -LiteralPath $log -Force }
$agentArgs = "$resolvedOutput|$log|$DocumentTitle|$($uv.left)|$($uv.right)|$($uv.top)|$($uv.bottom)|$($box[0])|$($box[1])|$($box[2])|$($box[3])"
& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent $ProcessId $jar $agentArgs
if ($LASTEXITCODE -ne 0) { throw "Cubism attach failed with exit code $LASTEXITCODE" }

$deadline = (Get-Date).AddSeconds(60)
while (-not (Test-Path $log)) {
    if ((Get-Date) -gt $deadline) { throw 'Cubism composite-hair operation timed out' }
    Start-Sleep -Milliseconds 250
}
$result = Get-Content -LiteralPath $log
if ($result[0] -ne 'status=ready') { throw ($result -join [Environment]::NewLine) }
$result | Write-Host
