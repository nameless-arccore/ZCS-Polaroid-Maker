@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Running setup...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_windows.ps1"
    if errorlevel 1 (
        echo Setup failed.
        pause
        popd
        exit /b 1
    )
)

if exist ".venv\Scripts\pythonw.exe" (
    start "ZCS Polaroid Maker" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
) else (
    ".venv\Scripts\python.exe" "%~dp0app.py"
)

popd
endlocal
