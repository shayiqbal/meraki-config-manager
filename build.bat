@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title GrayBar Meraki Manager - Build Script

:: ── Log file ------------------------------------------------------------------
set "LOGFILE=%~dp0build.log"
echo Build started: %date% %time% > "%LOGFILE%"
echo. >> "%LOGFILE%"
echo Log file: %LOGFILE%

:: ── Require Administrator privileges -----------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    call :fail "This script must be run as Administrator. Right-click build.bat and choose Run as administrator."
)

echo.
echo ============================================================
echo   GrayBar Meraki Manager - Windows Installer Builder
echo ============================================================
echo.

:: ── Configuration ------------------------------------------------------------
set APP_NAME=GrayBarMerakiManager
set PYTHON_VERSION=3.12.9
set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe
set PYTHON_INSTALLER=%TEMP%\python-installer.exe
set INNO_VERSION=6.7.3
set INNO_URL=https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe
set INNO_INSTALLER=%TEMP%\innosetup-6.7.3.exe
set INNO_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
set INNO_PATH_64=C:\Program Files\Inno Setup 6\ISCC.exe
set VENV_DIR=.build_venv
set OUTPUT_DIR=Output

:: ── Check for internet connectivity ------------------------------------------
ping -n 1 www.python.org >nul 2>&1
if errorlevel 1 (
    call :fail "No internet connection detected. Please connect to the internet and try again."
)

:: ── Step 1: Python -----------------------------------------------------------
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

:: ── Step 2: Virtual environment ----------------------------------------------
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

:: ── Step 3: Install dependencies ---------------------------------------------
echo.
echo [3/6] Installing dependencies (this may take 2-3 minutes)...
echo [3/6] Installing dependencies... >> "%LOGFILE%"

python -m pip install --upgrade pip >> "%LOGFILE%" 2>&1
timeout /t 3 /nobreak >nul

echo       Installing requirements.txt...
python -m pip install -r requirements.txt >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Failed to install requirements.txt - see build.log for details."
)

echo       Installing PyInstaller...
python -m pip install pyinstaller >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Failed to install PyInstaller - see build.log for details."
)
echo       Dependencies installed.
echo       Dependencies installed. >> "%LOGFILE%"

:: ── Step 4: PyInstaller bundle -----------------------------------------------
echo.
echo [4/6] Building application bundle (this takes 3-5 minutes)...
echo [4/6] PyInstaller build starting... >> "%LOGFILE%"
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
timeout /t 3 /nobreak >nul

python -m PyInstaller meraki_client.spec --noconfirm --clean >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "PyInstaller build failed - open build.log to see the full error."
)
if not exist "dist\%APP_NAME%\%APP_NAME%.exe" (
    call :fail "Build output not found at dist\%APP_NAME%\%APP_NAME%.exe - check build.log."
)
echo       Bundle created: dist\%APP_NAME%\
echo       Bundle created. >> "%LOGFILE%"

:: ── Step 5: Inno Setup -------------------------------------------------------
echo.
echo [5/6] Checking for Inno Setup...
echo [5/6] Checking for Inno Setup... >> "%LOGFILE%"

:: Resolve ISCC.exe - check x86 and x64 Program Files
call :find_iscc
if "!ISCC_EXE!"=="" (
    echo       Inno Setup not found. Installing via winget...
    echo       Attempting winget install... >> "%LOGFILE%"
    winget install --id JRSoftware.InnoSetup -e -s winget --silent --accept-package-agreements --accept-source-agreements
    echo       Waiting for install to complete...
    timeout /t 15 /nobreak >nul
    call :find_iscc
)

if "!ISCC_EXE!"=="" (
    echo       winget did not place ISCC.exe - downloading installer directly...
    echo       Downloading: %INNO_URL% >> "%LOGFILE%"
    powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -Uri '%INNO_URL%' -OutFile '%INNO_INSTALLER%'}" >> "%LOGFILE%" 2>&1
    if errorlevel 1 (
        call :fail "Failed to download Inno Setup from GitHub. Check your internet connection."
    )
        echo       Installing Inno Setup silently...
        "%INNO_INSTALLER%" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES "/DIR=%ProgramFiles(x86)%\Inno Setup 6"
        echo       Waiting for install to complete...
    timeout /t 15 /nobreak >nul
    call :find_iscc
)

if "!ISCC_EXE!"=="" (
    call :fail "Inno Setup could not be found after install. Install it manually from https://jrsoftware.org/isdl.php then re-run."
)

echo       Inno Setup found: !ISCC_EXE!
echo       Inno Setup found: !ISCC_EXE! >> "%LOGFILE%"

:: ── Step 6: Create installer -------------------------------------------------
echo.
echo [6/6] Creating Windows installer...
echo [6/6] Running ISCC... >> "%LOGFILE%"
if exist "%OUTPUT_DIR%" rmdir /s /q "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%"
"!ISCC_EXE!" installer.iss >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    call :fail "Inno Setup failed to create the installer - open build.log to see the full error."
)

:: ── Done ---------------------------------------------------------------------
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

:: ── Subroutine: find ISCC.exe in standard locations --------------------------
:find_iscc
set "ISCC_EXE="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    goto :eof
)
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    goto :eof
)
for /f "delims=" %%i in ('where ISCC.exe 2^>nul') do (
    set "ISCC_EXE=%%i"
    goto :eof
)
for /f "delims=" %%i in ('dir /s /b "%ProgramFiles(x86)%\ISCC.exe" 2^>nul') do (
    set "ISCC_EXE=%%i"
    goto :eof
)
for /f "delims=" %%i in ('dir /s /b "%ProgramFiles%\ISCC.exe" 2^>nul') do (
    set "ISCC_EXE=%%i"
    goto :eof
)
goto :eof

:: ── Subroutine: print error, dump log tail, pause, EXIT WHOLE SCRIPT ---------
:fail
echo.
echo [ERROR] %~1
echo [ERROR] %~1 >> "%LOGFILE%"
echo.
echo ---- Last 30 lines of build.log ----------------------------------------
powershell -Command "if (Test-Path '%LOGFILE%') { Get-Content '%LOGFILE%' | Select-Object -Last 30 }"
echo ------------------------------------------------------------------------
echo.
echo Full log: %LOGFILE%
echo.
pause
exit 1
