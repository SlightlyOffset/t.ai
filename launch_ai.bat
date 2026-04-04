@echo off
setlocal
cd /d "%~dp0"

set PYTHON_EXE=%~dp0.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at %PYTHON_EXE%
    echo Please ensure the .venv folder exists and contains Scripts\python.exe
    pause
    exit /b
)

echo [SYSTEM] Launching AI Companion...
echo [DEBUG] Using Python: %PYTHON_EXE%

"%PYTHON_EXE%" main.py

if %ERRORLEVEL% NEQ 0 (
    echo [SYSTEM] Application exited with error code %ERRORLEVEL%
    pause
)
endlocal
