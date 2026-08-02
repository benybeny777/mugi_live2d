$ErrorActionPreference = 'Stop'

$repo = 'C:\00_PG\40_mugi_live2d'
$tool = Join-Path $repo 'tools\see-through'
$source = Join-Path $repo 'source\mugi-original.png'
$output = Join-Path $repo 'work\psd\seethrough'
$python = Join-Path $tool '.venv\Scripts\python.exe'

Push-Location $tool
try {
    & $python inference\scripts\inference_psd_quantized.py `
        --srcp $source `
        --save_dir $output `
        --save_to_psd `
        --tblr_split `
        --resolution 1024 `
        --resolution_depth 512 `
        --seed 42
    if ($LASTEXITCODE -ne 0) {
        throw "See-through failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
