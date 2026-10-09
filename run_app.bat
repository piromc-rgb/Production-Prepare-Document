@echo off
title Production Order & Drawing Assembler Web App
echo ===================================================
echo  Starting Web App at http://localhost:8088
echo ===================================================
start http://localhost:8088
python "%~dp0app.py" 8088
pause
