@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment was not found. Run install_dependencies.bat first.
    goto error
)

call ".venv\Scripts\activate.bat"

echo Building RedditStoryParser.exe ...
python -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name RedditStoryParser ^
    --add-data "config.json;." ^
    reddit_story_app.py
if errorlevel 1 goto error

echo.
echo Build complete: dist\RedditStoryParser\RedditStoryParser.exe
echo To build the installer, run build_installer.bat.
goto end

:error
echo.
echo EXE build failed. Read the error above and try again.
pause
exit /b 1

:end
pause
endlocal
