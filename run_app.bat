@echo off
chcp 65001 >nul
title Production Order & Drawing Assembler Web App
echo ========================================================
echo   ระบบจัดชุดเอกสารสำหรับเตรียมผลิต (Production Document Assembler)
echo ========================================================
echo.

set "PY_CMD="

:: 1. ตรวจสอบ python ใน PATH ว่าทำงานได้จริงหรือไม่ (ไม่ติด Windows Store stub)
python -c "import sys; sys.exit(0)" >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
    goto :PYTHON_FOUND
)

:: 2. ตรวจสอบ py launcher
py -c "import sys; sys.exit(0)" >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py"
    goto :PYTHON_FOUND
)

:: 3. ตรวจสอบโฟลเดอร์ติดตั้งมาตรฐานในเครื่อง
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        %%P -c "import sys; sys.exit(0)" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PY_CMD=%%~P"
            goto :PYTHON_FOUND
        )
    )
)

:: 4. กรณีไม่พบ Python ในเครื่องเลย
echo [X] ไม่พบโปรแกรม Python บนเครื่องคอมพิวเตอร์ของคุณ
echo.
echo ระบบนี้จำเป็นต้องใช้ Python 3.10 ขึ้นไป เพื่อประมวลผลจัดชุดเอกสาร PDF
echo.
echo กรุณาเลือกวิธีดำเนินการ:
echo   [1] ติดตั้ง Python 3.12 อัตโนมัติ (ผ่าน Windows Package Manager / winget)
echo   [2] เปิดหน้าเว็บดาวน์โหลด Python (python.org)
echo   [3] ใช้งานบนคลาวด์ฟรีผ่าน GitHub Codespaces (ไม่ต้องติดตั้งโปรแกรม)
echo   [0] ออกจากโปรแกรม
echo.
set /p "INSTALL_CHOICE=พิมพ์หมายเลข [1, 2, 3 หรือ 0] แล้วกด Enter: "

if "%INSTALL_CHOICE%"=="1" (
    echo.
    echo [*] กำลังติดตั้ง Python 3.12 ผ่าน winget กรุณารอสักครู่...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    if %errorlevel% equ 0 (
        echo [✓] ติดตั้ง Python เรียบร้อยแล้ว! กรุณาปิดหน้าต่างนี้แล้วดับเบิลคลิก run_app.bat ใหม่อีกครั้ง
    ) else (
        echo [!] การติดตั้งผ่าน winget ไม่สำเร็จ กำลังเปิดหน้าเว็บดาวน์โหลดให้แทน...
        start https://www.python.org/downloads/
    )
    pause
    exit /b 0
)

if "%INSTALL_CHOICE%"=="2" (
    echo.
    echo [*] กำลังเปิดหน้าเว็บดาวน์โหลด Python...
    echo ** ข้อสำคัญ: ขณะติดตั้ง ให้ทำเครื่องหมายถูกที่ช่อง "Add python.exe to PATH" ด้วย **
    start https://www.python.org/downloads/
    pause
    exit /b 0
)

if "%INSTALL_CHOICE%"=="3" (
    echo.
    echo [*] กำลังเปิดใช้งานบน GitHub Codespaces (Cloud ฟรี)...
    start https://codespaces.new/piromc-rgb/Production-Prepare-Document
    exit /b 0
)

exit /b 1

:PYTHON_FOUND
echo [1/3] ตรวจสอบ Python: พร้อมใช้งานแล้ว
%PY_CMD% -c "import sys; print(f'      เวอร์ชัน: {sys.version.split()[0]} ({sys.executable})')"

echo.
echo [2/3] ตรวจสอบและติดตั้งโมดูลที่ต้องใช้ (Dependencies)...
%PY_CMD% -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo [!] กำลังลองติดตั้งด้วยสิทธิ์ผู้ใช้ (--user)...
    %PY_CMD% -m pip install --user -r "%~dp0requirements.txt"
)

echo.
echo [3/3] เริ่มการทำงานของ Web Server ที่ http://localhost:8088 ...
echo ========================================================
echo  * กำลังเปิดหน้าเว็บที่เบราว์เซอร์อัตโนมัติ...
echo  * หากต้องการปิดระบบ ให้ปิดหน้าต่างคอนโซลนี้ได้เลยครับ
echo ========================================================
echo.

%PY_CMD% "%~dp0app.py" 8088

pause
