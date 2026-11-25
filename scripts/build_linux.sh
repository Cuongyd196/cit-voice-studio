#!/usr/bin/env bash
# Đóng gói CIT Voice Studio cho Linux -> dist/CIT-Voice-Studio-v<version>-linux-<arch>.tar.gz
#                                   và dist/CIT-Voice-Studio-v<version>-<amd64|arm64>.deb
# (bản macOS: build_macos.sh; bản Windows: build_desktop_exe.bat - ba script độc lập,
#  sửa script này không ảnh hưởng hai bản kia).
#
# PyInstaller KHÔNG build chéo: phải chạy trên Linux. CI: .github/workflows/build-linux.yml
#
# Khác bản Windows:
#  - Không có cửa sổ riêng: app chạy trong Terminal và mở giao diện bằng trình duyệt
#    (desktop_app.py tự chọn trên Linux), nên không cần nhóm `desktop`, không --windowed.
#  - Kèm uv để app tự cài bộ GPU NVIDIA theo yêu cầu (xem apps/gpu_installer_linux.py).
#  - Bản .deb cài vào /opt/cit-voice-studio (chỉ đọc) + lệnh `cit-voice-studio` + mục
#    trong menu ứng dụng. Dữ liệu ghi được tự chuyển sang ~/CitVoiceStudio, mô hình đi
#    kèm được chép ra đó ở lần chạy đầu (apps/runtime_paths_linux.py).
#  - Build trên glibc càng cũ càng tốt (CI dùng Ubuntu 22.04): bản build trên glibc mới
#    không chạy được trên distro cũ hơn.
#
# Dùng:  ./build_linux.sh                  # cần uv + Node 20+
#        ./build_linux.sh --no-models      # không kèm mô hình, lần đầu chạy app tự tải
#        ./build_linux.sh --skip-frontend  # dùng giao diện đã build sẵn (không cần Node)
#        ./build_linux.sh --no-deb         # chỉ tạo .tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."  # gốc repo (script nằm trong scripts/)

[[ "$(uname -s)" == Linux ]] || { echo "[ERROR] Script này chỉ chạy trên Linux. macOS: build_macos.sh"; exit 1; }

WITH_MODELS=1
BUILD_FRONTEND=1
BUILD_DEB=1
for arg in "$@"; do
    case "$arg" in
        --no-models) WITH_MODELS=0 ;;
        --skip-frontend) BUILD_FRONTEND=0 ;;
        --no-deb) BUILD_DEB=0 ;;
        *) echo "[ERROR] Tham số không hợp lệ: $arg"; exit 1 ;;
    esac
done

ARCH="$(uname -m)"; [[ "$ARCH" == "aarch64" ]] && ARCH=arm64
NAME="CIT-Voice-Studio"
# Phiên bản lấy từ installer.iss để mọi hệ điều hành cùng một số phiên bản.
VERSION="$(sed -n 's/^#define AppVersion *"\(.*\)".*/\1/p' scripts/installer.iss)"
[[ -n "$VERSION" ]] || { echo "[ERROR] Không đọc được AppVersion trong scripts/installer.iss"; exit 1; }
OUT="dist/${NAME}-v${VERSION}-linux-${ARCH}"

if [[ $BUILD_FRONTEND == 1 ]]; then
    echo "[+] 1/4 Build giao diện React..."
    (cd app-desktop/cit-voice-app && npm ci --no-audit --no-fund && npm run build)
elif [[ -f app-desktop/cit-voice-app/dist/index.html ]]; then
    echo "[+] 1/4 Dùng giao diện đã build sẵn."
else
    echo "[ERROR] Chưa có app-desktop/cit-voice-app/dist - bỏ --skip-frontend hoặc build trước."
    exit 1
fi

echo "[+] 2/4 Cài môi trường Python (torch-free) + PyInstaller..."
uv sync --frozen
uv pip install pyinstaller

if [[ $WITH_MODELS == 1 ]]; then
    echo "[+] 3/4 Tải sẵn mô hình v3 Turbo int8 (~312 MB)..."
    uv run python scripts/fetch_models.py
else
    echo "[+] 3/4 Bỏ qua mô hình: app sẽ tự tải ở lần chạy đầu."
fi

echo "[+] 4/4 Đóng gói bằng PyInstaller..."
rm -rf build "dist/${NAME}" "$OUT" "${OUT}.tar.gz"
UV_BIN="$(command -v uv)" || { echo "[ERROR] Không tìm thấy uv để đóng gói bộ cài GPU."; exit 1; }
# Danh sách --collect-all giống bản Windows, trừ webview/pythonnet/clr_loader.
uv run pyinstaller --clean --noconfirm --onedir \
    --name "$NAME" \
    --paths src \
    --exclude-module torch --exclude-module torchaudio --exclude-module transformers \
    --exclude-module webview \
    --add-data "docs/cit-voice-studio.md:." \
    --add-data "DIEU-KHOAN.md:." \
    --add-data "app-desktop/cit-voice-app/dist:app-desktop/cit-voice-app/dist" \
    --add-binary "${UV_BIN}:tools" \
    --collect-all onnxruntime --collect-all sea_g2p --collect-all soundfile \
    --collect-all tokenizers --collect-all vieneu --collect-all vieneu_utils \
    --collect-all pypdf --collect-all kaldi_native_fbank --collect-all soxr \
    --collect-all librosa --collect-all huggingface_hub \
    --hidden-import unittest.mock \
    --hidden-import numpy.typing --hidden-import numpy.lib.stride_tricks \
    --collect-submodules joblib --collect-submodules apps._kokoro_torch \
    --hidden-import uvicorn.logging --hidden-import uvicorn.loops --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan \
    --hidden-import uvicorn.lifespan.on \
    apps/desktop_app.py

mv "dist/${NAME}" "$OUT"
cp LICENSE NOTICE THIRD-PARTY-NOTICES.md PRIVACY.md DIEU-KHOAN.md packaging/linux/HUONG-DAN.txt "$OUT/"

if [[ $WITH_MODELS == 1 && -d models/hf_cache ]]; then
    # Như bản Windows: chép THEO DANH SÁCH (Turbo int8 + codec, ~312 MB), không chép
    # cả cache - cache máy build có thể chứa mô hình khác (Kokoro ~650 MB) và giọng
    # nhân bản của người thật (custom_voices_*.json).
    uv run python scripts/copy_release_models.py "$OUT/models"
fi

echo "[+] Nén..."
tar -C dist -czf "${OUT}.tar.gz" "$(basename "$OUT")"
echo "[SUCCESS] ${OUT}.tar.gz"

[[ $BUILD_DEB == 1 ]] || exit 0

# ---- Gói .deb --------------------------------------------------------------
case "$ARCH" in x86_64) DEB_ARCH=amd64 ;; *) DEB_ARCH="$ARCH" ;; esac
# Tên file cùng kiểu các bản khác (CIT-Voice-Studio-v<version>-...); tên gói bên trong
# vẫn là cit-voice-studio nên apt nhận bản mới là bản nâng cấp.
DEB="dist/CIT-Voice-Studio-v${VERSION}-${DEB_ARCH}.deb"
PKG=".deb-stage"
echo "[+] Tạo gói .deb ${VERSION}..."
rm -rf "$PKG" "$DEB"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" \
    "$PKG/usr/share/metainfo"
# Hard link thay vì chép ~600 MB (khác ổ đĩa thì chép).
cp -al "$OUT" "$PKG/opt/cit-voice-studio" 2>/dev/null || cp -a "$OUT" "$PKG/opt/cit-voice-studio"
printf '#!/bin/sh\nexec /opt/cit-voice-studio/CIT-Voice-Studio "$@"\n' > "$PKG/usr/bin/cit-voice-studio"
cp packaging/linux/cit-voice-studio.desktop "$PKG/usr/share/applications/"
# Icon đủ cỡ: trước đây chỉ có 128px, trình khởi chạy/App Center cần 256/512 thì
# không thấy logo.
ICONS=assets/icons
for pair in "32x32:32x32.png" "64x64:64x64.png" "128x128:128x128.png" \
            "256x256:128x128@2x.png" "512x512:icon.png"; do
    size="${pair%%:*}"; src="${pair#*:}"
    mkdir -p "$PKG/usr/share/icons/hicolor/${size}/apps"
    cp "$ICONS/$src" "$PKG/usr/share/icons/hicolor/${size}/apps/cit-voice-studio.png"
done
# AppStream metainfo: App Center / GNOME Software đọc tên, mô tả, giấy phép, icon
# từ đây (thiếu file này thì hiện "License unknown", không có logo).
sed -e "s/@VERSION@/${VERSION}/" -e "s/@DATE@/$(date +%Y-%m-%d)/" \
    packaging/linux/cit-voice-studio.metainfo.xml > "$PKG/usr/share/metainfo/cit-voice-studio.metainfo.xml"
# control bằng tiếng Anh, chỉ ASCII: App Center của Ubuntu hiện chữ có dấu thành
# "Chuy??n v?n b??n" (người dùng báo, 2026-09).
{
    echo "Package: cit-voice-studio"
    echo "Version: ${VERSION}"
    echo "Architecture: ${DEB_ARCH}"
    echo "Maintainer: Cuong IT <noreply@cit.vn>"
    echo "Installed-Size: $(du -sk "$PKG" | cut -f1)"
    echo "Recommends: xdg-utils"
    echo "Section: sound"
    echo "Priority: optional"
    echo "Homepage: https://github.com/Cuongyd196/cit-voice-studio"
    echo "Description: Vietnamese text-to-speech and voice cloning (VieNeu-TTS)"
    echo " CIT Voice Studio turns Vietnamese text into natural speech and clones a"
    echo " voice from a short sample. Runs offline on the CPU, models included;"
    echo " optional NVIDIA GPU support can be installed from the app."
} > "$PKG/DEBIAN/control"
# Quyền chuẩn cho gói cài hệ thống; chủ sở hữu root nhờ --root-owner-group.
chmod -R u+rwX,go+rX,go-w "$PKG"
chmod 755 "$PKG/usr/bin/cit-voice-studio"
find "$PKG/usr/share" -type f -exec chmod 644 {} +
# gzip thay vì xz/zstd mặc định: nhanh hơn nhiều với ~600 MB, dpkg nào cũng đọc được.
dpkg-deb --root-owner-group -Zgzip --build "$PKG" "$DEB"
rm -rf "$PKG"
echo "[SUCCESS] $DEB"
