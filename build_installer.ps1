param(
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$VenvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Finish-Build {
    param([int]$Code, [string]$Message)

    Write-Host ""
    if ($Code -eq 0) {
        Write-Host $Message -ForegroundColor Green
    }
    else {
        Write-Host $Message -ForegroundColor Red
    }

    if (-not $NoPause) {
        Read-Host "Press Enter to exit"
    }
    exit $Code
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File ".\setup_windows.ps1" `
        -NoPause

    if ($LASTEXITCODE -ne 0) {
        Finish-Build $LASTEXITCODE "Setup failed. EXE was not created."
    }
}

& $VenvPython -c "import sys; assert sys.prefix != sys.base_prefix" *> $null
if ($LASTEXITCODE -ne 0) {
    Remove-Item ".\.venv" -Recurse -Force -ErrorAction SilentlyContinue

    & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File ".\setup_windows.ps1" `
        -NoPause

    if ($LASTEXITCODE -ne 0) {
        Finish-Build $LASTEXITCODE "Environment repair failed. EXE was not created."
    }
}

& $VenvPython -m pip install --upgrade "pyinstaller>=6.6,<7"
if ($LASTEXITCODE -ne 0) {
    Finish-Build 6 "PyInstaller installation failed."
}

& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "ZCS Polaroid Maker" `
    --icon ".\zcs_polaroid_maker.ico" `
    --collect-all rawpy `
    app.py

if ($LASTEXITCODE -ne 0) {
    Finish-Build 7 "PyInstaller build failed."
}

$exePath = Join-Path $PSScriptRoot "dist\ZCS Polaroid Maker.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    Finish-Build 8 "Build ended without producing the EXE."
}

Finish-Build 0 "EXE created: dist\ZCS Polaroid Maker.exe"
