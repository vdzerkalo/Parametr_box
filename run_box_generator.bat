@echo off
REM ASCII-only launcher. Self-heals a missing/broken .venv by rebuilding it
REM from the system Python (py launcher) - a stable base that won't vanish.
setlocal EnableExtensions
cd /d "%~dp0"
set "VENV=.venv"
set "PYEXE=%VENV%\Scripts\python.exe"

echo ============================================
echo   Autonomous Box Generator
echo   %CD%
echo ============================================

REM --- 1. Validate the venv; rebuild if missing or broken ---
if not exist "%PYEXE%" goto SETUP
"%PYEXE%" -c "import PySide6" 1>nul 2>nul
if errorlevel 1 (
    echo [info] .venv is broken or incomplete - rebuilding it...
    goto SETUP
)
goto RUN

:SETUP
echo [setup] Creating a fresh Python environment in .venv ...
if exist "%VENV%" rmdir /s /q "%VENV%"
call :MAKE_VENV
if not exist "%PYEXE%" (
    echo.
    echo [ERROR] Could not create .venv. Install Python 3.12 from https://python.org
    echo         ^(tick "Add to PATH"^), then run this file again.
    echo.
    pause
    exit /b 1
)
echo [setup] Installing dependencies ^(one-time, ~1-2 min^) ...
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Dependency install failed - see messages above.
    echo.
    pause
    exit /b 1
)
goto RUN

:MAKE_VENV
py -3.12 -m venv "%VENV%" 2>nul && exit /b 0
py -3.13 -m venv "%VENV%" 2>nul && exit /b 0
py -3.11 -m venv "%VENV%" 2>nul && exit /b 0
py -3 -m venv "%VENV%" 2>nul && exit /b 0
python -m venv "%VENV%" 2>nul && exit /b 0
exit /b 1

:RUN
echo [run] Starting application...
echo.
"%PYEXE%" main.py
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" (
    echo ====================================================
    echo [ERROR] Application exited with code %RC%.
    echo The error text is shown above - please copy and send it.
    echo ====================================================
    echo.
    pause
)
endlocal
