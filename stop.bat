@echo off
setlocal enabledelayedexpansion
title CIT Voice Studio - Dung ung dung
cd /d "%~dp0"

echo ================================================================
echo         CIT Voice Studio - Free Vietnamese Text-to-Speech
echo         Tac gia: Cuong IT (https://me.cuongit.net)
echo         Phat trien dua tren: VieNeu-TTS (Pham Nguyen Ngoc Bao)
echo ================================================================
echo.
echo [+] Dang tim va dong cac tien trinh CIT Voice Studio dang chay...
echo.

set "STOPPED=0"

:: Dong tien trinh dang lang nghe tren Port 8001 (may chu cua ung dung)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    set "STOPPED=1"
    echo [+] Dang dong tien trinh CIT Voice Studio tren Port 8001 (PID: %%a)...
    taskkill /f /pid %%a >nul 2>&1
)

echo.
if "!STOPPED!"=="1" (
    echo ================================================================
    echo  [+] Da dong thanh cong tat ca tien trinh CIT Voice Studio!
    echo ================================================================
) else (
    echo [i] Khong tim thay tien trinh CIT Voice Studio nao dang chay.
)
echo.
pause
