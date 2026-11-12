@echo off
setlocal enabledelayedexpansion
title CIT Voice Studio - Ban GPU (NVIDIA CUDA)
cd /d "%~dp0"

echo ================================================================
echo         CIT Voice Studio - BAN GPU (NVIDIA CUDA)
echo         Tac gia: Cuong IT (https://me.cuongit.net)
echo         Phat trien dua tren: VieNeu-TTS (Pham Nguyen Ngoc Bao)
echo ================================================================
echo.
echo  [Ban nay danh cho may CO CARD NVIDIA]
echo    * Chay v3 Turbo bang PyTorch/CUDA thay vi ONNX tren CPU
echo    * Gop lo ca kich ban - nhanh vuot troi o che do Hoi thoai/Podcast
echo.
echo  [LUU Y QUAN TRONG]
echo    * Lan cai dau phai tai khoang 3.5 GB (thu vien torch CUDA).
echo    * Bat buoc co Internet va con trong it nhat 12 GB o dia.
echo    * May KHONG co card NVIDIA thi dung run_desktop_app.bat thay vi file nay.
echo.
echo ================================================================
echo.

:: 1. Kiem tra co card NVIDIA that khong truoc khi tai 3.5 GB
where nvidia-smi >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Khong tim thay nvidia-smi - co ve may nay khong co card NVIDIA
    echo     hoac chua cai driver.
    echo.
    echo     Neu chac chan may co card NVIDIA, hay cai driver moi nhat roi chay lai.
    echo     Neu khong co card NVIDIA, hay dung run_desktop_app.bat ^(ban CPU^).
    echo.
    set /p "ans=Van muon tiep tuc tai 3.5 GB? [y/N] "
    if /i not "!ans!"=="y" goto END
) else (
    echo [+] Da phat hien card NVIDIA:
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo.
)

:: 2. Kiem tra moi truong .venv (phai chay duoc that, khong chi ton tai file)
if not exist ".venv\Scripts\python.exe" goto SETUP
".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
if not errorlevel 1 goto CHECK_TORCH

echo [!] Moi truong .venv hong (thuong do copy .venv tu may khac). Dang xoa va tao lai...
rmdir /s /q ".venv"

:SETUP
echo [+] Dang chuan bi moi truong...

:: 3. Kiem tra uv
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [+] Dang cai dat uv...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%APPDATA%\uv;%LOCALAPPDATA%\uv;%PATH%"
)

where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Khong tim thay cong cu uv va khong the tu dong cai dat.
    goto ERROR
)

:CHECK_TORCH
:: 4. Da co torch CUDA chua? Co roi thi bo qua buoc tai 3.5 GB.
".venv\Scripts\python.exe" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if not errorlevel 1 (
    echo [+] Moi truong GPU da san sang, bo qua buoc cai dat.
    goto LAUNCH
)

echo.
echo [+] Dang cai dat thu vien GPU (torch CUDA ~3.5 GB)...
echo     Buoc nay lau, vui long khong dong cua so.
echo.
uv sync --frozen --group gpu-app --group desktop
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Cai dat that bai. Kiem tra ket noi mang va dung luong o dia.
    goto ERROR
)

:: 5. Xac nhan torch thuc su thay card
".venv\Scripts\python.exe" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] Da cai torch nhung KHONG thay card NVIDIA.
    echo     Thuong do driver qua cu. Hay cap nhat driver NVIDIA roi chay lai.
    echo     Ung dung van chay duoc bang CPU.
    echo.
    pause
)

:LAUNCH
:: Giai phong port 8001 neu dang bi chiem dung
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING 2^>nul') do (
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo ================================================================
echo  [+] Dang khoi dong CIT Voice Studio (ban GPU)...
echo  [+] Dia chi: http://127.0.0.1:8001
echo ================================================================
echo.

start http://127.0.0.1:8001
".venv\Scripts\python.exe" -m apps.web_stream

if %errorlevel% neq 0 goto ERROR
goto END

:ERROR
echo.
echo ================================================================
echo  [ERROR] Co loi xay ra khi chay ban GPU!
echo ================================================================
pause
exit /b 1

:END
pause
