@echo off
title Quant Profiler UI (port 8501)
cd /d "d:\portfolio\vnstock\app"
"C:\py\venv\Scripts\streamlit.exe" run Quant_Profiler_ui.py --server.port 8501 --server.headless true --server.runOnSave false
