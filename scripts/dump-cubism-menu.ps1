param([Parameter(Mandatory=$true)][int]$ProcessId,[Parameter(Mandatory=$true)][string]$DocumentTitle,[string]$Output='temp/cubism-menu.txt')
$ErrorActionPreference='Stop';$root=Split-Path -Parent $PSScriptRoot;$source=Join-Path $PSScriptRoot 'cubism_bridge';$jdk=Join-Path $root 'temp\jdk17\jdk-17.0.20+8\bin'
$classes=Join-Path $root 'temp\cubism-menu-agent\classes';$hash=(Get-FileHash (Join-Path $source 'CubismMenuDumpAgent.java') -Algorithm SHA256).Hash.Substring(0,12).ToLowerInvariant();$jar=Join-Path $root "temp\cubism-menu-agent-$hash.jar";$manifest=Join-Path $root 'temp\cubism-menu-manifest.mf';$resolved=[IO.Path]::GetFullPath((Join-Path $root $Output))
New-Item -ItemType Directory -Force $classes,(Split-Path -Parent $resolved)|Out-Null
if(-not(Test-Path $jar)){@"
Agent-Class: mugi.bridge.CubismMenuDumpAgent

"@|Set-Content $manifest -Encoding ascii;& (Join-Path $jdk 'javac.exe') -encoding UTF-8 -d $classes (Join-Path $source 'AttachAgent.java') (Join-Path $source 'CubismMenuDumpAgent.java');if($LASTEXITCODE-ne 0){throw 'javac failed'};& (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .;if($LASTEXITCODE-ne 0){throw 'jar failed'}}
& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent $ProcessId $jar "$resolved|$DocumentTitle";if($LASTEXITCODE-ne 0){throw 'attach failed'}
$deadline=(Get-Date).AddSeconds(20);while(-not(Test-Path $resolved)){if((Get-Date)-gt$deadline){throw 'timeout'};Start-Sleep -Milliseconds 250};Write-Host $resolved
