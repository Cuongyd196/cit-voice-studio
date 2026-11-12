"""Điều khoản sử dụng: hỏi khi mở app lần đầu, lưu dấu đồng ý chỉ trên máy."""
import json

import pytest
from fastapi.testclient import TestClient

from apps import terms
from apps import web_stream as ws


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(terms, "terms_path", lambda: tmp_path / "terms-accepted.json")
    return TestClient(ws.app)


def test_lan_dau_chua_dong_y_va_co_noi_dung(client):
    body = client.get("/api/terms").json()
    assert body["accepted"] is False
    assert body["version"] == terms.TERMS_VERSION
    assert "Điều khoản sử dụng" in body["text"]


def test_dong_y_roi_thi_nho(client):
    assert client.post("/api/terms/accept").json()["accepted"] is True
    assert client.get("/api/terms").json()["accepted"] is True
    saved = json.loads(terms.terms_path().read_text(encoding="utf-8"))
    assert saved == {"terms_version": terms.TERMS_VERSION}


def test_doi_phien_ban_thi_hoi_lai(client, monkeypatch):
    client.post("/api/terms/accept")
    monkeypatch.setattr(terms, "TERMS_VERSION", "2.0")
    assert client.get("/api/terms").json()["accepted"] is False


def test_file_hong_coi_nhu_chua_dong_y(client):
    terms.terms_path().write_text("{rác", encoding="utf-8")
    assert client.get("/api/terms").json()["accepted"] is False


def test_phien_ban_khop_voi_file_dieu_khoan():
    assert f"Phiên bản điều khoản: **{terms.TERMS_VERSION}**" in terms.terms_text()


def test_khong_nam_trong_tai_lieu_api():
    assert "/api/terms" not in ws.app.openapi()["paths"]


def test_ban_txt_cho_trinh_cai_dat(tmp_path):
    import make_terms_txt

    out = make_terms_txt.write(tmp_path / "DIEU-KHOAN.txt")
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")          # Inno Setup cần BOM để hiện chữ Việt
    text = raw.decode("utf-8-sig")
    assert "Điều khoản sử dụng" in text
    assert "**" not in text and "# " not in text


def test_dieu_khoan_duoc_dong_goi_va_dong_bo():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    for script in ("build_desktop_exe.bat", "build_linux.sh", "build_macos.sh"):
        assert "DIEU-KHOAN.md" in (root / "scripts" / script).read_text(encoding="utf-8"), script
    assert "LicenseFile=build\\DIEU-KHOAN.txt" in (root / "scripts" / "installer.iss").read_text(encoding="utf-8")
