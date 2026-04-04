$PythonPath = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Host "[ERROR] Virtual environment not found at $PythonPath" -ForegroundColor Red
    return
}

Write-Host "[SYSTEM] Launching AI Companion via PowerShell..."
& $PythonPath main.py
