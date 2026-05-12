@echo off
setlocal
cd /d "%~dp0"
python reddit_story_parser.py --config config.json
pause
