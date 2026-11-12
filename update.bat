@echo off
setlocal enabledelayedexpansion
title CIT Voice Studio - Cap nhat
cd /d "%~dp0"

echo ================================================================
echo            CIT Voice Studio - Cap nhat phien ban moi
echo ================================================================
echo.

where git >nul 2>&1
if %errorlevel% equ 0 (
    echo [+] Dang cap nhat ma nguon tu GitHub (git pull)...
    git pull
) else (
    echo [!] Khong tim thay Git, bo qua git pull.
)

echo.
echo [+] Dang dong bo thu vien voi uv sync...
where uv >nul 2>&1
if %errorlevel% equ 0 (
    uv sync --frozen --group desktop
) else (
    if exist ".venv\Scripts\python.exe" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
        set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%APPDATA%\uv;%LOCALAPPDATA%\uv;%PATH%"
        uv sync --frozen --group desktop
    )
)

echo.
echo ================================================================
echo  [+] Cap nhat hoan tat! Nhan phim bat ky de thoat.
echo ================================================================
pause
