$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendRoot

$venvPython = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.12 and try again."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating Python 3.12 virtual environment..."
    py -3.12 -m venv .venv
}

Write-Host "Installing backend dependencies..."
& $venvPython -m pip install -r requirements.txt

Write-Host "Starting backend server on http://127.0.0.1:8000 ..."
& $venvPython -m uvicorn app.main:app --reload --port 8000
