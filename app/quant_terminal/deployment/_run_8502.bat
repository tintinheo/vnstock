@echo off
title Quant Profiler  :8502
cd /d "D:\portfolio\vnstock\app"
echo ================================================
echo  Quant Profiler   http://127.0.0.1:8502
echo ================================================
echo.
python3.13 -m streamlit run Quant_Profiler_ui.py ^
  --server.port 8502 ^
  --server.address 127.0.0.1 ^
  --server.headless true ^
  --server.fileWatcherType none
echo.
echo [STOPPED]  App exited or failed to start.
echo            Check error above, then press any key to close.
pause >nul
