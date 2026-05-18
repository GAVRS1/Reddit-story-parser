@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    goto error
)

call ".venv\Scripts\activate.bat"
python reddit_story_parser.py --config config.json
if errorlevel 1 goto error

goto end

:error
echo.
echo Parser failed.
pause
exit /b 1

:end
pause
endlocal
