@echo off
chcp 65001 >nul
title Production Order & Drawing Assembler Web App
echo ========================================================
echo   ระบบจัดชุดเอกสารสำหรับเตรียมผลิต (Production Document Assembler)
echo ========================================================

echo.
echo [1/3] ตรวจสอบ Python ในระบบ...
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [X] ไม่พบ Python ในเครื่อง! กรุณาติดตั้ง Python 3.10 ขึ้นไป
        echo     ดาวน์โหลดได้ที่: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    set PY_CMD=py
) else (
    set PY_CMD=python
)
echo [✓] พบ Python เรียบร้อยแล้ว

echo.
echo [2/3] ตรวจสอบและติดตั้งโมดูลที่ต้องใช้ (Dependencies)...
%PY_CMD% -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo [!] ข้อสังเกต: มีการแจ้งเตือนจาก pip แต่ระบบจะดำเนินการต่อ
)

echo.
echo [3/3] รัน Localhost Server ที่ http://localhost:8088 ...
start "" http://localhost:8088
%PY_CMD% "%~dp0app.py" 8088

pause
