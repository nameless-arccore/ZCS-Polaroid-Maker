$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\dist\ZCS Polaroid Maker.exe")) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\build_exe.ps1"
}

$possible = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $possible | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Inno Setup 6 was not found." -ForegroundColor Yellow
    Write-Host "Install Inno Setup 6, then run this script again."
    Read-Host "Press Enter to exit"
    exit 1
}

& $iscc ".\installer.iss"
Write-Host ""
Write-Host "Installer created in installer_output." -ForegroundColor Green
Read-Host "Press Enter to exit"
