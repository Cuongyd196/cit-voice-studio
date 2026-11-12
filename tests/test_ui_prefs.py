"""Tuỳ chọn giao diện lưu xuống đĩa: app desktop (PyWebView private_mode) xoá
localStorage mỗi lần tắt, người dùng chọn giao diện tối xong mở lại thấy sáng."""
import pytest
from fastapi.testclient import TestClient

from apps import ui_prefs


@pytest.fixture(autouse=True)
def _tep_tam(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_prefs, "settings_path", lambda: tmp_path / "cfg" / "ui-prefs.json")


@pytest.fixture
def client():
    import apps.web_stream as ws

    return TestClient(ws.app, base_url="http://127.0.0.1:8001")


def test_chua_co_file_thi_rong():
    assert ui_prefs.load() == {}


def test_luu_roi_doc_lai_va_gop_tung_phan():
    ui_prefs.update({"theme": "dark"})
    ui_prefs.update({"playbackSpeed": 1.25, "autoPlayOnGenerate": False})
    assert ui_prefs.load() == {"theme": "dark", "playbackSpeed": 1.25, "autoPlayOnGenerate": False}


def test_bo_khoa_la_va_gia_tri_sai_kieu():
    out = ui_prefs.update({
        "theme": "tim", "apiUrl": "http://x", "playbackSpeed": True,
        "silenceDuration": 99, "autoPlayOnGenerate": "có",
    })
    assert out == {}


def test_giong_mo_san_luu_va_bo_chon_duoc():
    ui_prefs.update({"defaultVoiceId": "Trúc Ly"})
    assert ui_prefs.load() == {"defaultVoiceId": "Trúc Ly"}
    ui_prefs.update({"defaultVoiceId": ""})
    assert ui_prefs.load() == {"defaultVoiceId": ""}


@pytest.mark.parametrize("sai", ["x" * 201, 5, None, ["Trúc Ly"]])
def test_bo_ma_giong_khong_hop_le(sai):
    assert ui_prefs.update({"defaultVoiceId": sai}) == {}


def test_file_hong_thi_rong():
    p = ui_prefs.settings_path()
    p.parent.mkdir(parents=True)
    p.write_text("không phải json", encoding="utf-8")
    assert ui_prefs.load() == {}
    p.write_text("[1, 2]", encoding="utf-8")
    assert ui_prefs.load() == {}


def test_api_get_put(client):
    assert client.get("/api/ui/prefs").json() == {}
    r = client.put("/api/ui/prefs", json={"theme": "dark"})
    assert r.status_code == 200 and r.json() == {"theme": "dark"}
    assert client.get("/api/ui/prefs").json() == {"theme": "dark"}


def test_trang_web_la_khong_doi_duoc(client):
    r = client.put("/api/ui/prefs", json={"theme": "dark"},
                   headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert ui_prefs.load() == {}
