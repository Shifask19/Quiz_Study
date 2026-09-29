@echo off
title SnapStudy Frontend
color 0B
echo.
echo  ===================================================
echo    SnapStudy -- Frontend dev server
echo    Opening at http://localhost:5173
echo  ===================================================
echo.
cd /d "%~dp0\frontend"
npm run dev
pause
