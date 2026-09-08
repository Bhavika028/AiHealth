@echo off
title PulseSync AI Launcher
color 0A
echo ========================================================
echo         PulseSync AI - Healthcare Platform
echo ========================================================
echo.
echo [1/3] Checking environment & dependencies...

cd /d "%~dp0"

REM Activate virtualenv if present
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist ".ven\Scripts\activate.bat" (
    call .ven\Scripts\activate.bat
)

REM Verify python is working
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH or virtual environment!
    echo Please install Python 3.10+ or check your environment.
    pause
    exit /b 1
)

REM Check if all required libraries are installed
python -c "import uvicorn, fastapi, sqlalchemy, jwt, cryptography, httpx, qrcode" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing required dependencies from requirements.txt...
    pip install -r requirements.txt
)

echo [2/3] Starting PulseSync AI Server on http://127.0.0.1:8000 ...
start "PulseSync AI Server" cmd /k "title PulseSync AI Server && cd /d "%~dp0" && python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000"

echo [3/3] Waiting for server to initialize...
timeout /t 3 >nul

echo Opening PulseSync AI in your default browser...
start http://127.0.0.1:8000

echo.
echo ========================================================
echo   Application is now running!
echo   Website URL: http://127.0.0.1:8000
echo   API Docs:    http://127.0.0.1:8000/docs
echo.
echo   Keep the server window open while using the app.
echo ========================================================
echo.
pause
