$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\setup_windows.ps1"
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
& ".\.venv\Scripts\pyinstaller.exe" `
  --noconfirm `
  --clean `
  --windowed `
  --onefile `
  --name "ZCS Polaroid Maker" `
  --icon ".\zcs_polaroid_maker.ico" `
  --collect-all rawpy `
  app.py

Write-Host ""
Write-Host "EXE created: dist\ZCS Polaroid Maker.exe" -ForegroundColor Green
Read-Host "Press Enter to exit"
