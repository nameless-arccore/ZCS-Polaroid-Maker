$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$exePath = Join-Path $PSScriptRoot "dist\ZCS Polaroid Maker.exe"

if (-not (Test-Path -LiteralPath $exePath)) {
    & powershell.exe `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File ".\build_exe.ps1" `
        -NoPause

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $exePath)) {
        Write-Host "EXE build failed. Installer was not created." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

$possible = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
)
$iscc = $possible |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1

if (-not $iscc) {
    Write-Host "Inno Setup 6 was not found." -ForegroundColor Yellow
    Write-Host "Install Inno Setup 6, then run this script again."
    Read-Host "Press Enter to exit"
    exit 1
}

& $iscc ".\installer.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installer build failed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Installer created in installer_output." -ForegroundColor Green
Read-Host "Press Enter to exit"
