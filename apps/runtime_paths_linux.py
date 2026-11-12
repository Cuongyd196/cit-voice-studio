"""Đường dẫn riêng cho bản Linux đóng gói - tách khỏi runtime_paths.py để sửa ở đây
không đụng tới Windows/macOS.

Bản .tar.gz giải nén vào thư mục người dùng (ghi được) nên mô hình dùng tại chỗ.
Bản .deb cài vào /opt/cit-voice-studio, chỉ root ghi được: runtime_paths đã tự chuyển
cache sang ~/CitVoiceStudio/hf_cache, nhưng mô hình đi kèm trong /opt thì không dùng
thẳng được (huggingface_hub ghi file khoá vào cache) - không chép ra là app tải lại
~312 MB dù đã có sẵn trên máy.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen_app() -> bool:
    return sys.platform.startswith("linux") and bool(getattr(sys, "frozen", False))


def bundled_models_dir() -> Path:
    """Mô hình đi kèm: models/hf_cache cạnh file chạy (build_linux.sh chép vào đó)."""
    return Path(sys.executable).resolve().parent / "models" / "hf_cache"


def seed_bundled_models(cache: Path) -> None:
    """Chép mô hình đi kèm sang cache ghi được, một lần. Bản .tar.gz (cache chính là
    thư mục đi kèm) và cache đã có `hub/` thì bỏ qua."""
    src = bundled_models_dir()
    if not src.is_dir() or src == cache.resolve() or (cache / "hub").is_dir():
        return
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + ".seeding")
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(src, tmp, symlinks=True)
    for entry in tmp.iterdir():
        shutil.move(str(entry), str(cache / entry.name))
    tmp.rmdir()
