@echo off
:: Captain Seventh Quant Terminal — Chrome Launcher
:: Double-click this file to start the app and open it in Chrome.

set APP_DIR=%~dp0
set APP_FILE=%APP_DIR%app.py
set PORT=8501
set URL=http://localhost:%PORT%

echo ============================================
echo  Captain Seventh Quant Terminal
echo ============================================
echo  Starting Streamlit on port %PORT%...
echo.

:: Launch Streamlit in background (new window)
start "Quant Terminal" cmd /k "cd /d "%APP_DIR%" && python -m streamlit run app.py --server.port %PORT% --server.headless true --browser.gatherUsageStats false"

:: Wait for Streamlit to be ready
echo Waiting for server to start...
timeout /t 4 /nobreak >nul

:: Open in Chrome (try standard install paths)
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
set CHROME_X86="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set CHROME_LOCAL="%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if exist %CHROME% (
    %CHROME% --new-window %URL%
) else if exist %CHROME_X86% (
    %CHROME_X86% --new-window %URL%
) else if exist %CHROME_LOCAL% (
    %CHROME_LOCAL% --new-window %URL%
) else (
    echo Chrome not found — opening in default browser instead.
    start %URL%
)

echo.
echo  App is running at %URL%
echo  Close the "Quant Terminal" console window to stop the server.