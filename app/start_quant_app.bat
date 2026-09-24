@echo off
title Quant App Terminal (port 8502)
cd /d "d:\portfolio\vnstock\app"
"C:\py\venv\Scripts\streamlit.exe" run quant_app.py --server.port 8502 --server.headless true --server.runOnSave false
