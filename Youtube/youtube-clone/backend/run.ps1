$ErrorActionPreference = "Stop"

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $backendRoot

# Keep heavy model cache in project drive by default (avoids C: low-space issues).
$defaultHfCache = Join-Path $backendRoot ".hf-cache"
if (-not (Test-Path $defaultHfCache)) {
    New-Item -ItemType Directory -Path $defaultHfCache | Out-Null
}

if (-not $env:HF_HOME) {
    $env:HF_HOME = $defaultHfCache
}
if (-not $env:HUGGINGFACE_HUB_CACHE) {
    $env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME "hub"
}
if (-not $env:TRANSFORMERS_CACHE) {
    $env:TRANSFORMERS_CACHE = Join-Path $env:HF_HOME "transformers"
}
if (-not $env:SENTENCE_TRANSFORMERS_HOME) {
    $env:SENTENCE_TRANSFORMERS_HOME = Join-Path $env:HF_HOME "sentence_transformers"
}

Write-Host "Hugging Face cache root: $($env:HF_HOME)"

#####################################################################################

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
