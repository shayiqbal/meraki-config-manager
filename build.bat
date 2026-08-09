@echo off
setlocal EnableDelayedExpansion
title GrayBar Meraki Manager — Build Script

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
set INNO_URL=https://jrsoftware.org/download.php/is.exe
set INNO_INSTALLER=%TEMP%\innosetup-installer.exe
set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
set VENV_DIR=.build_venv
set OUTPUT_DIR=Output

:: ── Check for internet connectivity ──────────────────────────────────────────
ping -n 1 www.python.org >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No internet connection detected.
    echo         Please connect to the internet and try again.
    pause & exit /b 1
)

:: ── Step 1: Python ────────────────────────────────────────────────────────────
echo [1/6] Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo       Python not found. Downloading Python %PYTHON_VERSION%...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'}"
    if errorlevel 1 (
        echo [ERROR] Failed to download Python. Check your internet connection.
        pause & exit /b 1
    )
    echo       Installing Python silently...
    "%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    if errorlevel 1 (
        echo [ERROR] Python installation failed.
        pause & exit /b 1
    )
    :: Refresh PATH so python is found in this session
    call RefreshEnv.cmd >nul 2>&1
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
    echo       Python installed successfully.
) else (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo       Found Python !PYVER!
)

:: ── Step 2: Virtual environment ───────────────────────────────────────────────
echo.
echo [2/6] Setting up virtual environment...
if exist "%VENV_DIR%" (
    echo       Removing old build environment...
    rmdir /s /q "%VENV_DIR%"
)
python -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause & exit /b 1
)
call "%VENV_DIR%\Scripts\activate.bat"
echo       Virtual environment ready.

:: ── Step 3: Install dependencies ─────────────────────────────────────────────
echo.
echo [3/6] Installing dependencies (this may take 2-3 minutes)...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install requirements.
    pause & exit /b 1
)
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause & exit /b 1
)
echo       Dependencies installed.

:: ── Step 4: PyInstaller bundle ────────────────────────────────────────────────
echo.
echo [4/6] Building application bundle (this takes 3-5 minutes)...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
pyinstaller meraki_client.spec --noconfirm --clean
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed. See errors above.
    pause & exit /b 1
)
if not exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    echo [ERROR] Build output not found. PyInstaller may have failed silently.
    pause & exit /b 1
)
echo       Bundle created: dist\%APP_NAME%\

:: ── Step 5: Inno Setup ────────────────────────────────────────────────────────
echo.
echo [5/6] Checking for Inno Setup...
if not exist "%INNO_PATH%" (
    echo       Inno Setup not found. Downloading...
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%INNO_URL%' -OutFile '%INNO_INSTALLER%'}"
    if errorlevel 1 (
        echo [ERROR] Failed to download Inno Setup.
        pause & exit /b 1
    )
    echo       Installing Inno Setup silently...
    "%INNO_INSTALLER%" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
    if errorlevel 1 (
        echo [ERROR] Inno Setup installation failed.
        pause & exit /b 1
    )
    echo       Inno Setup installed.
) else (
    echo       Inno Setup already installed.
)

:: ── Step 6: Create installer ──────────────────────────────────────────────────
echo.
echo [6/6] Creating Windows installer...
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"
"%INNO_PATH%" installer.iss
if errorlevel 1 (
    echo [ERROR] Inno Setup failed to create the installer.
    pause & exit /b 1
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

:: Open the Output folder in Explorer
explorer "%OUTPUT_DIR%"

pause
