"""Mở lại app thì nạp đúng mô hình đã chọn lần trước (1.0.3).

Trước đây `_startup_load` luôn nạp Turbo int8 (hoặc GPU), dù người dùng đã chuyển sang
mô hình khác trong Cài đặt.
"""
from unittest.mock import Mock

import pytest

from apps import model_catalog
from apps import web_stream as ws


@pytest.fixture
def saved(tmp_path, monkeypatch):
    monkeypatch.setattr(ws, "_last_model_path", lambda: tmp_path / "last-model.json")
    monkeypatch.setattr(model_catalog, "is_downloaded", lambda spec: True)
    return tmp_path / "last-model.json"


def _start(monkeypatch, fail=()):
    loaded = []

    def load(name, device="auto"):
        loaded.append(name)
        if name in fail:
            raise RuntimeError("hỏng")
        ws.vieneu = Mock()

    monkeypatch.setattr(ws, "load_model_instance", load)
    monkeypatch.setattr(ws, "cuda_is_available", lambda: False)
    ws._startup_load()
    return loaded


def test_nap_lai_mo_hinh_da_chon(saved, monkeypatch):
    ws._remember_model(model_catalog.SUPERTONIC_ID)
    assert _start(monkeypatch) == [model_catalog.SUPERTONIC_ID]
    assert ws.model_status["state"] == "ok"


def test_chua_chon_gi_thi_mac_dinh(saved, monkeypatch):
    assert _start(monkeypatch) == ["VieNeu-TTS-v3-Turbo (int8)"]


def test_mo_hinh_da_luu_chua_tai_hoac_la_thi_bo_qua(saved, monkeypatch):
    ws._remember_model("Mô hình không tồn tại")
    assert ws._saved_model() is None
    ws._remember_model(model_catalog.SUPERTONIC_ID)
    monkeypatch.setattr(model_catalog, "is_downloaded", lambda spec: False)
    assert ws._saved_model() is None
    saved.write_text("hỏng", encoding="utf-8")
    assert ws._saved_model() is None


def test_mo_hinh_da_luu_nap_hong_thi_lui_ve_int8(saved, monkeypatch):
    ws._remember_model(model_catalog.SUPERTONIC_ID)
    loaded = _start(monkeypatch, fail=(model_catalog.SUPERTONIC_ID,))
    assert loaded == [model_catalog.SUPERTONIC_ID, "VieNeu-TTS-v3-Turbo (int8)"]
    assert ws.model_status["state"] == "ok"
