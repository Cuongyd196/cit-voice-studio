r"""Kiểu MIME của file tĩnh phải đúng, kể cả khi registry Windows khai báo sai.

Lỗi thật đã gặp: trên máy người dùng, registry đặt HKEY_CLASSES_ROOT\.js thành
"text/plain". `mimetypes` của Python đọc registry và cho nó đè lên bảng mặc định,
nên StaticFiles trả file .js kèm Content-Type sai, trình duyệt từ chối chạy module
và cửa sổ ứng dụng TRẮNG TRƠN không một dòng báo lỗi.
"""
from __future__ import annotations

import mimetypes

import pytest

from apps.runtime_paths import fix_web_mime_types


@pytest.fixture(autouse=True)
def _restore_mime_map():
    """mimetypes dùng state toàn cục — trả lại nguyên trạng sau mỗi test."""
    mimetypes.init()
    saved = dict(mimetypes.types_map)
    yield
    mimetypes.types_map.clear()
    mimetypes.types_map.update(saved)


@pytest.mark.parametrize("ext", [".js", ".mjs", ".css", ".wasm", ".json"])
def test_registry_ban_van_tra_ve_kieu_dung(ext):
    mimetypes.types_map[ext] = "text/plain"          # giả lập registry bẩn
    fix_web_mime_types()
    assert mimetypes.guess_type("x" + ext)[0] != "text/plain"


def test_js_la_kieu_trinh_duyet_chap_nhan_cho_module():
    mimetypes.types_map[".js"] = "text/plain"
    fix_web_mime_types()
    # Chỉ hai giá trị này được trình duyệt chấp nhận cho <script type="module">.
    assert mimetypes.guess_type("a.js")[0] in {"text/javascript", "application/javascript"}


def test_bao_cao_dung_nhung_duoi_file_da_phai_sua():
    mimetypes.types_map[".js"] = "text/plain"
    mimetypes.types_map[".css"] = "text/css"          # vốn đã đúng
    fixed = fix_web_mime_types()
    assert fixed[".js"] == "text/plain"
    assert ".css" not in fixed


def test_goi_nhieu_lan_khong_doi_ket_qua():
    fix_web_mime_types()
    assert fix_web_mime_types() == {}
