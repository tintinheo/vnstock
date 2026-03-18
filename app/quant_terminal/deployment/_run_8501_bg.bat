@echo off
:: Background runner for Quant Terminal :8501
:: No pause — designed to be called from start-background.ps1
:: Logs are handled externally by the launcher.
cd /d "D:\portfolio\vnstock\app\quant_terminal"
python3.13 -m streamlit run app.py ^
  --server.port 8501 ^
  --server.address 127.0.0.1 ^
  --server.headless true ^
  --server.fileWatcherType none
