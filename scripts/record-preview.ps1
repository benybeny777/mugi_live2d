# Record the README preview from the viewer demo mode.
# Opens a frameless browser window, captures only its client area, and writes
# mp4 and gif. Defaults match the existing media: 768x600 / 640x500 / 9fps.
param(
  [string]$Url = 'http://127.0.0.1:8765/viewer/index.html?demo=1',
  [string]$OutDir = 'docs/media',
  [string]$Name = 'mugi-cubism-preview',
  [int]$Seconds = 7,
  [int]$Width = 768,
  [int]$Height = 600,
  [int]$GifWidth = 640,
  [int]$GifHeight = 500,
  [int]$Fps = 9,
  [int]$LoadWaitSeconds = 8
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$outDir = [IO.Path]::GetFullPath((Join-Path $root $OutDir))
New-Item -ItemType Directory -Force $outDir | Out-Null

$ffmpeg = (Get-Command ffmpeg).Source
$browser = @(
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Google\Chrome\Application\chrome.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $browser) { throw 'no Chromium browser found' }

# A recording is meaningless if the viewer server is down, so check it first.
$probe = ($Url -split '\?')[0]
$null = Invoke-WebRequest -Uri $probe -UseBasicParsing -TimeoutSec 10

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class Win {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, IntPtr pid);
  [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool attach);
  [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
  // Windows refuses SetForegroundWindow from a background process unless the
  // caller shares an input queue with the current foreground thread.
  public static bool ForceForeground(IntPtr h) {
    uint other = GetWindowThreadProcessId(GetForegroundWindow(), IntPtr.Zero);
    uint self = GetCurrentThreadId();
    AttachThreadInput(other, self, true);
    ShowWindow(h, 9);
    BringWindowToTop(h);
    bool ok = SetForegroundWindow(h);
    AttachThreadInput(other, self, false);
    return ok;
  }
}
'@ -Language CSharp

$profileDir = Join-Path $root 'temp\preview-browser-profile'
$browserArgs = @(
  "--app=$Url",
  "--user-data-dir=$profileDir",
  '--window-position=0,0',
  "--window-size=$($Width + 40),$($Height + 80)",
  '--no-first-run',
  '--no-default-browser-check',
  '--disable-features=Translate'
)
$proc = Start-Process -FilePath $browser -ArgumentList $browserArgs -PassThru
try {
  # Wait for the runtime and model to load; recording earlier captures the loader.
  Start-Sleep -Seconds $LoadWaitSeconds
  $proc.Refresh()
  $handle = $proc.MainWindowHandle
  if ($handle -eq [IntPtr]::Zero) {
    $handle = (Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($browser)) |
      Where-Object { $_.MainWindowTitle -and $_.MainWindowHandle -ne [IntPtr]::Zero } |
      Sort-Object StartTime -Descending | Select-Object -First 1).MainWindowHandle
  }
  if (-not $handle -or $handle -eq [IntPtr]::Zero) { throw 'cannot locate the browser window' }
  $null = [Win]::ForceForeground($handle)
  Start-Sleep -Seconds 2
  # gdigrab records whatever sits at these screen coordinates. Without this check a
  # window stacked on top is captured silently, which is worse than failing.
  $front = [Win]::GetForegroundWindow()
  if ($front -ne $handle) { throw "browser is not foreground (front=$front, browser=$handle)" }

  $rect = New-Object Win+RECT
  $null = [Win]::GetClientRect($handle, [ref]$rect)
  $origin = New-Object Win+POINT
  $null = [Win]::ClientToScreen($handle, [ref]$origin)
  $clientW = $rect.R - $rect.L
  $clientH = $rect.B - $rect.T
  if ($clientW -lt $Width -or $clientH -lt $Height) {
    throw "client area ${clientW}x${clientH} is smaller than the requested ${Width}x${Height}"
  }
  # Crop from the centre of the client area so no window border is captured.
  $x = $origin.X + [int](($clientW - $Width) / 2)
  $y = $origin.Y + [int](($clientH - $Height) / 2)
  Write-Host "capture region: ${Width}x${Height} at ($x,$y) client=${clientW}x${clientH}"

  $mp4 = Join-Path $outDir "$Name.mp4"
  $gif = Join-Path $outDir "$Name.gif"
  & $ffmpeg -y -loglevel error -f gdigrab -framerate $Fps -draw_mouse 0 `
    -offset_x $x -offset_y $y -video_size "${Width}x${Height}" -t $Seconds -i desktop `
    -vf format=yuv420p -c:v libx264 -preset slow -crf 20 -movflags +faststart $mp4
  if ($LASTEXITCODE -ne 0) { throw 'mp4 capture failed' }
  if ([Win]::GetForegroundWindow() -ne $handle) { throw 'browser lost foreground during capture' }

  $palette = "fps=$Fps,scale=${GifWidth}:${GifHeight}:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3"
  & $ffmpeg -y -loglevel error -i $mp4 -vf $palette -loop 0 $gif
  if ($LASTEXITCODE -ne 0) { throw 'gif conversion failed' }

  Write-Host "wrote $mp4"
  Write-Host "wrote $gif"
} finally {
  if (-not $proc.HasExited) { $proc.CloseMainWindow() | Out-Null; Start-Sleep -Seconds 2 }
  if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
}
