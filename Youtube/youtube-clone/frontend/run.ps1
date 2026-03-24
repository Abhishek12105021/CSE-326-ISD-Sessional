$ErrorActionPreference = "Stop"

$frontendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $frontendRoot
$npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue

if (-not $npmCmd) {
    throw "npm was not found. Install Node.js and try again."
}

$nodeModulesPath = Join-Path $frontendRoot "node_modules"
$supabasePackagePath = Join-Path $frontendRoot "node_modules\@supabase\supabase-js"

if (
    (-not (Test-Path $nodeModulesPath)) -or
    (-not (Test-Path $supabasePackagePath))
) {
    Write-Host "Installing frontend dependencies..."
    & $npmCmd.Source install
}

Write-Host "Starting frontend dev server on http://localhost:3000 ..."
& $npmCmd.Source run dev
