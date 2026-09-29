@echo off
title SnapStudy Setup
color 0E
echo.
echo  ===================================================
echo    SnapStudy -- First-time Setup
echo  ===================================================
echo.

cd /d "%~dp0"

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 ( echo ERROR: pip install failed & pause & exit /b 1 )

echo.
echo [2/4] Building frontend...
cd frontend
call npm install
if %errorlevel% neq 0 ( echo ERROR: npm install failed & pause & exit /b 1 )
call npm run build
if %errorlevel% neq 0 ( echo ERROR: npm build failed & pause & exit /b 1 )
cd ..

echo.
echo [3/4] Initialising database and loading demo data...
python scripts\create_demo_data.py
if %errorlevel% neq 0 ( echo WARNING: Demo data load failed - you can load it from the app )

echo.
echo [4/4] Setup complete!
echo.
echo  To start SnapStudy:
echo    Double-click start_backend.bat
echo    Then open http://localhost:8000 in your browser
echo.
echo  For live frontend development (optional):
echo    Double-click start_frontend.bat
echo    Then open http://localhost:5173
echo.
pause
