# ChaosPilot one-command demo (Windows): simulator + backend + dashboard.
#
#   powershell -ExecutionPolicy Bypass -File .\run_demo.ps1
#
# Requirements: Python 3.11+, Node.js 20+. No Docker required.
# The script is safe to re-run: it only creates .env, the virtualenv and
# node_modules when they are missing. It builds the seed dataset and trains
# the anomaly model if they are absent, so the app works with zero internet.
# The backend and dashboard start in their own windows.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Say($Message) { Write-Host "`n$Message" -ForegroundColor Cyan }
function Fail($Message) {
  Write-Host "`n$Message" -ForegroundColor Red
  exit 1
}

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
  $Python = "python3"
}
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
  Fail "Python 3.11+ was not found; install Python or set the PYTHON environment variable."
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Say "created .env from .env.example"
}

$Venv = Join-Path $Root "backend\.venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
  Say "creating backend virtualenv"
  & $Python -m venv $Venv
}

Say "installing backend dependencies"
& $VenvPython -m pip install --quiet --upgrade pip
& $VenvPython -m pip install --quiet -r (Join-Path $Root "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "backend dependency installation failed." }

# --- seed data + anomaly model (offline, zero internet) ---------------------
$SeedMarker = Join-Path $Root "backend\data\seed\metrics_seed.csv"
$ModelMarker = Join-Path $Root "backend\models\isolation_forest.joblib"
if (-not (Test-Path $SeedMarker) -or -not (Test-Path $ModelMarker)) {
  Say "building seed dataset and training the anomaly model"
  & $VenvPython (Join-Path $Root "scripts\build_seed.py")
  if ($LASTEXITCODE -ne 0) { Fail "seed build failed." }
}

$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $Npm) { $Npm = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $Npm) { Fail "Node.js and npm are required: https://nodejs.org/" }

if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
  Say "installing frontend dependencies"
  Push-Location (Join-Path $Root "frontend")
  & $Npm.Source install
  Pop-Location
}

function Wait-Healthy($Url, $Label, $Attempts = 60) {
  for ($i = 0; $i -lt $Attempts; $i++) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
      if ($response.StatusCode -eq 200) { return }
    } catch {
      # Keep polling until the service is up.
    }
    Start-Sleep -Seconds 1
  }
  Fail "$Label did not become healthy at $Url"
}

Say "starting the backend on http://127.0.0.1:8090"
$Backend = Start-Process -FilePath $VenvPython `
  -ArgumentList @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8090") `
  -WorkingDirectory (Join-Path $Root "backend") -PassThru
Wait-Healthy "http://127.0.0.1:8090/health" "ChaosPilot API" 60

Say "starting the dashboard on http://localhost:5173"
$Frontend = Start-Process -FilePath $Npm.Source -ArgumentList @("run", "dev") `
  -WorkingDirectory (Join-Path $Root "frontend") -PassThru
Wait-Healthy "http://localhost:5173" "dashboard" 60

Write-Host ""
Write-Host "dashboard : http://localhost:5173" -ForegroundColor Green
Write-Host "api docs  : http://127.0.0.1:8090/docs" -ForegroundColor Green
Write-Host "backend PID: $($Backend.Id)  (stop with: Stop-Process -Id $($Backend.Id))"
Write-Host "frontend PID: $($Frontend.Id)  (stop with: Stop-Process -Id $($Frontend.Id))"

Start-Process "http://localhost:5173"
