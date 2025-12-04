param(
    [string]$Port = "5000"
)

Write-Host "Starting dispatcher install..." -ForegroundColor Cyan
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$backend = Join-Path $root "backend"
$venv = Join-Path $backend ".venv"

# Helper to run and throw on failure
function RunOrFail($cmd, $args) {
    $p = Start-Process -FilePath $cmd -ArgumentList $args -NoNewWindow -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        throw "Command failed: $cmd $args"
    }
}

# Check basics
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js not found. Install Node LTS first." }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm not found. Install Node LTS first." }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python not found. Install Python 3.11+ and add to PATH." }

# Frontend build
Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location $frontend
RunOrFail "npm" "install"
Write-Host "Building frontend..." -ForegroundColor Yellow
RunOrFail "npm" "run build"
Pop-Location

# Backend venv + deps
if (-not (Test-Path $venv)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Yellow
    RunOrFail "python" "-m venv `"$venv`""
}

$py = Join-Path $venv "Scripts\python.exe"
$pip = Join-Path $venv "Scripts\pip.exe"
Write-Host "Upgrading pip and installing backend dependencies..." -ForegroundColor Yellow
RunOrFail $py "-m pip install --upgrade pip"
RunOrFail $pip "-r `"$backend\requirements.txt`""

# Seed backend .env if missing
$envFile = Join-Path $backend ".env"
$envExample = Join-Path $backend ".env.example"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envFile
    Write-Host "Created backend\.env from example. Edit it to add API keys." -ForegroundColor Green
}

Write-Host "Launching server on port $Port ..." -ForegroundColor Cyan
Push-Location $backend
RunOrFail $py "-m waitress --host 0.0.0.0 --port $Port app:create_app"
Pop-Location
