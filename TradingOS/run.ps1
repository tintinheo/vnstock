# TradingOS Alpha — launcher
# Usage: .\run.ps1
Set-Location $PSScriptRoot
$env:PYTHONPATH = "$PSScriptRoot\src"
& C:\py\venv\Scripts\streamlit run src/tradingos/ui/app.py --server.port 8501 --server.headless false
