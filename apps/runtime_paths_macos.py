"""Đường dẫn riêng cho bản macOS đóng gói (.app) - tách khỏi runtime_paths.py để
sửa ở đây không đụng tới Windows/Linux.

Vì sao cần: trên Windows/Linux "thư mục chứa file chạy" là thư mục app người dùng
giải nén ra, ghi dữ liệu vào đó là hợp lý. Trên macOS file chạy nằm TRONG gói
`CIT Voice Studio.app/Contents/MacOS/`. Ghi vào đó thì:
  - cập nhật app (kéo bản .app mới đè lên) là MẤT mô hình đã tải, giọng nhân bản…
  - nội dung gói đổi sau khi ký -> macOS có thể báo app "bị hỏng".
Nên mọi dữ liệu ghi được của bản .app nằm ở ~/Library/Application Support.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

APP_DIR_NAME = "CIT Voice Studio"


def is_frozen_app() -> bool:
    return sys.platform == "darwin" and bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    d = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def bundled_models_dir() -> Path:
    """Mô hình đóng gói kèm trong .app (build_macos.sh --add-data models/hf_cache)."""
    return Path(getattr(sys, "_MEIPASS", "")) / "models" / "hf_cache"


def seed_bundled_models(cache: Path) -> None:
    """Lần đầu chạy: chép mô hình đi kèm trong .app sang cache ghi được.

    Không trỏ thẳng HF_HOME vào trong gói: huggingface_hub ghi file khoá / tải thêm
    (fp32, Nano) vào cache, mà gói .app không nên bị ghi. Chép một lần (~312 MB,
    vài giây); các lần sau thấy đã có `hub/` thì bỏ qua.
    """
    src = bundled_models_dir()
    if not src.is_dir() or (cache / "hub").is_dir():
        return
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + ".seeding")
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp, symlinks=True)
    for entry in tmp.iterdir():
        shutil.move(str(entry), str(cache / entry.name))
    tmp.rmdir()
