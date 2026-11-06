#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SetupOnly,
    [switch]$ReinstallDependencies
)

$ErrorActionPreference = 'Stop'

function Invoke-Checked {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "A setup command failed (exit $LASTEXITCODE). Fix the error printed above and run this script again."
    }
}

function Test-AvailablePort {
    param([int]$Port)
    $listener = New-Object System.Net.Sockets.TcpListener -ArgumentList ([System.Net.IPAddress]::Loopback), $Port
    try { $listener.Start() }
    catch { throw "Port $Port is already in use or unavailable. Stop the other server with Ctrl+C, then try again." }
    finally { $listener.Stop() }
}

Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not $SetupOnly) { Test-AvailablePort -Port 8000 }
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        Write-Host 'Created .env from the local development template.' -ForegroundColor Cyan
    }

    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $pythonCommand = $null
        $pythonPrefix = @()
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            try {
                & $launcher.Source -3.12 -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>$null
                if ($LASTEXITCODE -eq 0) {
                    $pythonCommand = $launcher.Source
                    $pythonPrefix = @('-3.12')
                }
            } catch { }
        }
        if (-not $pythonCommand) {
            $candidates = @(
                (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
                (Join-Path $env:ProgramFiles 'Python312\python.exe')
            )
            $pythonOnPath = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($pythonOnPath -and $pythonOnPath.Source -notlike '*\WindowsApps\*') {
                $candidates += $pythonOnPath.Source
            }
            foreach ($candidate in ($candidates | Select-Object -Unique)) {
                if (Test-Path -LiteralPath $candidate) {
                    try {
                        & $candidate -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>$null
                        if ($LASTEXITCODE -eq 0) { $pythonCommand = $candidate; break }
                    } catch { }
                }
            }
        }
        if (-not $pythonCommand) { throw 'Python 3.12 was not found. Install Python 3.12, reopen PowerShell, and run this script again.' }
        Write-Host 'Creating the Python virtual environment...' -ForegroundColor Cyan
        $createArguments = $pythonPrefix + @('-m', 'venv', (Join-Path $PSScriptRoot '.venv'))
        Invoke-Checked -FilePath $pythonCommand -Arguments $createArguments
    }

    Invoke-Checked -FilePath $venvPython -Arguments @('-c', 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)')
    $requirementsHash = (Get-FileHash -LiteralPath 'requirements.txt' -Algorithm SHA256).Hash
    $marker = Join-Path $PSScriptRoot '.venv\.marketpilot-requirements.sha256'
    $savedHash = ''
    if (Test-Path -LiteralPath $marker) { $savedHash = [string](Get-Content -LiteralPath $marker -Raw) }
    if ($ReinstallDependencies -or $savedHash.Trim() -ne $requirementsHash) {
        Write-Host 'Installing backend dependencies. The first run needs internet access...' -ForegroundColor Cyan
        Invoke-Checked -FilePath $venvPython -Arguments @('-m', 'pip', 'install', '-r', 'requirements.txt')
        Set-Content -LiteralPath $marker -Value $requirementsHash -Encoding ASCII
    }

    Write-Host 'Applying database migrations...' -ForegroundColor Cyan
    Invoke-Checked -FilePath $venvPython -Arguments @('-m', 'alembic', 'upgrade', 'head')
    if ($SetupOnly) {
        Write-Host 'Backend setup complete. No server was started.' -ForegroundColor Green
    } else {
        Write-Host 'Starting backend. API docs: http://localhost:8000/docs' -ForegroundColor Green
        Write-Host 'Keep this window open. Press Ctrl+C to stop.'
        & $venvPython -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
        if ($LASTEXITCODE -notin @(0, 130, -1073741510)) { throw "Backend exited with code $LASTEXITCODE. Review the server error above." }
    }
} catch {
    Write-Host ("ERROR: " + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}
