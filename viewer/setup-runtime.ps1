[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$source = 'C:\00_PG\20_PicoAgent\ui\vendor\live2d'
$destination = Join-Path $PSScriptRoot 'vendor'
$required = @('live2dcubismcore.min.js', 'pixi.min.js', 'cubism4.min.js')

foreach ($name in $required) {
    $path = Join-Path $source $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "PicoAgentのLive2Dランタイムがありません: $path"
    }
}

New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($name in $required) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $destination $name) -Force
}

Write-Host "Live2D viewer runtime ready: $destination"
