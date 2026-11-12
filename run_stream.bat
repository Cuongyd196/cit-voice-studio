@echo off
setlocal enabledelayedexpansion
title VieNeu-TTS - Web Streaming (Realtime)
cd /d "%~dp0"

echo ================================================================
echo       VieNeu-TTS - Web Streaming Realtime (FastAPI)
echo ================================================================
echo.

:: Kiem tra .venv chay duoc that, khong chi ton tai file
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo [!] Moi truong .venv hong ^(thuong do copy .venv tu may khac^). Dang xoa va tao lai...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo [!] Khong tim thay moi truong .venv.
    echo [+] Dang dong bo thu vien voi uv sync...
    uv sync --frozen --group desktop
    if %errorlevel% neq 0 (
        echo [ERROR] uv sync that bai.
        pause
        exit /b 1
    )
)

echo [+] Dang khoi dong Web Streaming tai: http://localhost:8001
echo [+] Trinh duyet se tu dong mo...
start http://localhost:8001

".venv\Scripts\python.exe" -m apps.web_stream

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Co loi xay ra khi chay Web Streaming!
    pause
    exit /b 1
)

pause
