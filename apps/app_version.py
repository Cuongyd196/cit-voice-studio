"""Số phiên bản ứng dụng - khai MỘT chỗ duy nhất.

Tab "Thông tin" đọc số này qua /api/app/update; `installer.iss` (AppVersion) phải
khớp, tests/test_app_update.py kiểm tra. Ra bản mới: sửa cả hai rồi gắn tag.
"""
APP_VERSION = "1.0.6"
