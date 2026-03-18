<#
.SYNOPSIS
    Start Quant Suite (ports 8501 + 8502) as hidden background processes.
    Logs are written to deployment\logs\
    Called automatically by Windows Task Scheduler at logon, or run directly.
.NOTES
    Do NOT run as Administrator — Windows Store Python aliases require a user session.
#>
$ErrorActionPreference = "SilentlyContinue"
$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ── Kill any existing Streamlit processes on 8501 / 8502 ─────────────────────
foreach ($port in 8501, 8502) {
    $hits = netstat -ano | Select-String ":$port\s"
    if ($hits) {
        $pids = $hits | ForEach-Object {
            ($_.ToString().Trim() -split '\s+')[-1]
        } | Sort-Object -Unique
        foreach ($p in $pids) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
    }
}
Start-Sleep -Seconds 1

# ── Launch apps as MINIMIZED windows ────────────────────────────────────────
# Windows Store Python (App Execution Alias) requires a desktop-session console.
# -WindowStyle Hidden breaks alias activation; Minimized keeps it working while
# staying out of the user's way (visible in taskbar but not in the foreground).
# /k keeps the window alive after the app stops so errors remain readable.
foreach ($bat in @("_run_8501_bg.bat", "_run_8502_bg.bat")) {
    $batPath = Join-Path $root $bat
    Start-Process "cmd.exe" `
        -ArgumentList "/k `"$batPath`"" `
        -WindowStyle Minimized
}

# Record startup time
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Quant Suite started by start-background.ps1" |
    Out-File (Join-Path $logDir "startup.log") -Append
