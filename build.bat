@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title GrayBar Meraki Manager — Build Script

:: ── Log file ──────────────────────────────────────────────────────────────────
set "LOGFILE=%~dp0build.log"
echo Build started: %date% %time% > "%LOGFILE%"
echo. >> "%LOGFILE%"
echo Log file: %LOGFILE%

:: ── Require Administrator privileges ─────────────────────────────────────────
net session >nul 2>&1
if errorlevel 1 (
    call :fail "This script must be run as Administrator. Right-click build.bat and choose 'Run as administrator'."
)

echo.
echo ============================================================
echo   GrayBar Meraki Manager — Windows Installer Builder
echo ============================================================
echo.

:: ── Configuration ────────────────────────────────────────────────────────────
set APP_NAME=GrayBarMerakiManager
set PYTHON_VERSION=3.12.9
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe
set PYTHON_INSTALLER=%TEMP%\python-installer.exe
set INNO_VERSION=6.3.3
set INNO_URL=https://files.jrsoftware.org/is/6/innosetup-6.3.3.exe
set INNO_INSTALLER=%TEMP%\innosetup-installer.exe
set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
set VENV_DIR=.build_venv
set OUTPUT_DIR=Output

:: ── Check for internet connectivity ──────────────────────────────────────────
ping -n 1 www.python.org >nul 2>&1
if errorlevel 1 (
    call :fail "No internet connection detected. Please connect to the internet and try again."
)

:: ── Step 1: Python ────────────────────────────────────────────────────────────
echo [1/6] Checking for Python...
echo [1/6] Checking for Python... >> "%LOGFILE%"
python --version >nul 2>&1
if errorlevel 1 (
    echo       Python not found. Downloading Python %PYTHON_VERSION%...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'}" >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        call :fail "Failed to download Python. Check your internet connection."
    )
    echo       Installing Python silently...
    "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        call :fail "Python installation failed."
    )
    call RefreshEnv.cmd >nul 2>&1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    echo       Python installed successfully.
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo       Found Python !PYVER!
    echo       Found Python !PYVER! >> "%LOGFILE%"
)

:: ── Step 2: Virtual environment ───────────────────────────────────────────────
echo.
echo [2/6] Setting up virtual environment...
echo [2/6] Setting up virtual environment... >> "%LOGFILE%"
if exist "%VENV_DIR%" (
    echo       Removing old build environment...
    rmdir /s /q "%VENV_DIR%"
)
python -m venv "%VENV_DIR%" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Failed to create virtual environment."
)
call "%VENV_DIR%\Scripts\activate.bat"
echo       Virtual environment ready.

:: ── Step 3: Install dependencies ─────────────────────────────────────────────
echo.
echo [3/6] Installing dependencies (this may take 2-3 minutes)...
echo [3/6] Installing dependencies... >> "%LOGFILE%"

python -m pip install --upgrade pip >> "%LOGFILE%" 2>&1

echo       Installing requirements.txt...
pip install -r requirements.txt >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Failed to install requirements.txt — see build.log for details."
)

echo       Installing PyInstaller...
pip install pyinstaller >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Failed to install PyInstaller — see build.log for details."
)
echo       Dependencies installed.
echo       Dependencies installed. >> "%LOGFILE%"

:: ── Step 4: PyInstaller bundle ────────────────────────────────────────────────
echo.
echo [4/6] Building application bundle (this takes 3-5 minutes)...
echo [4/6] PyInstaller build starting... >> "%LOGFILE%"
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

pyinstaller meraki_client.spec --noconfirm --clean >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "PyInstaller build failed — open build.log to see the full error."
)
if not exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    call :fail "Build output not found at dist\%APP_NAME%\%APP_NAME%.exe — PyInstaller may have failed silently. Check build.log."
)
echo       Bundle created: dist\%APP_NAME%\
echo       Bundle created. >> "%LOGFILE%"

:: ── Step 5: Inno Setup ────────────────────────────────────────────────────────
echo.
echo [5/6] Checking for Inno Setup...
echo [5/6] Checking for Inno Setup... >> "%LOGFILE%"
if not exist "%INNO_PATH%" (
    echo       Inno Setup not found. Downloading...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%INNO_URL%' -OutFile '%INNO_INSTALLER%'}" >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        call :fail "Failed to download Inno Setup — check internet connection."
    )
    echo       Installing Inno Setup silently...
    "%INNO_INSTALLER%" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        call :fail "Inno Setup installation failed — see build.log."
    )
    timeout /t 5 /nobreak >nul
    if not exist "%INNO_PATH%" (
        call :fail "Inno Setup installed but ISCC.exe not found at: %INNO_PATH% — try installing Inno Setup 6 manually from https://jrsoftware.org/isdl.php"
    )
    echo       Inno Setup installed.
    echo       Inno Setup installed. >> "%LOGFILE%"
) else (
    echo       Inno Setup already installed.
    echo       Inno Setup already installed. >> "%LOGFILE%"
)

:: ── Step 6: Create installer ──────────────────────────────────────────────────
echo.
echo [6/6] Creating Windows installer...
echo [6/6] Running ISCC... >> "%LOGFILE%"
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"
"%INNO_PATH%" installer.iss >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Inno Setup failed to create the installer — open build.log to see the full error."
)

:: ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo ============================================================
echo   BUILD COMPLETE
echo ============================================================
echo.
echo   Installer: %OUTPUT_DIR%\GrayBarMerakiManager-Setup.exe
echo.
echo   Distribute this single file to your end users.
echo   They double-click it, click Next a few times,
echo   and a desktop shortcut is created automatically.
echo.
echo Build completed successfully: %date% %time% >> "%LOGFILE%"

explorer "%OUTPUT_DIR%"
pause
exit /b 0

:: ── Helper: print error, dump tail of log, pause ──────────────────────────────
:fail
echo.
echo [ERROR] %~1
echo [ERROR] %~1 >> "%LOGFILE%"
echo.
echo ── Last lines of build.log ──────────────────────────────────────────────────
powershell -Command "if (Test-Path '%LOGFILE%') { Get-Content '%LOGFILE%' | Select-Object -Last 30 }"
echo ─────────────────────────────────────────────────────────────────────────────
echo.
echo Full log: %LOGFILE%
echo.
pause
exit /b 1
