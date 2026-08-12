@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title GrayBar Meraki Manager - Web Server

echo.
echo ============================================================
echo   GrayBar Meraki Manager - Web Interface
echo ============================================================
echo.

:: ── Check Python ──────────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Download Python from https://python.org and re-run.
    pause & exit 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [1/3] Python !PYVER! found.

:: ── Virtual environment ────────────────────────────────────────────────────────
set VENV=.web_venv
if not exist "%VENV%\Scripts\activate.bat" (
    echo [2/3] Creating virtual environment...
    python -m venv "%VENV%"
    if errorlevel 1 ( echo [ERROR] Could not create venv. & pause & exit 1 )
) else (
    echo [2/3] Virtual environment ready.
)
call "%VENV%\Scripts\activate.bat"

:: ── Install / update dependencies ─────────────────────────────────────────────
echo [3/3] Installing/updating dependencies...
python -m pip install --upgrade pip >nul 2>&1
timeout /t 2 /nobreak >nul
python -m pip install -r requirements-web.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause & exit 1
)

:: ── Launch ─────────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo   Starting server at http://localhost:8000
echo   Press Ctrl+C to stop.
echo ============================================================
echo.

:: Open browser after a short delay
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8000"

python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000
pause
