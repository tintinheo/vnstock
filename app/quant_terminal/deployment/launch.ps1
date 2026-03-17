$ErrorActionPreference = "SilentlyContinue"

Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Quant Suite — Local Launcher" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan

# ── Kill any existing processes on 8501 / 8502 ────────────────────────────────
foreach ($port in 8501, 8502) {
    $found = netstat -ano | Select-String ":$port\s"
    if ($found) {
        $pids = $found | ForEach-Object { ($_.ToString().Trim() -split '\s+')[-1] } | Sort-Object -Unique
        foreach ($p in $pids) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped PID $p (was on :$port)" -ForegroundColor Yellow
        }
    }
}
Start-Sleep -Seconds 1

# ── App definitions ────────────────────────────────────────────────────────────
$apps = @(
    @{ Name = "Quant Terminal";  Dir = "D:\portfolio\vnstock\app\quant_terminal"; File = "app.py";               Port = 8501 },
    @{ Name = "Quant Profiler";  Dir = "D:\portfolio\vnstock\app";                File = "Quant_Profiler_ui.py"; Port = 8502 }
)

# ── Launch each app in its own PowerShell window ──────────────────────────────
foreach ($app in $apps) {
    $cmd = "Set-Location '$($app.Dir)'; " +
           "python3.13 -m streamlit run '$($app.File)' " +
           "--server.port $($app.Port) " +
           "--server.address 127.0.0.1 " +
           "--server.headless true " +
           "--server.fileWatcherType none"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd -WindowStyle Normal
    Write-Host "  Started : $($app.Name)  →  http://127.0.0.1:$($app.Port)" -ForegroundColor Green
}

# ── Wait for apps to initialise ───────────────────────────────────────────────
Write-Host ""
Write-Host "  Waiting 5 s for apps to initialise..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# ── Open portal in Brave (fallback to default browser) ───────────────────────
$portal = "$PSScriptRoot\index.html"
$brave  = @(
    "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe",
    "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($brave) {
    Start-Process $brave $portal
    Write-Host "  Opened portal in Brave." -ForegroundColor Cyan
} else {
    Start-Process $portal
    Write-Host "  Brave not found — opening in default browser." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Portal : $portal" -ForegroundColor White
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
