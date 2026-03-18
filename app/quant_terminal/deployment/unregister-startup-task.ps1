<#
.SYNOPSIS
    Remove the "QuantSuite" Task Scheduler task and stop the running apps.
#>
$taskName = "QuantSuite"

# Stop running apps first
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

# Remove task
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Task '$taskName' removed. Apps stopped." -ForegroundColor Yellow
} else {
    Write-Host "Task '$taskName' not found — nothing to remove." -ForegroundColor Gray
}
