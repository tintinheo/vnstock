<#
.SYNOPSIS
    Register "QuantSuite" Windows Task Scheduler task — auto-starts both
    Streamlit apps at user logon (hidden, no console windows).

.USAGE
    Right-click in File Explorer → "Run with PowerShell"
    — or —
    powershell -ExecutionPolicy Bypass -File register-startup-task.ps1
#>

$taskName  = "QuantSuite"
$scriptPath = Join-Path $PSScriptRoot "start-background.ps1"

# ── Action: run the hidden launcher ──────────────────────────────────────────
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -NonInteractive -File `"$scriptPath`""

# ── Trigger: at current user logon ───────────────────────────────────────────
$trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME

# ── Settings: no time limit, restart up to 3× if it fails ───────────────────
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([timespan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

# ── Register (overwrites if already exists) ───────────────────────────────────
Register-ScheduledTask `
    -TaskName $taskName `
    -Action   $action `
    -Trigger  $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Task '$taskName' registered successfully." -ForegroundColor Green
Write-Host "  → Quant Suite will auto-start at every logon." -ForegroundColor Green
Write-Host ""
Write-Host "  Starting now..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 6
Write-Host "  Done. Open http://127.0.0.1:8501 or :8502" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To remove: run unregister-startup-task.ps1" -ForegroundColor Gray
