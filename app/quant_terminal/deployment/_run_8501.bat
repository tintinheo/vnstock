@echo off
title Quant Terminal  :8501
cd /d "D:\portfolio\vnstock\app\quant_terminal"
echo ================================================
echo  Quant Terminal   http://127.0.0.1:8501
echo ================================================
echo.
python3.13 -m streamlit run app.py ^
  --server.port 8501 ^
  --server.address 127.0.0.1 ^
  --server.headless true ^
  --server.fileWatcherType none
echo.
echo [STOPPED]  App exited or failed to start.
echo            Check error above, then press any key to close.
pause >nul
