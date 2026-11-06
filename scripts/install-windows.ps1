# TIHULU TEXT CENTER Windows x64: user-local, no driver changes.
param([string]$Branch = "main")
$ErrorActionPreference = "Stop"
if ($env:TIHULU_TEXT_BRANCH) { $Branch = $env:TIHULU_TEXT_BRANCH }
if ($Branch -notmatch '^[A-Za-z0-9][A-Za-z0-9./_-]*$') { throw "Invalid Git branch" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git for Windows is required" }
$py = Get-Command py -ErrorAction SilentlyContinue
$pythonCmd = "python"
$pythonArgs = @()
if ($py) {
    $pythonCmd = "py"
    $pythonArgs = @("-3")
} elseif (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ is required"
}
$version = & $pythonCmd @pythonArgs -c "import sys; print(int(sys.version_info >= (3,11)))"
if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne "1") { throw "Python 3.11+ is required" }
$homeDir = Join-Path $env:LOCALAPPDATA "TIHULU-Text-Center"
$dest = Join-Path $homeDir "source"
New-Item -ItemType Directory -Force -Path $homeDir | Out-Null
$repo = "https://github.com/Tihulu/TIHULU-TEXT-CENTER.git"
if (Test-Path $dest) {
    if (-not (Test-Path (Join-Path $dest ".git"))) { throw "Unrelated directory exists" }
    $remote = (& git -C $dest remote get-url origin).Trim()
    if ($remote -ne $repo) { throw "Unrecognized Git origin; refusing update" }
    $changes = (& git -C $dest status --porcelain | Out-String).Trim()
    if ($changes.Length -gt 0) { throw "Local Git changes; update manually" }
    $current = (& git -C $dest symbolic-ref --short HEAD).Trim()
    if ($current -ne $Branch) { throw "Checkout branch mismatch: $current" }
    & git -C $dest fetch origin $Branch
    if ($LASTEXITCODE -ne 0) { throw "Git fetch failed" }
    & git -C $dest merge --ff-only FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "Fast-forward refused; existing files retained" }
} else {
    & git clone --branch $Branch --single-branch $repo $dest
    if ($LASTEXITCODE -ne 0) { throw "Clone failed" }
}
$launcher = Join-Path $homeDir "Start-Text-Center.cmd"
$managed = "@rem TIHULU TEXT CENTER MANAGED LAUNCHER"
if (Test-Path $launcher) {
    if (-not ((Get-Content $launcher -TotalCount 2) -join " ").Contains($managed)) {
        throw "Unrelated launcher exists; will not overwrite"
    }
}
$run = if ($pythonCmd -eq "py") { "py -3" } else { "python" }
$lines = @("@echo off", $managed, "cd /d ""$dest""", "$run -m textcenter desktop")
[System.IO.File]::WriteAllText($launcher, ($lines -join [Environment]::NewLine) + [Environment]::NewLine)
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
$shortcutPath = Join-Path $startMenu "TIHULU Text Center.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $dest
$shortcut.Description = "TIHULU Text Center — local radio and TV"
$shortcut.Save()
Write-Host "TIHULU Text Center registered in Start Menu. No radio driver or AI model installed."
Write-Host "Source: $dest"
Write-Host "To run: $launcher"
