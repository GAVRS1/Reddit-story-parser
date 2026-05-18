@echo off
setlocal
cd /d "%~dp0"

echo Checking Python ...
where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.11+ and enable "Add python.exe to PATH".
    goto error
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Python 3.11 or newer is required.
    python --version
    goto error
)

if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 goto error
) else (
    echo Virtual environment already exists.
)

call ".venv\Scripts\activate.bat"

echo Upgrading pip ...
python -m pip install --upgrade pip
if errorlevel 1 goto error

echo Installing dependencies ...
python -m pip install -r requirements.txt
if errorlevel 1 goto error

echo.
echo Dependencies are installed.
echo Next step: run run_app.bat
goto end

:error
echo.
echo Dependency installation failed.
pause
exit /b 1

:end
pause
endlocal
