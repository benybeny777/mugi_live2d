$ErrorActionPreference = 'Stop'

$vendorRoot = Join-Path $PSScriptRoot 'vendor'
New-Item -ItemType Directory -Force $vendorRoot | Out-Null

npm install --prefix $vendorRoot --no-save --no-audit --no-fund `
  three@0.180.0 `
  '@pixiv/three-vrm@3.5.3'

Write-Host "VRM runtime ready: $vendorRoot"
