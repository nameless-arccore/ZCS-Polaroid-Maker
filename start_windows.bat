param(
    [switch]$NoPause
)

# Windows PowerShell 5.1 compatibility:
# Binary string operators are never placed at the beginning of a continued line.
# The release launcher parses this file before executing it.
# Native Python checks use temporary .py files instead of python -c.
# This avoids Windows PowerShell 5.1 native-argument quote rewriting.

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$AppName = "ZCS Polaroid Maker"
$AppVersion = "2.14"

$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# 壊れたシステムPythonへ依存しない、ZCS専用の隔離ランタイム。
$PrivatePythonVersion = "3.11.9"
$PrivatePythonRoot = Join-Path `
    $env:LOCALAPPDATA `
    "ZCS\ZCS_Polaroid_Maker\Python311"
$PrivatePythonExe = Join-Path $PrivatePythonRoot "python.exe"

$SetupLog = Join-Path $PSScriptRoot "setup_windows.log"
$PythonInstallerLog = Join-Path `
    $PSScriptRoot `
    "private_python_installer.log"

function Write-SetupLog {
    param(
        [string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::Gray
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    try {
        Add-Content `
            -LiteralPath $SetupLog `
            -Value "[$timestamp] $Message" `
            -Encoding UTF8
    }
    catch {
        # ログ保存失敗だけではセットアップを止めない。
    }

    Write-Host $Message -ForegroundColor $Color
}

function Finish-Setup {
    param(
        [int]$ExitCode,
        [string]$Message
    )

    Write-Host ""

    if ($ExitCode -eq 0) {
        Write-SetupLog $Message Green
    }
    else {
        Write-SetupLog $Message Red
    }

    if (-not $NoPause) {
        Read-Host "Press Enter to exit"
    }

    exit $ExitCode
}

function Refresh-ProcessPath {
    $parts = New-Object System.Collections.Generic.List[string]

    foreach ($target in @(
        [EnvironmentVariableTarget]::Machine,
        [EnvironmentVariableTarget]::User
    )) {
        $value = [Environment]::GetEnvironmentVariable(
            "Path",
            $target
        )

        if ($value) {
            $parts.Add($value)
        }
    }

    if ($env:Path) {
        $parts.Add($env:Path)
    }

    $env:Path = ($parts -join ";")
}

function Invoke-PythonProbe {
    param(
        [string]$Executable,
        [string[]]$PrefixArguments = @(),
        [switch]$Quiet
    )

    if (
        $Executable -match '[\\/]' -and
        -not (Test-Path -LiteralPath $Executable)
    ) {
        return $null
    }

    # Windows PowerShell 5.1はnative commandの-c引数へ
    # 複数行コードや引用符を渡す際に内容を変形する場合がある。
    # そのため確認コードは一時.pyファイルとして実行する。
    $probeScript = Join-Path `
        $env:TEMP `
        ("zcs_python_probe_{0}.py" -f ([Guid]::NewGuid().ToString("N")))

    $probeSource = @(
        "import sys",
        "print(str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '|' + sys.executable)"
    )

    $arguments = @()
    $arguments += $PrefixArguments
    $arguments += @($probeScript)

    $oldPreference = $ErrorActionPreference

    try {
        Set-Content `
            -LiteralPath $probeScript `
            -Value $probeSource `
            -Encoding ASCII

        $ErrorActionPreference = "Continue"
        $output = @(
            & $Executable @arguments 2>&1
        )
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $oldPreference

        $textLines = @(
            $output | ForEach-Object { "$_" }
        )

        if ($exitCode -ne 0) {
            if (-not $Quiet) {
                Write-SetupLog `
                    ("Python probe failed: {0}" -f $Executable) `
                    Yellow
                Write-SetupLog `
                    ("  Exit code: {0}" -f $exitCode) `
                    Yellow

                foreach ($line in $textLines) {
                    if ($line.Trim()) {
                        Write-SetupLog `
                            ("  {0}" -f $line) `
                            Yellow
                    }
                }
            }

            return $null
        }

        $line = @(
            $textLines | Where-Object {
                $_ -match '^\d+\.\d+\|'
            }
        ) | Select-Object -Last 1

        if (-not $line) {
            if (-not $Quiet) {
                Write-SetupLog `
                    ("Python probe produced no version line: {0}" -f $Executable) `
                    Yellow

                foreach ($item in $textLines) {
                    if ($item.Trim()) {
                        Write-SetupLog `
                            ("  {0}" -f $item) `
                            Yellow
                    }
                }
            }

            return $null
        }

        $parts = $line.Trim().Split('|', 2)

        if ($parts.Count -ne 2) {
            return $null
        }

        $version = $parts[0]
        $resolvedExecutable = $parts[1]

        if (-not (Test-Path -LiteralPath $resolvedExecutable)) {
            return $null
        }

        return [PSCustomObject]@{
            Version = $version
            Executable = $resolvedExecutable
        }
    }
    catch {
        $ErrorActionPreference = $oldPreference

        if (-not $Quiet) {
            Write-SetupLog `
                ("Python could not start: {0}" -f $Executable) `
                Yellow
            Write-SetupLog `
                ("  {0}" -f $_.Exception.Message) `
                Yellow
        }

        return $null
    }
    finally {
        $ErrorActionPreference = $oldPreference

        if (Test-Path -LiteralPath $probeScript) {
            Remove-Item `
                -LiteralPath $probeScript `
                -Force `
                -ErrorAction SilentlyContinue
        }
    }
}

function Add-PythonCandidate {
    param(
        [System.Collections.Generic.List[object]]$List,
        [string]$Executable,
        [string[]]$Arguments = @()
    )

    if (-not $Executable) {
        return
    }

    $List.Add(
        [PSCustomObject]@{
            Executable = $Executable
            Arguments = $Arguments
        }
    )
}

function Get-Pep514PythonPaths {
    $paths = New-Object System.Collections.Generic.List[string]

    $roots = @(
        "HKCU:\Software\Python",
        "HKLM:\Software\Python",
        "HKLM:\Software\WOW6432Node\Python"
    )

    foreach ($root in $roots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }

        $companies = @(
            Get-ChildItem `
                -LiteralPath $root `
                -ErrorAction SilentlyContinue
        )

        foreach ($company in $companies) {
            if ($company.PSChildName -eq "PyLauncher") {
                continue
            }

            $tags = @(
                Get-ChildItem `
                    -LiteralPath $company.PSPath `
                    -ErrorAction SilentlyContinue
            )

            foreach ($tag in $tags) {
                $installPathKey = Join-Path `
                    $tag.PSPath `
                    "InstallPath"

                if (-not (Test-Path -LiteralPath $installPathKey)) {
                    continue
                }

                try {
                    $key = Get-Item -LiteralPath $installPathKey
                    $base = [string]$key.GetValue("")
                    $executable = [string]$key.GetValue(
                        "ExecutablePath"
                    )

                    if ($executable) {
                        $paths.Add($executable)
                    }

                    if ($base) {
                        $paths.Add(
                            (Join-Path $base "python.exe")
                        )
                    }
                }
                catch {
                    continue
                }
            }
        }
    }

    return @($paths)
}

function Find-CompatiblePython {
    Refresh-ProcessPath

    $candidates = New-Object System.Collections.Generic.List[object]

    # ZCS専用Pythonを最優先する。
    Add-PythonCandidate `
        -List $candidates `
        -Executable $PrivatePythonExe

    # Python Launcher。
    $pyCommand = Get-Command "py" -ErrorAction SilentlyContinue

    if ($pyCommand) {
        Add-PythonCandidate `
            -List $candidates `
            -Executable $pyCommand.Source `
            -Arguments @("-3.12")

        Add-PythonCandidate `
            -List $candidates `
            -Executable $pyCommand.Source `
            -Arguments @("-3.11")
    }

    # PEP 514レジストリ。
    foreach ($path in @(Get-Pep514PythonPaths)) {
        Add-PythonCandidate `
            -List $candidates `
            -Executable $path
    }

    # 標準的な設置場所。
    foreach ($path in @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:ProgramFiles\Python312\python.exe",
        "$env:ProgramFiles\Python311\python.exe",
        "${env:ProgramFiles(x86)}\Python312\python.exe",
        "${env:ProgramFiles(x86)}\Python311\python.exe"
    )) {
        Add-PythonCandidate `
            -List $candidates `
            -Executable $path
    }

    # PATHとwhere.exe。
    foreach ($name in @(
        "python",
        "python3",
        "python3.12",
        "python3.11"
    )) {
        $command = Get-Command $name -ErrorAction SilentlyContinue

        if (
            $command -and
            $command.Source -and
            $command.Source -notlike "*\WindowsApps\python.exe"
        ) {
            Add-PythonCandidate `
                -List $candidates `
                -Executable $command.Source
        }
    }

    try {
        foreach ($path in @(& where.exe python.exe 2>$null)) {
            if ($path -and $path -notlike "*\WindowsApps\*") {
                Add-PythonCandidate `
                    -List $candidates `
                    -Executable "$path"
            }
        }
    }
    catch {
        # where.exeが失敗しても続行。
    }

    $checked = @{}

    foreach ($candidate in $candidates) {
        $key = "{0}|{1}" -f `
            $candidate.Executable, `
            ($candidate.Arguments -join " ")

        if ($checked.ContainsKey($key)) {
            continue
        }

        $checked[$key] = $true

        $result = Invoke-PythonProbe `
            -Executable $candidate.Executable `
            -PrefixArguments $candidate.Arguments `
            -Quiet

        if (
            $result -and
            $result.Version -in @("3.11", "3.12")
        ) {
            return $result
        }
    }

    return $null
}

function Test-VirtualEnvironment {
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        return $false
    }

    $result = Invoke-PythonProbe `
        -Executable $VenvPython `
        -Quiet

    return ($null -ne $result)
}

function Get-NativeArchitecture {
    $architecture = $env:PROCESSOR_ARCHITECTURE

    if ($env:PROCESSOR_ARCHITEW6432) {
        $architecture = $env:PROCESSOR_ARCHITEW6432
    }

    switch ($architecture.ToUpperInvariant()) {
        "AMD64" { return "amd64" }
        "ARM64" { return "arm64" }
        default { return $null }
    }
}

function Install-PrivatePython {
    $architecture = Get-NativeArchitecture

    if (-not $architecture) {
        Write-SetupLog `
            "Unsupported Windows architecture." `
            Red
        return $null
    }

    $fileName = "python-{0}-{1}.exe" -f `
        $PrivatePythonVersion, `
        $architecture

    $downloadUrl = "https://www.python.org/ftp/python/{0}/{1}" -f `
        $PrivatePythonVersion, `
        $fileName
    $installerPath = Join-Path $env:TEMP $fileName

    Write-Host ""
    Write-SetupLog `
        "Installing an isolated Python runtime for ZCS Polaroid Maker..." `
        Cyan
    Write-SetupLog `
        ("Version: {0}" -f $PrivatePythonVersion)
    Write-SetupLog `
        ("Architecture: {0}" -f $architecture)
    Write-SetupLog `
        ("Target: {0}" -f $PrivatePythonRoot)

    try {
        [Net.ServicePointManager]::SecurityProtocol = (
            [Net.SecurityProtocolType]::Tls12
        )

        if (Test-Path -LiteralPath $installerPath) {
            Remove-Item `
                -LiteralPath $installerPath `
                -Force
        }

        if (Test-Path -LiteralPath $PrivatePythonRoot) {
            Write-SetupLog `
                "Removing the incomplete private Python runtime..." `
                Yellow

            Remove-Item `
                -LiteralPath $PrivatePythonRoot `
                -Recurse `
                -Force
        }

        New-Item `
            -ItemType Directory `
            -Path (Split-Path $PrivatePythonRoot -Parent) `
            -Force | Out-Null

        $null = Invoke-WebRequest `
            -UseBasicParsing `
            -Uri $downloadUrl `
            -OutFile $installerPath

        if (-not (Test-Path -LiteralPath $installerPath)) {
            throw "The Python installer was not downloaded."
        }

        $installerInfo = Get-Item -LiteralPath $installerPath

        if ($installerInfo.Length -lt 1MB) {
            throw "The downloaded installer is unexpectedly small."
        }

        $signature = Get-AuthenticodeSignature `
            -LiteralPath $installerPath

        if ($signature.Status -ne "Valid") {
            throw (
                "Invalid Python installer signature: {0}" -f `
                $signature.Status
            )
        }

        $signer = $signature.SignerCertificate.Subject

        if ($signer -notmatch "Python Software Foundation") {
            throw ("Unexpected installer signer: " + $signer)
        }

        Write-SetupLog `
            "Digital signature verified: Python Software Foundation" `
            Green

        $arguments = @(
            "/quiet",
            "/log",
            "`"$PythonInstallerLog`"",
            "InstallAllUsers=0",
            "TargetDir=`"$PrivatePythonRoot`"",
            "PrependPath=0",
            "Include_exe=1",
            "Include_lib=1",
            "Include_pip=1",
            "Include_tcltk=1",
            "Include_launcher=0",
            "InstallLauncherAllUsers=0",
            "Include_test=0",
            "Include_doc=0",
            "Include_symbols=0",
            "Include_debug=0",
            "AssociateFiles=0",
            "Shortcuts=0"
        ) -join " "

        $process = Start-Process `
            -FilePath $installerPath `
            -ArgumentList $arguments `
            -Wait `
            -PassThru

        Write-SetupLog `
            ("Private Python installer exit code: {0}" -f $process.ExitCode)

        if ($process.ExitCode -notin @(0, 3010)) {
            throw (
                "Private Python installer returned exit code {0}" -f `
                $process.ExitCode
            )
        }

        Start-Sleep -Seconds 2

        if (-not (Test-Path -LiteralPath $PrivatePythonExe)) {
            throw (
                "The installer completed, but private python.exe was not created."
            )
        }

        $runtimeResult = Invoke-PythonProbe `
            -Executable $PrivatePythonExe

        if (-not $runtimeResult) {
            Write-SetupLog `
                "Private runtime file inspection:" `
                Yellow

            foreach ($path in @(
                $PrivatePythonExe,
                (Join-Path $PrivatePythonRoot "python311.dll"),
                (Join-Path $PrivatePythonRoot "Lib"),
                (Join-Path $PrivatePythonRoot "DLLs"),
                (Join-Path $PrivatePythonRoot "tcl")
            )) {
                Write-SetupLog `
                    ("  {0} / exists={1}" -f $path, (Test-Path -LiteralPath $path)) `
                    Yellow
            }

            throw (
                "The private Python runtime exists but cannot start. See setup_windows.log and private_python_installer.log."
            )
        }

        Write-SetupLog `
            ("Private Python is ready: {0}" -f $runtimeResult.Executable) `
            Green

        return $runtimeResult
    }
    catch {
        Write-SetupLog `
            ("Private Python installation failed: {0}" -f $_.Exception.Message) `
            Red

        return $null
    }
    finally {
        if (Test-Path -LiteralPath $installerPath) {
            Remove-Item `
                -LiteralPath $installerPath `
                -Force `
                -ErrorAction SilentlyContinue
        }
    }
}

try {
    Set-Content `
        -LiteralPath $SetupLog `
        -Value "=== $AppName $AppVersion Setup Log ===" `
        -Encoding UTF8
}
catch {
    # ログ作成失敗だけでは中止しない。
}

Write-SetupLog `
    "=== $AppName $AppVersion Setup ===" `
    Cyan
Write-SetupLog ("Folder: {0}" -f $PSScriptRoot)
Write-Host ""

# 別PC由来または壊れた仮想環境は再作成。
if (Test-Path -LiteralPath $VenvDir) {
    if (Test-VirtualEnvironment) {
        Write-SetupLog `
            "Existing Python environment is valid." `
            Green
    }
    else {
        Write-SetupLog `
            "Existing .venv is invalid or belongs to another PC." `
            Yellow
        Write-SetupLog "Recreating .venv..."

        Remove-Item `
            -LiteralPath $VenvDir `
            -Recurse `
            -Force
    }
}

if (-not (Test-VirtualEnvironment)) {
    $python = Find-CompatiblePython

    if (-not $python) {
        Write-SetupLog `
            "No usable Python 3.11 or 3.12 was found." `
            Yellow
        Write-SetupLog `
            "The existing registered Python will not be modified." `
            Yellow

        $python = Install-PrivatePython
    }

    if (-not $python) {
        Finish-Setup `
            -ExitCode 2 `
            -Message (
                "Automatic private Python installation failed. See setup_windows.log."
            )
    }

    Write-Host ""
    Write-SetupLog `
        ("Using Python {0}:" -f $python.Version) `
        Green
    Write-SetupLog ("  {0}" -f $python.Executable)
    Write-Host ""
    Write-SetupLog "Creating .venv..."

    & $python.Executable -m venv $VenvDir
    $venvExit = $LASTEXITCODE

    if (
        $venvExit -ne 0 -or
        -not (Test-Path -LiteralPath $VenvPython)
    ) {
        Finish-Setup `
            -ExitCode 3 `
            -Message (
                "Failed to create .venv. Exit code: {0}" -f `
                $venvExit
            )
    }
}

try {
    Write-Host ""
    Write-SetupLog "Updating pip..."

    & $VenvPython -m pip install --upgrade pip

    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed."
    }

    Write-Host ""
    Write-SetupLog "Installing required packages..."

    & $VenvPython -m pip install `
        -r (Join-Path $PSScriptRoot "requirements.txt")

    if ($LASTEXITCODE -ne 0) {
        throw "Package installation failed."
    }

    Write-Host ""
    Write-SetupLog "Verifying the application environment..."

    $verifyScript = Join-Path `
        $env:TEMP `
        ("zcs_environment_verify_{0}.py" -f ([Guid]::NewGuid().ToString("N")))

    try {
        Set-Content `
            -LiteralPath $verifyScript `
            -Value @(
                "from PIL import Image",
                "import tkinter",
                "print('Pillow and Tkinter: OK')"
            ) `
            -Encoding ASCII

        & $VenvPython $verifyScript
        $verifyExit = $LASTEXITCODE
    }
    finally {
        if (Test-Path -LiteralPath $verifyScript) {
            Remove-Item `
                -LiteralPath $verifyScript `
                -Force `
                -ErrorAction SilentlyContinue
        }
    }

    if ($verifyExit -ne 0) {
        throw "Application environment verification failed."
    }
}
catch {
    Write-SetupLog `
        ("Setup error: {0}" -f $_.Exception.Message) `
        Red

    Finish-Setup `
        -ExitCode 4 `
        -Message (
            "ZCS Polaroid Maker setup failed. See setup_windows.log."
        )
}

Finish-Setup `
    -ExitCode 0 `
    -Message "ZCS Polaroid Maker setup completed."
