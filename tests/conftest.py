import os
import sys

import pytest

# apps/web_stream.py nạp model thật trong thread nền ngay lúc import; thread đó gán
# đè `vieneu` mà các test đã mock (test hỏng chập chờn) và có thể tải ~300 MB.
# Phải đặt TRƯỚC khi bất kỳ test nào import web_stream.
os.environ.setdefault("CIT_SKIP_MODEL_AUTOLOAD", "1")


@pytest.fixture(autouse=True)
def _khong_ghi_mo_hinh_da_chon(tmp_path, monkeypatch):
    """Test gọi load_model_instance không được ghi last-model.json vào thư mục dữ liệu
    thật của máy dev: lần mở app sau sẽ nạp mô hình do test chọn."""
    ws = sys.modules.get("apps.web_stream")
    if ws is not None:
        monkeypatch.setattr(ws, "_last_model_path", lambda: tmp_path / "last-model.json")
