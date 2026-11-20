# ChaosPilot Localhost Quick Launcher
Set-Location $PSScriptRoot

Write-Host "Checking ChaosPilot services..." -ForegroundColor Cyan

$backendRunning = Get-NetTCPConnection -LocalPort 8090 -State Listen -ErrorAction SilentlyContinue
if (-not $backendRunning) {
    Write-Host "Starting Backend on http://127.0.0.1:8090..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-Command backend\.venv\Scripts\python.exe -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8090" -WindowStyle Minimized
} else {
    Write-Host "Backend already active on http://127.0.0.1:8090" -ForegroundColor Green
}

$frontendRunning = Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue
if (-not $frontendRunning) {
    Write-Host "Starting Frontend on http://localhost:5173..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-Command npm --prefix frontend run dev" -WindowStyle Minimized
} else {
    Write-Host "Frontend already active on http://localhost:5173" -ForegroundColor Green
}

Start-Sleep -Seconds 2
Start-Process "http://localhost:5173"
Write-Host "ChaosPilot Dashboard opened at http://localhost:5173" -ForegroundColor Green
