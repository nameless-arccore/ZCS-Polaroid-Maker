$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== ZCS Polaroid Maker 2.0 Setup ===" -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python Launcher (py) was not found." -ForegroundColor Red
    Write-Host "Install Python 3.11 or 3.12, then run this script again."
    Read-Host "Press Enter to exit"
    exit 1
}

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host ""
Write-Host "ZCS Polaroid Maker setup completed." -ForegroundColor Green
Write-Host "Double-click start_windows.bat to launch."
Read-Host "Press Enter to exit"
