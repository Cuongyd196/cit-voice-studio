"""Phần riêng cho Linux (và macOS) của bộ tự cài GPU - tách khỏi gpu_installer.py
để sửa ở đây không đụng tới đường chạy trên Windows.

gpu_installer.py chỉ gọi sang module này trong các nhánh `sys.platform != "win32"`.
"""
from __future__ import annotations

import sys
from pathlib import Path


def base_stdlib_roots(venv_home: Path) -> list[Path]:
    """Thư mục thư viện chuẩn của Python gốc, tính từ `home` trong pyvenv.cfg.

    Khác Windows: trên Linux/macOS `home` là thư mục `bin/` của Python gốc
    (vd. `.../base-python/3.12.3/python/bin`), còn thư viện chuẩn nằm ở
    `../lib/python3.12`. Ghép thẳng vào `home` như Windows thì trỏ vào thư mục không
    tồn tại, và bản đóng gói không tìm được module còn thiếu - lỗi thật trên máy
    khách: "Could not import module 'PretrainedConfig'", gốc là
    `No module named 'filecmp'`.
    """
    tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
    prefix = venv_home.parent if venv_home.name == "bin" else venv_home
    lib = prefix / "lib" / tag
    # Module C của thư viện chuẩn (vd. _json.so) nằm trong lib-dynload.
    return [p for p in (lib, lib / "lib-dynload") if p.is_dir()]


def clean_child_env(env: dict) -> None:
    """Trả `LD_LIBRARY_PATH` về như trước khi bootloader PyInstaller sửa.

    Bootloader trên Linux trỏ `LD_LIBRARY_PATH` vào `_internal/` và cất bản gốc vào
    `LD_LIBRARY_PATH_ORIG`. Không trả lại thì Python gốc và phép thử CUDA chạy trong
    tiến trình con nạp nhầm .so của bản đóng gói (libstdc++, libssl...) thay cho thư
    viện của hệ thống/torch - kiểu lỗi chỉ xảy ra trên máy khách.
    """
    orig = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    elif getattr(sys, "frozen", False):
        env.pop("LD_LIBRARY_PATH", None)
