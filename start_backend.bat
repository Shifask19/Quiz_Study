@echo off
title SnapStudy Backend
color 0A
echo.
echo  ===================================================
echo    SnapStudy -- Private AI Tutor, On-Device
echo    Backend starting on http://localhost:8000
echo  ===================================================
echo.
cd /d "%~dp0"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
pause
