@echo off
setlocal
title CIT Voice Studio - Dong goi Installer
cd /d "%~dp0.."

echo ================================================================
echo   CIT Voice Studio - Tao file cai dat (Setup.exe)
echo ================================================================
echo.

:: Phai co ban .exe truoc. Installer chi dong goi, khong build lai.
if not exist "dist\CIT-Voice-Studio\CIT-Voice-Studio.exe" (
    echo [ERROR] Chua co dist\CIT-Voice-Studio\CIT-Voice-Studio.exe
    echo         Chay build_desktop_exe.bat truoc.
    if not "%1"=="--no-pause" pause
    exit /b 1
)

:: Don file app sinh ra khi chay thu exe trong dist (log, chan doan, bo GPU tu
:: cai), de ca ban zip nen tu dist cung sach. installer.iss con loai them lan nua.
set "APPDIR=dist\CIT-Voice-Studio"
for %%F in (cit-voice-studio.log chan-doan.txt gpu-selftest.txt kokoro-selftest.txt) do (
    if exist "%APPDIR%\%%F" del /f /q "%APPDIR%\%%F"
)
for %%D in (gpu_venv addons) do (
    if exist "%APPDIR%\%%D" (
        echo [+] Xoa %%D con sot tu lan chay thu...
        rmdir /s /q "%APPDIR%\%%D"
    )
)

:: Trang dieu khoan cua trinh cai (Inno can file .txt co BOM).
".venv\Scripts\python.exe" scripts\make_terms_txt.py || (echo [ERROR] Khong tao duoc build\DIEU-KHOAN.txt & exit /b 1)

:: Tim ISCC.exe. Inno Setup cai theo kieu user nam trong LOCALAPPDATA, cai theo
:: kieu may nam trong Program Files - kiem tra ca hai.
set "ISCC="
for %%P in (
    "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
) do (
    if exist "%%~P" if not defined ISCC set "ISCC=%%~P"
)

if not defined ISCC (
    echo [ERROR] Khong tim thay Inno Setup.
    echo         Cai bang lenh:  winget install JRSoftware.InnoSetup
    if not "%1"=="--no-pause" pause
    exit /b 1
)

echo [+] Dung: %ISCC%
echo [+] Dang dong goi thanh Setup.exe... buoc nay mat vai phut, hay doi.
echo.

"%ISCC%" scripts\installer.iss
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Dong goi that bai.
    if not "%1"=="--no-pause" pause
    exit /b 1
)

echo.
echo ================================================================
echo  [SUCCESS] Xong.
echo.
echo  File gui cho khach - CHI MOT FILE DUY NHAT:
echo    ^> dist\CIT-Voice-Studio-v^<version^>-win-x86_64.exe  (version lay tu AppVersion trong scripts\installer.iss)
echo.
echo  Khach bam dup vao do la cai duoc, khong can giai nen gi ca.
echo ================================================================
if not "%1"=="--no-pause" pause
