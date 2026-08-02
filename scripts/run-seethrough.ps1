param(
    [ValidateSet('blockswap', 'nf4')]
    [string]$Mode = 'blockswap'
)

$ErrorActionPreference = 'Stop'

$repo = 'C:\00_PG\40_mugi_live2d'
$tool = Join-Path $repo 'tools\see-through'
$source = Join-Path $repo 'source\mugi-original.png'
$output = Join-Path $repo 'work\psd\seethrough'
$python = Join-Path $tool '.venv\Scripts\python.exe'
$logDirectory = Join-Path $repo 'logs'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stdoutLog = Join-Path $logDirectory "seethrough-$timestamp.stdout.log"
$stderrLog = Join-Path $logDirectory "seethrough-$timestamp.stderr.log"
$lifecycleLog = Join-Path $logDirectory "seethrough-$timestamp.lifecycle.log"

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
"$(Get-Date -Format o) start mode=$Mode python=$python" | Set-Content -LiteralPath $lifecycleLog -Encoding utf8

Push-Location $tool
try {
    if ($Mode -eq 'blockswap') {
        $inferenceArguments = @(
            '-u',
            'inference\scripts\inference_psd_blockswap.py',
            '--srcp', $source,
            '--save_dir', $output,
            '--save_to_psd',
            '--tblr_split',
            '--resolution', '1024',
            '--resolution_depth', '512',
            '--seed', '42'
        )
    }
    else {
        $inferenceArguments = @(
            '-u',
            'inference\scripts\inference_psd_quantized.py',
            '--srcp', $source,
            '--save_dir', $output,
            '--save_to_psd',
            '--tblr_split',
            '--cpu_offload',
            '--resolution', '1024',
            '--resolution_depth', '512',
            '--seed', '42'
        )
    }
    $inferenceProcess = Start-Process `
        -FilePath $python `
        -ArgumentList $inferenceArguments `
        -WorkingDirectory $tool `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog
    $nativeExitCode = $inferenceProcess.ExitCode
    "$(Get-Date -Format o) python-exit code=$nativeExitCode" | Add-Content -LiteralPath $lifecycleLog -Encoding utf8
    if ($nativeExitCode -ne 0) {
        throw "See-through failed with exit code $nativeExitCode"
    }
}
catch {
    "$(Get-Date -Format o) exception=$($_.Exception.Message)" | Add-Content -LiteralPath $lifecycleLog -Encoding utf8
    throw
}
finally {
    Pop-Location
    "$(Get-Date -Format o) finished" | Add-Content -LiteralPath $lifecycleLog -Encoding utf8
    Write-Host "See-through stdout: $stdoutLog"
    Write-Host "See-through stderr: $stderrLog"
    Write-Host "See-through lifecycle: $lifecycleLog"
}
