@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    goto error
)

call ".venv\Scripts\activate.bat"

echo Starting Reddit Story Parser ...
python reddit_story_app.py
if errorlevel 1 goto error

goto end

:error
echo.
echo The app did not start. Read the error above and try again.
pause
exit /b 1

:end
endlocal
