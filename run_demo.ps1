# ChaosPilot one-command demo (Windows): sample stack + backend + dashboard.
#
#   powershell -ExecutionPolicy Bypass -File .\run_demo.ps1
#
# Requirements: Docker Desktop with Compose v2, Python 3.11, Node.js 18+.
# The script is safe to re-run: it only creates .env, the virtualenv and
# node_modules when they are missing. The backend and dashboard start in their
# own windows, so this script returns once both are healthy. Stop them with
# Ctrl+C in their windows; stop the stack with:
#   docker compose -f sample-stack/docker-compose.yml down

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Say($Message) { Write-Host "`n$Message" -ForegroundColor Cyan }
function Fail($Message) {
  Write-Host "`n$Message" -ForegroundColor Red
  exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Fail "Docker is required: https://docs.docker.com/get-docker/"
}
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Fail "Docker Compose v2 is required (docker compose)." }

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Say "created .env from .env.example (edit it to use Ollama or OpenAI)"
}

$Python = if ($env:PYTHON) { $env:PYTHON } else { "python" }
if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
  Fail "Python was not found; install Python 3.11 or set the PYTHON environment variable."
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

$Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $Npm) { $Npm = Get-Command npm -ErrorAction SilentlyContinue }
if (-not $Npm) { Fail "Node.js and npm are required: https://nodejs.org/" }

if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
  Say "installing frontend dependencies"
  Push-Location (Join-Path $Root "frontend")
  & $Npm.Source install
  Pop-Location
}

function Wait-Healthy($Url, $Label, $Attempts = 120) {
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

Say "starting the sample stack"
docker compose -f sample-stack/docker-compose.yml up -d --build
if ($LASTEXITCODE -ne 0) { Fail "docker compose up failed." }
Wait-Healthy "http://127.0.0.1:8000/health" "sample-stack gateway"

Say "starting the backend on http://127.0.0.1:8090"
$Backend = Start-Process -FilePath $VenvPython `
  -ArgumentList @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8090") `
  -WorkingDirectory (Join-Path $Root "backend") -PassThru
Wait-Healthy "http://127.0.0.1:8090/health" "ChaosPilot API" 60

Say "starting the dashboard on http://localhost:5173"
Start-Process -FilePath $Npm.Source -ArgumentList @("run", "dev") `
  -WorkingDirectory (Join-Path $Root "frontend")
Wait-Healthy "http://127.0.0.1:5173" "dashboard" 60

Write-Host ""
Write-Host "dashboard : http://localhost:5173" -ForegroundColor Green
Write-Host "api docs  : http://127.0.0.1:8090/docs" -ForegroundColor Green
Write-Host "backend PID: $($Backend.Id)  (stop with: Stop-Process -Id $($Backend.Id))"
Write-Host "stack     : docker compose -f sample-stack/docker-compose.yml down"

Start-Process "http://localhost:5173"
