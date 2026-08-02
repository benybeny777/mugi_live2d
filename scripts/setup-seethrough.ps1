$ErrorActionPreference = 'Stop'

$repo = 'C:\00_PG\40_mugi_live2d'
$tool = Join-Path $repo 'tools\see-through'
$env:UV_CACHE_DIR = Join-Path $repo '.uv-cache'

git -C $repo submodule update --init --recursive
Push-Location $tool
try {
    uv venv .venv --python 3.12
    uv pip install --python .venv\Scripts\python.exe `
        torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 `
        --index-url https://download.pytorch.org/whl/cu128
    uv pip install --python .venv\Scripts\python.exe `
        -r requirements.txt -r requirements-inference-bnb.txt
}
finally {
    Pop-Location
}
