"""Đường dẫn dùng chung cho mọi entry point (FastAPI, Desktop).

Lý do tồn tại: trước đây mỗi entry point đặt HF_HOME một kiểu, nên chạy hai cách
khởi động sẽ tải cùng một bộ mô hình ~300 MB xuống HAI thư mục khác nhau.

Giờ mọi entry point cùng gọi `setup_hf_home()`, mặc định trỏ vào `models/hf_cache` NGAY TRONG
thư mục ứng dụng. Nhờ vậy bộ mô hình tải sẵn có thể đi kèm bản phát hành, và gỡ ứng
dụng là sạch, không để lại rác trong profile người dùng.

QUAN TRỌNG: phải gọi TRƯỚC khi `huggingface_hub` được import lần đầu, vì thư viện
này đọc HF_HOME ngay lúc import.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def app_root() -> Path:
    """Thư mục gốc của ứng dụng.

    Bản đóng gói PyInstaller `--onedir`: thư mục chứa file .exe. Cố tình KHÔNG dùng
    `sys._MEIPASS` - đó là thư mục giải nén tạm, bị xoá khi thoát, nên cache đặt ở
    đó sẽ phải tải lại mỗi lần mở ứng dụng.
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            # File chạy nằm trong gói .app - dữ liệu phải ra ngoài gói.
            from apps.runtime_paths_macos import data_dir
            return data_dir()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


VCREDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

# onnxruntime import 4 DLL này (kiểm bằng bảng import PE của
# onnxruntime_pybind11_state.pyd). Chúng thuộc Microsoft Visual C++ Redistributable
# 2015-2022 x64 và onnxruntime KHÔNG tự mang theo - khác numpy/sklearn/llvmlite, vốn
# kèm sẵn bản msvcp140 riêng. Máy thiếu sẽ nhận thông báo tối nghĩa:
#   "DLL load failed while importing onnxruntime_pybind11_state:
#    A dynamic link library (DLL) initialization routine failed."
# VCRUNTIME140_1.dll chỉ có từ bản redist 2019 trở đi, nên máy cài bản 2015 cũ vẫn
# thiếu đúng file đó.
#
# Bản đóng gói .exe không dính: PyInstaller gom sẵn cả 4 DLL vào bundle.
_VCREDIST_DLLS = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll", "msvcp140_1.dll")


def missing_vcredist() -> list[str]:
    """Các DLL của VC++ Redistributable mà máy đang thiếu. Rỗng nghĩa là đủ."""
    if sys.platform != "win32" or getattr(sys, "frozen", False):
        return []
    import ctypes
    missing = []
    for name in _VCREDIST_DLLS:
        try:
            ctypes.WinDLL(name)
        except Exception:
            missing.append(name)
    return missing


def vcredist_error_message(missing: list[str]) -> str:
    return (
        "Máy thiếu Microsoft Visual C++ Redistributable nên không nạp được thư viện "
        "suy luận (onnxruntime).\n\n"
        f"Thiếu: {', '.join(missing)}\n\n"
        f"Tải và cài bản x64 (miễn phí, của Microsoft):\n{VCREDIST_URL}\n\n"
        "Cài xong khởi động lại ứng dụng."
    )


def _is_writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".write_test"
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except Exception:
        return False


def setup_hf_home() -> Path:
    """Đặt HF_HOME dùng chung và trả về đường dẫn cache.

    Thứ tự ưu tiên:
      1. HF_HOME người dùng tự đặt  → tôn trọng, không ghi đè.
      2. `<thư mục app>/models/hf_cache` → đi kèm bản phát hành, gỡ app là sạch.
      3. `%LOCALAPPDATA%\\CitVoiceStudio\\hf_cache` → khi thư mục app chỉ đọc
         (cài trong Program Files, chạy từ ổ mạng, ổ USB khoá ghi...).
    """
    existing = os.environ.get("HF_HOME")
    if existing:
        return Path(existing)

    cache = app_root() / "models" / "hf_cache"
    if not _is_writable(cache):
        base = os.getenv("LOCALAPPDATA") or str(Path.home())
        cache = Path(base) / "CitVoiceStudio" / "hf_cache"
        cache.mkdir(parents=True, exist_ok=True)

    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        from apps.runtime_paths_macos import seed_bundled_models
        seed_bundled_models(cache)
    elif sys.platform.startswith("linux") and getattr(sys, "frozen", False):
        from apps.runtime_paths_linux import seed_bundled_models as seed_linux
        seed_linux(cache)

    os.environ["HF_HOME"] = str(cache)
    # Windows không bật Developer Mode thì HF không tạo được symlink và cảnh báo mỗi
    # lần tải. Nó vẫn chạy (chỉ tốn đĩa hơn), không cần doạ người dùng cuối.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    return cache


# Kiểu MIME đúng cho các file tĩnh mà trình duyệt BẮT BUỘC phải nhận đúng loại.
_WEB_MIME_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".wasm": "application/wasm",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


def fix_web_mime_types() -> dict[str, str]:
    r"""Ép kiểu MIME đúng cho file tĩnh, bất kể registry Windows ghi gì.

    Vì sao cần: trên Windows, `mimetypes.init()` ĐỌC REGISTRY (HKEY_CLASSES_ROOT\.js
    → "Content Type") và cho nó ĐÈ LÊN bảng mặc định của Python. Nhiều phần mềm
    (trình soạn thảo cũ, bộ cài Java/Adobe, công cụ nội bộ) ghi đè khoá này thành
    "text/plain". Khi đó `StaticFiles` của Starlette trả về file .js kèm
    `Content-Type: text/plain`, và trình duyệt TỪ CHỐI thực thi nó:

        Failed to load module script: Expected a JavaScript-or-Wasm module script
        but the server responded with a MIME type of "text/plain".

    Hậu quả là cửa sổ TRẮNG TRƠN, không báo lỗi gì - React không bao giờ chạy. Lỗi
    chỉ xuất hiện trên máy có registry bị bẩn, nên máy dev vẫn chạy tốt và rất khó
    đoán ra. Đo trên chính máy dev: `.mjs` bị registry ghi thành "text/plain" trong
    khi Python mặc định là "text/javascript".

    `mimetypes.add_type()` chạy `init()` trước rồi mới ghi đè, nên gọi hàm này một
    lần lúc khởi động là đủ. Trả về những đuôi file thực sự đã phải sửa, để ghi log.
    """
    import mimetypes

    fixed: dict[str, str] = {}
    for ext, correct in _WEB_MIME_TYPES.items():
        before = mimetypes.guess_type("x" + ext)[0]
        if before != correct:
            fixed[ext] = before or "(không có)"
        mimetypes.add_type(correct, ext)
    return fixed


def https_context():
    """SSL context cho các lệnh tải bằng urllib: tin kho chứng chỉ của hệ điều hành
    VÀ bộ chứng chỉ của certifi.

    Windows chỉ cài chứng chỉ gốc khi có chương trình cần đến (schannel tự tải qua
    Windows Update), còn OpenSSL của Python chỉ đọc những gốc đã có sẵn trong kho. Máy
    chưa từng gặp gốc "USERTrust ECC" (chuỗi mới của api.github.com, 2026-10) vì thế
    báo CERTIFICATE_VERIFY_FAILED, dù curl và trình duyệt vẫn vào được.
    """
    import ssl

    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(certifi.where())
    except (ImportError, OSError):
        pass
    return ctx
