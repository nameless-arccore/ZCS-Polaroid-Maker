$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\dist\ZCS Polaroid Maker.exe")) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\build_exe.ps1"
}

$portable = Join-Path $PSScriptRoot "portable\ZCS Polaroid Maker 2.6"
if (Test-Path $portable) { Remove-Item $portable -Recurse -Force }
New-Item -ItemType Directory -Path $portable | Out-Null
Copy-Item ".\dist\ZCS Polaroid Maker.exe" $portable
Copy-Item ".\README_最初にお読みください.txt" $portable

$zip = Join-Path $PSScriptRoot "portable\ZCS_Polaroid_Maker_2.6_Portable.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$portable\*" -DestinationPath $zip

Write-Host "Portable package created: $zip" -ForegroundColor Green
Read-Host "Press Enter to exit"
