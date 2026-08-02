$ErrorActionPreference = 'Stop'

$repo = 'C:\00_PG\40_mugi_live2d'
$target = Join-Path $repo 'tools\see-through\common\modules\layerdiffuse\diffusers_kdiffusion_sdxl.py'
$old = '        device = self.text_encoder.device'
$new = @'
        # With Accelerate CPU offload the module is parked on CPU until its
        # forward hook moves it to the execution device.  Using the parked
        # module device leaves input_ids on CPU while weights are on CUDA.
        device = self._execution_device
'@

$content = Get-Content -LiteralPath $target -Raw
if ($content.Contains($new.TrimEnd())) {
    Write-Host 'See-through CPU-offload device fix is already applied.'
    exit 0
}
if (-not $content.Contains($old)) {
    throw "Expected patch target was not found: $target"
}

$content.Replace($old, $new.TrimEnd()) | Set-Content -LiteralPath $target -Encoding utf8 -NoNewline
Write-Host 'Applied See-through CPU-offload device fix.'
