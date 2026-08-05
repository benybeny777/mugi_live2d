[CmdletBinding()]
param(
    [string]$Core = 'viewer/vendor/live2dcubismcore.min.js',
    [string]$Moc = 'temp/hiyori-reference-sdk5.moc3',
    [string]$Psd = 'work/psd/hiyori/mugi-hiyori-compatible-repaired.psd',
    [string]$ReferenceTexture = 'temp/hiyori-reference.2048/texture_00.png',
    [string]$Output = 'temp/mugi-fixed-atlas.png'
)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $repository 'logs'
$tempDirectory = Join-Path $repository 'temp'
$stdout = Join-Path $logDirectory 'fixed-atlas.out.log'
$stderr = Join-Path $logDirectory 'fixed-atlas.err.log'
$projectionStdout = Join-Path $logDirectory 'fixed-atlas-projection.out.log'
$resourceLog = Join-Path $logDirectory 'fixed-atlas-resources.csv'
$exitLog = Join-Path $logDirectory 'fixed-atlas-exit.log'
$topology = Join-Path $tempDirectory 'hiyori-topology.json'
$parts = Join-Path $tempDirectory 'atlas-parts'
$report = Join-Path $tempDirectory 'fixed-atlas-report.json'

New-Item -ItemType Directory -Path $logDirectory, $tempDirectory -Force | Out-Null
Set-Content -LiteralPath $stdout -Value "start=$([DateTimeOffset]::Now.ToString('o'))" -Encoding utf8
Set-Content -LiteralPath $stderr -Value '' -Encoding utf8
Set-Content -LiteralPath $projectionStdout -Value '' -Encoding utf8
Set-Content -LiteralPath $resourceLog -Value 'timestamp,cpu_seconds,working_set_bytes,output_files,output_bytes,gpu_util_percent,gpu_memory_mib' -Encoding utf8

Push-Location $repository
try {
    & node scripts/extract_moc_topology.mjs $Core $Moc $topology 2>&1 |
        Add-Content -LiteralPath $stdout -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "topology extraction failed: $LASTEXITCODE" }

    $env:UV_CACHE_DIR = Join-Path $repository '.uv-cache'
    & uv run python -u scripts/export_atlas_source_parts.py $Psd --output $parts 2>&1 |
        Add-Content -LiteralPath $stdout -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "PSD part export failed: $LASTEXITCODE" }

    $arguments = @(
        'run', 'python', '-u', 'scripts/build_fixed_atlas.py',
        '--topology', $topology,
        '--parts', (Join-Path $parts 'manifest.json'),
        '--reference-texture', $ReferenceTexture,
        '--output', $Output,
        '--report', $report
    )
    $process = Start-Process -FilePath 'uv' -ArgumentList $arguments -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $projectionStdout -RedirectStandardError $stderr
    while (-not $process.HasExited) {
        Start-Sleep -Seconds 10
        $process.Refresh()
        $files = @(Get-ChildItem -LiteralPath $tempDirectory -File -ErrorAction SilentlyContinue)
        $gpu = & nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits 2>$null |
            Select-Object -First 1
        $gpuValues = if ($gpu) { $gpu -split ',' } else { @('', '') }
        $row = @(
            [DateTimeOffset]::Now.ToString('o'),
            [math]::Round($process.CPU, 3),
            $process.WorkingSet64,
            $files.Count,
            ($files | Measure-Object -Property Length -Sum).Sum,
            $gpuValues[0].Trim(),
            $gpuValues[1].Trim()
        ) -join ','
        Add-Content -LiteralPath $resourceLog -Value $row -Encoding utf8
    }
    $process.WaitForExit()
    $process.Refresh()
    Get-Content -LiteralPath $projectionStdout -Encoding utf8 |
        Add-Content -LiteralPath $stdout -Encoding utf8
    $exitCode = $process.ExitCode
    $reportDocument = if (Test-Path -LiteralPath $report) {
        Get-Content -Raw -LiteralPath $report -Encoding utf8 | ConvertFrom-Json
    } else {
        $null
    }
    $verifiedOutput = (Test-Path -LiteralPath $Output -PathType Leaf) -and
        $null -ne $reportDocument -and $reportDocument.triangles -gt 0
    Set-Content -LiteralPath $exitLog -Value @(
        "end=$([DateTimeOffset]::Now.ToString('o'))",
        "exit_code=$(if ($null -eq $exitCode) { 'unavailable' } else { $exitCode })",
        "verified_output=$verifiedOutput"
    ) -Encoding utf8
    if (($null -ne $exitCode -and $exitCode -ne 0) -or -not $verifiedOutput) {
        throw "atlas projection failed: exit=$exitCode verified_output=$verifiedOutput"
    }
    Get-Content -LiteralPath $stdout -Tail 20
} finally {
    Pop-Location
}
