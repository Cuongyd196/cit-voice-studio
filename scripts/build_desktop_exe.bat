@echo off
setlocal enabledelayedexpansion
title Build CIT Voice Studio Standalone Desktop App (.exe)
cd /d "%~dp0.."

echo ================================================================
echo       DONG GOI CIT VOICE STUDIO THANH FILE DESKTOP .EXE
echo       Tac gia: Cuong IT (https://me.cuongit.net)
echo ================================================================
echo.

:: 1. Build giao dien React moi nhat
echo [+] Buoc 1/3: Dang build giao dien React Frontend...
cd app-desktop\cit-voice-app
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] Build Frontend that bai!
    cd ..\..
    if not "%1"=="--no-pause" pause
    exit /b 1
)
cd ..\..

:: 2. Kiem tra va cai dat cong cu dong goi
::    pywebview nam trong nhom `desktop` cua pyproject (co trong uv.lock), khong con
::    cai le bang pip nua - truoc day no chi ton tai tren may build, nen ban source
::    tai ve khong bao gio mo duoc cua so rieng.
::    pyinstaller la cong cu BUILD, khong phai phu thuoc runtime -> van cai rieng.
::    pillow: chi make_splash.py can (ve man hinh khoi dong); truoc day co san nho
::    gradio keo theo, bo gradio thi phai cai tuong minh.
echo.
echo [+] Buoc 2/3: Kiem tra cac cong cu dong goi (PyInstaller, PyWebView)...
uv sync --frozen --group desktop
if %errorlevel% neq 0 (
    echo [ERROR] uv sync that bai.
    if not "%1"=="--no-pause" pause
    exit /b 1
)
uv pip install pyinstaller pillow
if %errorlevel% neq 0 (
    echo [!] Thu cai dat bang pip thong thuong...
    ".venv\Scripts\python.exe" -m pip install pyinstaller pillow
)

:: Kem cong cu nho gon; torch/CUDA chi tai khi nguoi dung chon GPU.
set "CIT_UV_EXE="
for /f "delims=" %%U in ('where uv.exe') do if not defined CIT_UV_EXE set "CIT_UV_EXE=%%U"
if not defined CIT_UV_EXE (
    echo [ERROR] Khong tim thay uv.exe de dong goi bo cai GPU.
    exit /b 1
)

:: 3. Dong goi thanh file chay Desktop .exe
:: Ve splash theo phien ban ung dung hien tai.
".venv\Scripts\python.exe" assets\brand\make_splash.py
if %errorlevel% neq 0 (
    echo [ERROR] Khong tao duoc man hinh khoi dong.
    exit /b 1
)
echo.
echo [+] Buoc 3/3: Dang tien hanh dong goi thanh thu muc dist/CIT-Voice-Studio...

:: Dong ung dung neu dang chay de tranh bi lock file
taskkill /f /im CIT-Voice-Studio.exe >nul 2>&1

:: Don dep va tao truoc thu muc build de tranh loi FileNotFoundError
if exist "build" rmdir /s /q "build" >nul 2>&1
if not exist "build\CIT-Voice-Studio" mkdir "build\CIT-Voice-Studio"

:: LUU Y ve danh sach --collect-all duoi day:
::  - pythonnet: hook mac dinh cua PyInstaller CHI gom Python.Runtime.dll (1/99 file),
::    thieu netstandard.dll va cac facade netstandard2.0. May nao co .NET Framework
::    cu hon 4.7.2 se bao "Failed to resolve Python.Runtime.Loader.Initialize".
::  - kaldi_native_fbank: giau DLL native trong thu muc lib\, can cho Voice Cloning.
::  - librosa: nap submodule kieu lazy (librosa.effects), thieu thi mat chinh toc do.
::
:: --manifest assets\app.manifest: khai bao exe DPI-aware ngay tu dau. Thieu no, man
:: hinh cho --splash hien o che do DPI-unaware (phong to, can giua theo pixel logic),
:: roi khi webview.start() goi SetProcessDPIAware() thi no co lai 520x300 va nhay len
:: goc tren truoc khi cua so chinh hien. Manifest nay THAY ban mac dinh cua PyInstaller,
:: nen giu supportedOS + longPathAware trong do.
".venv\Scripts\pyinstaller.exe" --clean --noconfirm --onedir --windowed ^
    --name "CIT-Voice-Studio" ^
    --paths "src" ^
    --add-binary "%CIT_UV_EXE%;tools" ^
    --exclude-module "torch" ^
    --exclude-module "torchaudio" ^
    --exclude-module "transformers" ^
    --add-data "docs\cit-voice-studio.md;." ^
    --add-data "DIEU-KHOAN.md;." ^
    --add-data "app-desktop/cit-voice-app/dist;app-desktop/cit-voice-app/dist" ^
    --collect-all "onnxruntime" ^
    --collect-all "sea_g2p" ^
    --collect-all "soundfile" ^
    --collect-all "tokenizers" ^
    --collect-all "vieneu" ^
    --collect-all "vieneu_utils" ^
    --collect-all "pypdf" ^
    --collect-all "webview" ^
    --collect-all "pythonnet" ^
    --collect-all "clr_loader" ^
    --collect-all "kaldi_native_fbank" ^
    --collect-all "soxr" ^
    --collect-all "librosa" ^
    --collect-all "huggingface_hub" ^
    --hidden-import "unittest.mock" ^
    --hidden-import "numpy.typing" ^
    --hidden-import "numpy.lib.stride_tricks" ^
    --collect-submodules "joblib" ^
    --collect-submodules "apps._kokoro_torch" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    --hidden-import "clr" ^
    --hidden-import "pythonnet" ^
    --icon "assets\icons\icon.ico" ^
    --splash "assets\splash.png" ^
    --manifest "assets\app.manifest" ^
    apps/desktop_app.py


if %errorlevel% neq 0 (
    echo.
    echo ================================================================
    echo  [ERROR] Dong goi that bai! Vui long kiem tra log loi o tren.
    echo ================================================================
    if not "%1"=="--no-pause" pause
    exit /b 1
)

:: 4. Chep mo hinh kem san canh file .exe (neu co)
::    Chep THEO DANH SACH trong apps\model_catalog.py (Turbo int8 + codec MOSS,
::    ~312 MB), khong chep ca thu muc models\: truoc day robocopy chep moi thu trong
::    cache may dev tru vai thu muc da biet, nen ban 1.0.1 suyt mang theo ~650 MB mo
::    hinh Kokoro cua nhanh khac. Giong nhan ban cua may dev (custom_voices_*.json,
::    giong nguoi that) cung khong bao gio lot vao. Mo hinh khac (Nano, fp32) nguoi
::    dung tai trong Cai dat.
if exist "models\hf_cache" (
    echo.
    echo [+] Dang chep mo hinh VieNeu-TTS-v3-Turbo int8 vao ban dong goi...
    ".venv\Scripts\python.exe" scripts\copy_release_models.py "dist\CIT-Voice-Studio\models"
    if !errorlevel! neq 0 (
        echo [ERROR] Chep mo hinh that bai.
        if not "%1"=="--no-pause" pause
        exit /b 1
    )
) else (
    echo.
    echo [!] Khong thay models\hf_cache - ban dong goi se phai tai mo hinh lan dau.
    echo     Muon kem san: chay "python scripts\fetch_models.py" roi build lai.
)

:: 4b. Chep cong cu chan doan sang canh .exe
::     Ban --windowed khong co console, nen khi may khach loi thi day la cach duy
::     nhat lay duoc thong tin ve.
copy /y "packaging\windows\chan-doan.bat" "dist\CIT-Voice-Studio\" >nul 2>&1
copy /y "packaging\windows\chan-doan.ps1" "dist\CIT-Voice-Studio\" >nul 2>&1
:: Apache 2.0 buoc kem ban LICENSE khi PHAT HANH LAI, ke ca phat hanh dang nhi
:: phan (dieu 4a). NOTICE ghi cong tac gia goc VieNeu-TTS (dieu 4d).
copy /y "LICENSE" "dist\CIT-Voice-Studio\" >nul 2>&1
copy /y "NOTICE" "dist\CIT-Voice-Studio\" >nul 2>&1
:: Giay phep cac thu vien di kem (co LGPL cua bo ma MP3) va tuyen bo quyen rieng tu.
copy /y "THIRD-PARTY-NOTICES.md" "dist\CIT-Voice-Studio\" >nul 2>&1
copy /y "PRIVACY.md" "dist\CIT-Voice-Studio\" >nul 2>&1
copy /y "DIEU-KHOAN.md" "dist\CIT-Voice-Studio\" >nul 2>&1
copy /y "docs\cit-voice-studio.md" "dist\CIT-Voice-Studio\" >nul 2>&1

:: 5. Don dep thu muc build tam thoi
if exist "build" rmdir /s /q "build"
if exist "CIT-Voice-Studio.spec" del /f /q "CIT-Voice-Studio.spec"

echo.
echo ================================================================
echo  [SUCCESS] DONG GOI THANH CONG!
echo.
echo  Thu muc ung dung danh cho nguoi dung cuoi:
echo    ^> dist\CIT-Voice-Studio\
echo.
echo  File chay ung dung truc tiep (.exe):
echo    ^> dist\CIT-Voice-Studio\CIT-Voice-Studio.exe
echo.
echo  Ban chi can nen thu muc dist\CIT-Voice-Studio thanh file .zip 
echo  va gui cho nguoi dung la ho co the su dung ngay!
echo ================================================================

:: Tu dong mo thu muc dist\CIT-Voice-Studio de nguoi dung thay ngay
if not "%1"=="--no-pause" explorer "dist\CIT-Voice-Studio"
if not "%1"=="--no-pause" pause
