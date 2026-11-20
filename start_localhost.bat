@echo off
title ChaosPilot Localhost Launcher
echo ============================================================
echo   ChaosPilot - AI Agent Chaos Engineering Cockpit
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking environment...
if not exist ".env" (
    copy ".env.example" ".env" >nul 2>&1
    echo   Created .env from .env.example
)

echo [2/3] Checking backend and frontend services...

:: Check if backend is already listening on port 8090
netstat -ano | findstr ":8090" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo   Starting Backend (FastAPI on http://127.0.0.1:8090)...
    start "ChaosPilot Backend" /min powershell -Command "backend\.venv\Scripts\python.exe -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8090"
) else (
    echo   Backend is already active on http://127.0.0.1:8090
)

:: Check if frontend is already listening on port 5173
netstat -ano | findstr ":5173" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo   Starting Frontend (Vite on http://localhost:5173)...
    start "ChaosPilot Frontend" /min powershell -Command "npm --prefix frontend run dev"
) else (
    echo   Frontend is already active on http://localhost:5173
)

:: Wait 2 seconds for services to ensure ports are listening
timeout /t 2 /nobreak >nul 2>&1

echo [3/3] Opening dashboard in browser...
start http://localhost:5173/

echo.
echo ============================================================
echo   ChaosPilot is running:
echo   - Local Dashboard : http://localhost:5173/
echo   - Backend Health  : http://127.0.0.1:8090/health
echo   - API Swagger     : http://127.0.0.1:8090/docs
echo ============================================================
echo.
pause
