# NOTE: Do NOT run as Administrator — Windows Store Python aliases require a
#       normal user session.  If apps fail, check each console window for errors.
$ErrorActionPreference = "Continue"

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

# ── Launch apps via cmd.exe ────────────────────────────────────────────────────
# cmd.exe reliably resolves Windows Store Python App Execution Aliases.
# Each runner .bat keeps its window open on error so you can read the message.
$root    = $PSScriptRoot
$runners = @(
    @{ Name = "Quant Terminal (8501)"; Script = "_run_8501.bat" },
    @{ Name = "Quant Profiler (8502)"; Script = "_run_8502.bat" }
)
foreach ($r in $runners) {
    $bat = Join-Path $root $r.Script
    Start-Process "cmd.exe" -ArgumentList "/k `"$bat`"" -WindowStyle Normal
    Write-Host "  Started : $($r.Name)" -ForegroundColor Green
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
