$ErrorActionPreference = 'Stop'

$repo = 'C:\00_PG\40_mugi_live2d'
$target = Join-Path $repo 'tools\see-through\common\modules\layerdiffuse\diffusers_kdiffusion_sdxl.py'
$blockswapDevice = '        device = self.text_encoder.device'
$cpuOffloadPatch = @'
        # With Accelerate CPU offload the module is parked on CPU until its
        # forward hook moves it to the execution device.  Using the parked
        # module device leaves input_ids on CPU while weights are on CUDA.
        device = self._execution_device
'@

$content = Get-Content -LiteralPath $target -Raw
if ($content.Contains($blockswapDevice)) {
    Write-Host 'See-through is already in the blockswap-compatible device state.'
    exit 0
}
if (-not $content.Contains($cpuOffloadPatch.TrimEnd())) {
    throw "Expected patch target was not found: $target"
}

$content.Replace($cpuOffloadPatch.TrimEnd(), $blockswapDevice) | Set-Content -LiteralPath $target -Encoding utf8 -NoNewline
Write-Host 'Restored See-through text embeddings to the blockswap-compatible CPU device.'
