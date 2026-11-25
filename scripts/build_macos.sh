#!/usr/bin/env bash
# Đóng gói CIT Voice Studio cho macOS -> dist/CIT-Voice-Studio-v<version>-macos-<arch>.dmg
# Người dùng mở .dmg rồi kéo "CIT Voice Studio" vào Applications.
# (bản Linux: build_linux.sh; bản Windows: build_desktop_exe.bat - ba script độc lập,
#  sửa script này không ảnh hưởng hai bản kia).
#
# PyInstaller KHÔNG build chéo: phải chạy trên macOS. Không có Mac thì dùng CI:
# .github/workflows/build-macos.yml. Bản build theo chip của máy build (arm64 / x86_64).
#
# Khác bản Windows/Linux:
#  - Gói .app có cửa sổ riêng (pywebview + WebKit có sẵn của macOS, PyObjC đóng gói kèm),
#    tắt bằng Cmd+Q như app bình thường.
#  - Mô hình đóng gói TRONG .app và được chép ra ~/Library/Application Support ở lần
#    chạy đầu; mọi dữ liệu ghi được nằm ngoài gói (xem apps/runtime_paths_macos.py).
#  - Chỉ chạy CPU. Chưa ký bằng Apple Developer ID (chỉ ký ad-hoc): lần đầu mở phải bấm
#    "Open Anyway" trong System Settings -> Privacy & Security.
#
# Dùng:  ./build_macos.sh                  # cần uv + Node 20+
#        ./build_macos.sh --no-models      # không kèm mô hình, lần đầu chạy app tự tải
#        ./build_macos.sh --skip-frontend  # dùng giao diện đã build sẵn (không cần Node)
# Lưu ý: macOS dùng bash 3.2 - tránh cú pháp bash 4+ (mảng kết hợp, ${var,,}...).
set -euo pipefail
cd "$(dirname "$0")/.."  # gốc repo (script nằm trong scripts/)

[[ "$(uname -s)" == Darwin ]] || { echo "[ERROR] Script này chỉ chạy trên macOS. Linux: build_linux.sh"; exit 1; }

WITH_MODELS=1
BUILD_FRONTEND=1
for arg in "$@"; do
    case "$arg" in
        --no-models) WITH_MODELS=0 ;;
        --skip-frontend) BUILD_FRONTEND=0 ;;
        *) echo "[ERROR] Tham số không hợp lệ: $arg"; exit 1 ;;
    esac
done

ARCH="$(uname -m)"
APP_NAME="CIT Voice Studio"
APP="dist/${APP_NAME}.app"
# Phiên bản lấy từ installer.iss để mọi hệ điều hành cùng một số phiên bản.
VERSION="$(sed -n 's/^#define AppVersion *"\(.*\)".*/\1/p' scripts/installer.iss)"
[[ -n "$VERSION" ]] || { echo "[ERROR] Không đọc được AppVersion trong scripts/installer.iss"; exit 1; }
DMG="dist/CIT-Voice-Studio-v${VERSION}-macos-${ARCH}.dmg"
STAGE=".mac-stage"

if [[ $BUILD_FRONTEND == 1 ]]; then
    echo "[+] 1/5 Build giao diện React..."
    (cd app-desktop/cit-voice-app && npm ci --no-audit --no-fund && npm run build)
elif [[ -f app-desktop/cit-voice-app/dist/index.html ]]; then
    echo "[+] 1/5 Dùng giao diện đã build sẵn."
else
    echo "[ERROR] Chưa có app-desktop/cit-voice-app/dist - bỏ --skip-frontend hoặc build trước."
    exit 1
fi

echo "[+] 2/5 Cài môi trường Python (torch-free) + pywebview/PyObjC + PyInstaller..."
if [[ "$ARCH" == x86_64 ]]; then
    # onnxruntime 1.24 bỏ Mac chip Intel (chỉ còn wheel macosx arm64); 1.23.2 là bản
    # cuối có wheel x86_64. Hạ riêng ở đây thay vì sửa uv.lock để Windows/Linux giữ nguyên.
    uv sync --frozen --group desktop --no-install-package onnxruntime
    uv pip install "onnxruntime==1.23.2"
else
    uv sync --frozen --group desktop
fi
uv pip install pyinstaller
# Từ đây `uv run` không được sync lại (sẽ cài lại onnxruntime theo uv.lock).
export UV_NO_SYNC=1

rm -rf build "dist/${APP_NAME}" "$APP" "$STAGE" "$DMG"
MODEL_ARGS=()
if [[ $WITH_MODELS == 1 ]]; then
    echo "[+] 3/5 Tải sẵn mô hình v3 Turbo int8 (~312 MB)..."
    uv run python scripts/fetch_models.py
    # Như bản Windows: chép THEO DANH SÁCH (Turbo int8 + codec, ~312 MB), không chép
    # cả cache - cache máy build có thể chứa mô hình khác (Kokoro ~650 MB) và giọng
    # nhân bản của người thật (custom_voices_*.json).
    uv run python scripts/copy_release_models.py "$STAGE/models"
    MODEL_ARGS=(--add-data "$STAGE/models/hf_cache:models/hf_cache")
else
    echo "[+] 3/5 Bỏ qua mô hình: app sẽ tự tải ở lần chạy đầu."
fi

echo "[+] 4/5 Đóng gói bằng PyInstaller (.app)..."
uv run pyinstaller --clean --noconfirm --onedir --windowed \
    --name "$APP_NAME" \
    --icon "assets/icons/icon.icns" \
    --osx-bundle-identifier "vn.cit.voicestudio" \
    --paths src \
    --exclude-module torch --exclude-module torchaudio --exclude-module transformers \
    --add-data "docs/cit-voice-studio.md:." \
    --add-data "DIEU-KHOAN.md:." \
    --add-data "app-desktop/cit-voice-app/dist:app-desktop/cit-voice-app/dist" \
    --collect-all onnxruntime --collect-all sea_g2p --collect-all soundfile \
    --collect-all tokenizers --collect-all vieneu --collect-all vieneu_utils \
    --collect-all pypdf --collect-all kaldi_native_fbank --collect-all soxr \
    --collect-all librosa --collect-all huggingface_hub \
    --collect-all webview \
    --hidden-import webview.platforms.cocoa \
    --hidden-import unittest.mock \
    --hidden-import uvicorn.logging --hidden-import uvicorn.loops --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan \
    --hidden-import uvicorn.lifespan.on \
    ${MODEL_ARGS[@]+"${MODEL_ARGS[@]}"} \
    apps/desktop_app.py

# Tab Nhân bản giọng thu âm bằng micro: WebKit trên macOS tắt app ngay khi xin quyền
# micro nếu Info.plist không khai báo lý do.
PLIST="$APP/Contents/Info.plist"
plutil -replace NSMicrophoneUsageDescription \
    -string "CIT Voice Studio dùng micro để thu giọng mẫu khi nhân bản giọng nói." "$PLIST"
plutil -replace NSHighResolutionCapable -bool true "$PLIST"
# Bản macOS tối thiểu theo wheel onnxruntime: arm64 1.24.4 = macosx_14_0, x86_64 1.23.2 = macosx_13_0.
if [[ "$ARCH" == x86_64 ]]; then MIN_MACOS="13.0"; else MIN_MACOS="14.0"; fi
plutil -replace LSMinimumSystemVersion -string "$MIN_MACOS" "$PLIST"
plutil -lint "$PLIST"

# Sửa Info.plist làm hỏng chữ ký ad-hoc PyInstaller vừa ký -> ký lại. Chip Apple bắt
# buộc mọi mã chạy phải có chữ ký (dù chỉ ad-hoc), thiếu là báo "app bị hỏng".
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "[+] 5/5 Tạo file cài .dmg..."
DMGSRC="$STAGE/dmg"
rm -rf "$DMGSRC"; mkdir -p "$DMGSRC"
cp -R "$APP" "$DMGSRC/"
ln -s /Applications "$DMGSRC/Applications"
cp LICENSE NOTICE THIRD-PARTY-NOTICES.md PRIVACY.md DIEU-KHOAN.md packaging/macos/HUONG-DAN.txt "$DMGSRC/"
# hdiutil trên máy CI đôi khi báo "Resource busy" -> thử lại vài lần.
ok=0
for i in 1 2 3 4 5; do
    if hdiutil create -volname "$APP_NAME" -srcfolder "$DMGSRC" -ov -format UDZO "$DMG"; then
        ok=1; break
    fi
    sleep 5
done
[[ $ok == 1 ]] || { echo "[ERROR] Không tạo được file .dmg"; exit 1; }
rm -rf "$STAGE"
echo "[SUCCESS] $DMG  (app: $APP)"
