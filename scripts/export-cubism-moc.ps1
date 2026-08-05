param(
 [int]$ProcessId=0,
 [Parameter(Mandatory=$true)][string]$DocumentTitle,
 [Parameter(Mandatory=$true)][ValidateSet('sdk5','sdk4')][string]$Sdk,
 [Parameter(Mandatory=$true)][string]$Output
)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$source=Join-Path $PSScriptRoot 'cubism_bridge'
$jdk=Join-Path $root 'temp\jdk17\jdk-17.0.20+8\bin'
$cubismLib='C:\Program Files\Live2D Cubism 5.3\app\lib'
$classes=Join-Path $root 'temp\cubism-moc-export-agent\classes'
$hashInput=((Get-FileHash (Join-Path $source 'CubismMocExportAgent.java') -Algorithm SHA256).Hash+(Get-FileHash (Join-Path $source 'CubismMocExportAgentV4.java') -Algorithm SHA256).Hash)
$hashBytes=[Text.Encoding]::UTF8.GetBytes($hashInput);$sha=[Security.Cryptography.SHA256]::Create()
try{$hash=([BitConverter]::ToString($sha.ComputeHash($hashBytes))-replace'-','').Substring(0,12).ToLowerInvariant()}finally{$sha.Dispose()}
$jar=Join-Path $root "temp\cubism-moc-export-agent-$hash.jar"
$manifest=Join-Path $root 'temp\cubism-moc-export-manifest.mf'
$resolved=[IO.Path]::GetFullPath((Join-Path $root $Output))
New-Item -ItemType Directory -Force $classes,(Split-Path -Parent $resolved)|Out-Null
if(-not(Test-Path $jar)){
@"
Agent-Class: mugi.bridge.CubismMocExportAgentV4

"@|Set-Content $manifest -Encoding ascii
& (Join-Path $jdk 'javac.exe') -encoding UTF-8 -cp "$cubismLib\*" -d $classes (Join-Path $source 'AttachAgent.java') (Join-Path $source 'CubismMocExportAgent.java') (Join-Path $source 'CubismMocExportAgentV4.java')
if($LASTEXITCODE-ne 0){throw 'javac failed'}
& (Join-Path $jdk 'jar.exe') cfm $jar $manifest -C $classes .
if($LASTEXITCODE-ne 0){throw 'jar failed'}
}
$process=if($ProcessId){Get-Process -Id $ProcessId -ErrorAction Stop}else{Get-Process java|Where-Object MainWindowTitle -Like "*$DocumentTitle*"|Select-Object -First 1}
if(-not $process){throw "document not found: $DocumentTitle"}
# Every prior output must go first. Otherwise a stale MOC satisfies the wait
# below and a failed run is reported as a success.
$stale=@("$resolved","$resolved.error.txt","$resolved.done.txt")+
 (Get-ChildItem -LiteralPath (Split-Path -Parent $resolved) -Filter ((Split-Path -Leaf $resolved)+'.texture_*.png') -ErrorAction SilentlyContinue|ForEach-Object FullName)
foreach($path in $stale){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path -Force}}
& (Join-Path $jdk 'java.exe') --add-modules jdk.attach -cp $classes AttachAgent $process.Id $jar "$resolved|$DocumentTitle|$Sdk"
if($LASTEXITCODE-ne 0){throw 'attach failed'}
# The agent writes the MOC before its textures, so wait for the marker it writes
# last rather than for the MOC itself.
$deadline=(Get-Date).AddSeconds(180)
while(-not(Test-Path "$resolved.done.txt")){
 if(Test-Path "$resolved.error.txt"){throw(Get-Content "$resolved.error.txt" -Raw)}
 if((Get-Date)-gt$deadline){throw 'MOC export timeout'}
 Start-Sleep -Milliseconds 250
}
if(-not(Test-Path $resolved)){throw 'export reported completion without writing the MOC'}
Get-Content "$resolved.done.txt"
Get-Item $resolved|Select-Object FullName,Length
