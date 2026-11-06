# TIHULU Satellite Center — Windows 10/11 x64 user-local installer.
$ErrorActionPreference = 'Stop'
$Channel = if ($env:TIHULU_CHANNEL) { $env:TIHULU_CHANNEL } else { 'feature/satellite-center-standalone-2026-11-06' }
$AppRoot = Join-Path $env:LOCALAPPDATA 'Tihulu\SatelliteCenterApp'
$Work = Join-Path $env:TEMP ('tihulu-satellite-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Work -Force | Out-Null
try {
  $Py = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { throw 'Python 3.11+ is required. Install it from python.org then rerun.' }
  $PyArgs = if ($Py -eq 'py') { @('-3') } else { @() }
  & $Py @PyArgs -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
  if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required' }
  $Archive = Join-Path $Work 'source.zip'
  $Url = "https://github.com/Tihulu/TIHULU-TEXT-CENTER/archive/refs/heads/$Channel.zip"
  Invoke-WebRequest -Uri $Url -OutFile $Archive -UseBasicParsing
  Expand-Archive -Path $Archive -DestinationPath $Work -Force
  $Source = Get-ChildItem -Path $Work -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'satellite_center\__main__.py') } | Select-Object -First 1
  if (-not $Source) { throw 'Downloaded archive has no Satellite Center. Check branch/channel.' }
  if (Test-Path $AppRoot) {
    $Backup = "$AppRoot.old.$([guid]::NewGuid().ToString('N'))"
    Move-Item -Path $AppRoot -Destination $Backup
  }
  New-Item -ItemType Directory -Path (Split-Path $AppRoot -Parent) -Force | Out-Null
  Copy-Item -Path $Source.FullName -Destination $AppRoot -Recurse
  & $Py @PyArgs -m venv (Join-Path $AppRoot '.venv-satellite')
  if ($LASTEXITCODE -ne 0) { throw 'Could not create Python virtual environment' }
  $Python = Join-Path $AppRoot '.venv-satellite\Scripts\python.exe'
  & $Python -m pip install --disable-pip-version-check 'skyfield>=1.49,<2'
  if ($LASTEXITCODE -ne 0) { throw 'Skyfield dependency installation failed' }
  $Launcher = Join-Path $AppRoot 'TIHULU-Satellite-Center.cmd'
  @"
@echo off
cd /d "$AppRoot"
"$Python" -m satellite_center serve --port 8791 --open-browser
"@ | Set-Content -Path $Launcher -Encoding Ascii
  $Menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\TIHULU Satellite Center.lnk'
  $Shell = New-Object -ComObject WScript.Shell
  $Shortcut = $Shell.CreateShortcut($Menu)
  $Shortcut.TargetPath = $Launcher
  $Shortcut.WorkingDirectory = $AppRoot
  $Shortcut.Description = 'Local receive-only satellite dashboard'
  $Shortcut.Save()
  Write-Host "Installed. Open 'TIHULU Satellite Center' from the Start Menu."
  Write-Host "Local dashboard after launching: http://127.0.0.1:8791/"
  Write-Host 'Windows RTL-SDR utilities must be installed separately and made available on PATH.'
  Write-Host 'RTL2832U hardware may require a WinUSB driver (Zadig); nothing is modified automatically.'
  Write-Host 'No scheduled task, RF capture, or network listener was silently enabled.'
} finally {
  Remove-Item -Recurse -Force -Path $Work -ErrorAction SilentlyContinue
}
