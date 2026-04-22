@echo off
setlocal

echo =^> Checking Python 3...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3 is required. Install it from https://www.python.org/downloads/
    echo        Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo =^> Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo =^> Installing dependencies (this may take a few minutes -- Whisper pulls in PyTorch)...
venv\Scripts\pip install --upgrade pip -q
venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo.
echo =^> Setup complete!
echo.
echo Next steps:
echo   1. Start the server manually:
echo        venv\Scripts\python server.py
echo.
echo   2. Load the extension in Chrome/Edge:
echo        - Go to chrome://extensions  (or edge://extensions)
echo        - Enable Developer mode (top right)
echo        - Click "Load unpacked" and select the "extension\" folder
echo.
echo   3. Open a YouTube video and press Shift+Y to save it
echo.
echo   To have the server start automatically at login, run (as your normal user):
echo        powershell -ExecutionPolicy Bypass -File install-autostart.ps1
echo.
pause
