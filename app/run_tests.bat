@echo off
title VN-Swing Alpha — Test Suite
cd /d "d:\portfolio\vnstock\app"
echo Running full test suite...
echo.
"C:\py\venv\Scripts\python.exe" tests\run_all.py
echo.
pause
