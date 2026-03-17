$ErrorActionPreference = "SilentlyContinue"

Write-Host "Stopping Quant Suite..." -ForegroundColor Yellow
$stopped = 0

foreach ($port in 8501, 8502) {
    $found = netstat -ano | Select-String ":$port\s"
    if ($found) {
        $pids = $found | ForEach-Object { ($_.ToString().Trim() -split '\s+')[-1] } | Sort-Object -Unique
        foreach ($p in $pids) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "  Killed PID $p on :$port" -ForegroundColor Yellow
            $stopped++
        }
    }
}

# Fallback: kill any remaining streamlit processes by name
Get-Process -Name "streamlit" -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Write-Host "  Killed streamlit.exe PID $($_.Id)" -ForegroundColor Yellow
    $stopped++
}

if ($stopped -eq 0) { Write-Host "  Nothing was running." -ForegroundColor Gray }
else { Write-Host "Done. ($stopped process(es) stopped)" -ForegroundColor Green }
