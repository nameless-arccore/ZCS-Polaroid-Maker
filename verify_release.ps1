@echo off
setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0"

set "VENV_DIR=%~dp0.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "VENV_PYW=%VENV_DIR%\Scripts\pythonw.exe"
set "SETUP_PS1=%~dp0setup_windows.ps1"

if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; assert sys.prefix != sys.base_prefix" >nul 2>&1

    if errorlevel 1 (
        echo Existing Python environment is invalid or belongs to another PC.
        echo Rebuilding .venv...
        rmdir /s /q "%VENV_DIR%" >nul 2>&1
    )
)

if not exist "%VENV_PY%" (
    echo Python environment not found.
    echo A private Python runtime and required packages will be installed automatically.
    echo The registered system Python will not be modified.
    echo An internet connection is required.
    echo.

    rem Parse setup_windows.ps1 with the Windows PowerShell parser first.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$tokens=$null; $errors=$null; [System.Management.Automation.Language.Parser]::ParseFile($env:SETUP_PS1,[ref]$tokens,[ref]$errors) > $null; if($errors.Count -gt 0){ foreach($item in $errors){ Write-Host ('Parser error: ' + $item.Message) -ForegroundColor Red }; exit 87 }; exit 0"
    set "PARSE_EXIT=!ERRORLEVEL!"

    if not "!PARSE_EXIT!"=="0" (
        echo.
        echo setup_windows.ps1 has a syntax error.
        echo Replace it with the v2.13 file, then run start_windows.bat again.
        pause
        popd
        exit /b !PARSE_EXIT!
    )

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP_PS1%" -NoPause
    set "SETUP_EXIT=!ERRORLEVEL!"

    if not "!SETUP_EXIT!"=="0" (
        echo.
        echo Setup failed. Exit code: !SETUP_EXIT!
        echo Details:
        echo   %~dp0setup_windows.log
        echo   %~dp0private_python_installer.log
        echo.
        echo Run diagnose_windows.ps1 if the cause is unclear.
        pause
        popd
        exit /b !SETUP_EXIT!
    )
)

if not exist "%VENV_PY%" (
    echo.
    echo Setup completed without creating .venv.
    echo Review:
    echo   %~dp0setup_windows.log
    pause
    popd
    exit /b 5
)

if exist "%VENV_PYW%" (
    start "" "%VENV_PYW%" "%~dp0app.py"
) else (
    "%VENV_PY%" "%~dp0app.py"
    set "APP_EXIT=!ERRORLEVEL!"

    if not "!APP_EXIT!"=="0" (
        echo.
        echo The application stopped with error code !APP_EXIT!.
        pause
    )
)

popd
endlocal
