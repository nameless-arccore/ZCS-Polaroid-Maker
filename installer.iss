$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot

$PrivatePythonRoot = Join-Path `
    $env:LOCALAPPDATA `
    "ZCS\ZCS_Polaroid_Maker\Python311"
$PrivatePythonExe = Join-Path $PrivatePythonRoot "python.exe"

Write-Host "=== ZCS Polaroid Maker Environment Check ===" -ForegroundColor Cyan
Write-Host "Folder: $PSScriptRoot"
Write-Host "Windows: $([Environment]::OSVersion.VersionString)"
Write-Host "64-bit OS: $([Environment]::Is64BitOperatingSystem)"
Write-Host "Architecture: $env:PROCESSOR_ARCHITECTURE"
Write-Host ""

Write-Host "ZCS private Python:"
Write-Host "  Root: $PrivatePythonRoot"
Write-Host "  python.exe exists: $(Test-Path -LiteralPath $PrivatePythonExe)"

if (Test-Path -LiteralPath $PrivatePythonExe) {
    Write-Host "  Running private Python..."

    $output = @(
        & $PrivatePythonExe -c "import sys; print(sys.version); print(sys.executable)" 2>&1
    )
    $exitCode = $LASTEXITCODE

    Write-Host "  Exit code: $exitCode"

    foreach ($line in $output) {
        Write-Host "  $line"
    }

    foreach ($path in @(
        (Join-Path $PrivatePythonRoot "python311.dll"),
        (Join-Path $PrivatePythonRoot "Lib"),
        (Join-Path $PrivatePythonRoot "DLLs"),
        (Join-Path $PrivatePythonRoot "tcl")
    )) {
        Write-Host "  $path : $(Test-Path -LiteralPath $path)"
    }
}

Write-Host ""
Write-Host "Commands:"

foreach ($name in @(
    "py",
    "python",
    "python3"
)) {
    $command = Get-Command $name -ErrorAction SilentlyContinue

    if ($command) {
        Write-Host "  $name : $($command.Source)"
    }
    else {
        Write-Host "  $name : not found"
    }
}

Write-Host ""
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host ".venv:"
Write-Host "  $venvPython : $(Test-Path -LiteralPath $venvPython)"

if (Test-Path -LiteralPath $venvPython) {
    $output = @(
        & $venvPython -c "import sys; print(sys.version); print(sys.executable)" 2>&1
    )
    $exitCode = $LASTEXITCODE

    Write-Host "  Exit code: $exitCode"

    foreach ($line in $output) {
        Write-Host "  $line"
    }
}

foreach ($name in @(
    "setup_windows.log",
    "private_python_installer.log"
)) {
    Write-Host ""
    $path = Join-Path $PSScriptRoot $name

    if (Test-Path -LiteralPath $path) {
        Write-Host "Last lines of $name:"
        Get-Content -LiteralPath $path -Tail 60
    }
    else {
        Write-Host "$name : not found"
    }
}

Write-Host ""
Read-Host "Press Enter to exit"
