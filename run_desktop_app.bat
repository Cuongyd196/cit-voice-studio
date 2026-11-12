@echo off
setlocal enabledelayedexpansion
title CIT Voice Studio - Desktop App
cd /d "%~dp0"

echo ================================================================
echo       CIT Voice Studio - Desktop App (PyWebView + VieNeu-TTS)
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

:: Dong bo LUON, khong chi khi thieu .venv: mot .venv tao boi lenh uv sync tron khong
:: co pywebview, khi do app im lang roi xuong trinh duyet thay vi mo cua so rieng.
echo [+] Dang dong bo thu vien voi uv sync...
uv sync --frozen --group desktop
if %errorlevel% neq 0 (
    echo [ERROR] uv sync that bai. Kiem tra mang, tat VPN/proxy roi chay lai.
    pause
    exit /b 1
)

:: Desktop launcher tu chon cong trong, khong tat phien dang chay.

echo [+] Dang mo ung dung Desktop CIT Voice Studio...
".venv\Scripts\python.exe" -m apps.desktop_app

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Co loi xay ra khi chay Desktop App!
    pause
    exit /b 1
)
