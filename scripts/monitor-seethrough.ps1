param(
    [int]$ProcessId = 13508,
    [int]$IntervalSeconds = 60
)

$ErrorActionPreference = 'Continue'
$repoRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $repoRoot 'logs'
$outputDirectory = Join-Path $repoRoot 'work\psd\seethrough'
$logPath = Join-Path $logDirectory 'seethrough-monitor.csv'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
if (-not (Test-Path -LiteralPath $logPath)) {
    'timestamp,state,cpu_seconds,working_set_gb,gpu_memory_mib,gpu_utilization_percent,gpu_temperature_c,output_file_count,output_bytes' |
        Set-Content -LiteralPath $logPath -Encoding utf8
}

while ($true) {
    $timestamp = Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK'
    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    $gpu = (& nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits 2>$null) -split ',' |
        ForEach-Object { $_.Trim() }
    $files = @(Get-ChildItem -LiteralPath $outputDirectory -Recurse -File -ErrorAction SilentlyContinue)
    $outputBytes = ($files | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $outputBytes) { $outputBytes = 0 }

    if ($process) {
        $row = @(
            $timestamp, 'running', [math]::Round($process.CPU, 1),
            [math]::Round($process.WorkingSet64 / 1GB, 2),
            $gpu[0], $gpu[1], $gpu[2], $files.Count, $outputBytes
        ) -join ','
        Add-Content -LiteralPath $logPath -Value $row -Encoding utf8
        Start-Sleep -Seconds $IntervalSeconds
        continue
    }

    $row = @($timestamp, 'finished', '', '', $gpu[0], $gpu[1], $gpu[2], $files.Count, $outputBytes) -join ','
    Add-Content -LiteralPath $logPath -Value $row -Encoding utf8
    break
}
