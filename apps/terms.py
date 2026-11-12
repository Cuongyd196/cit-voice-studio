"""Điều khoản sử dụng (DIEU-KHOAN.md): người dùng phải đồng ý khi mở app lần đầu.

Dấu đồng ý chỉ nằm trên máy người dùng, không gửi đi đâu. Đổi TERMS_VERSION (và dòng
"Phiên bản điều khoản" trong DIEU-KHOAN.md) thì mọi người được hỏi lại.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from fastapi import APIRouter

TERMS_VERSION = "1.3"

VOICE_RIGHTS_STATEMENT = (
    "Tôi chỉ dùng giọng của mình hoặc giọng đã được chủ giọng cho phép nhân bản bằng AI "
    "và sử dụng đúng mục đích đã đồng ý. Tôi có quyền sử dụng bản ghi âm và không dùng "
    "giọng tạo ra để mạo danh, lừa đảo, gây hiểu lầm hoặc xâm phạm quyền, lợi ích hợp pháp "
    "của người khác."
)


def terms_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "terms-accepted.json"


def _terms_file() -> Path:
    # Bản đóng gói: DIEU-KHOAN.md được --add-data vào _MEIPASS; chạy từ mã nguồn: gốc repo.
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / "DIEU-KHOAN.md"


def terms_text() -> str:
    return _terms_file().read_text(encoding="utf-8")


def accepted() -> bool:
    try:
        data = json.loads(terms_path().read_text(encoding="utf-8"))
        return data.get("terms_version") == TERMS_VERSION
    except (OSError, ValueError, AttributeError):
        return False


def accept() -> None:
    path = terms_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump({"terms_version": TERMS_VERSION}, f)
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


router = APIRouter()


@router.get("/api/terms")
def get_terms():
    return {"version": TERMS_VERSION, "accepted": accepted(), "text": terms_text()}


@router.post("/api/terms/accept")
def post_accept():
    accept()
    return {"version": TERMS_VERSION, "accepted": True}
