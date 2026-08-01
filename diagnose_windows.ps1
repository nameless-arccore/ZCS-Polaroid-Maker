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
        Write-Host "EXE build failed. Portable package was not created." -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

$portable = Join-Path $PSScriptRoot "portable\ZCS Polaroid Maker 2.14"
if (Test-Path -LiteralPath $portable) {
    Remove-Item -LiteralPath $portable -Recurse -Force
}
New-Item -ItemType Directory -Path $portable | Out-Null

Copy-Item -LiteralPath $exePath -Destination $portable
Copy-Item -LiteralPath ".\README_最初にお読みください.txt" -Destination $portable

$zip = Join-Path $PSScriptRoot "portable\ZCS_Polaroid_Maker_2.14_Portable.zip"
if (Test-Path -LiteralPath $zip) {
    Remove-Item -LiteralPath $zip -Force
}

Compress-Archive -Path "$portable\*" -DestinationPath $zip

Write-Host "Portable package created: $zip" -ForegroundColor Green
Read-Host "Press Enter to exit"
