"""`/api/models` phải nói thật: cái gì máy chạy được, cái gì đã tải về.

Trước khi có hai cờ tách bạch này, chọn FP32 trên bản đóng gói trông y hệt
chọn int8, rồi treo vài phút vì đang tải ngầm 453MB.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps import model_catalog as mc


@pytest.fixture
def ws():
    import apps.web_stream as _ws

    return _ws


def test_mo_ta_model_tach_bach_compatible_va_downloaded(ws):
    spec = mc.get("VieNeu-TTS-v3-Turbo (fp32)")
    with patch.object(mc, "is_downloaded", return_value=False):
        d = ws._mo_ta_model(spec, has_torch=False, has_cuda=False)

    assert d["id"] == "VieNeu-TTS-v3-Turbo (fp32)"
    assert d["compatible"] is True        # ONNX fp32 chạy mọi máy
    assert d["downloaded"] is False       # nhưng chưa có file
    assert d["approx_bytes"] > 0
    assert d["unavailable_reason"] is None


def test_available_van_bang_compatible_de_frontend_cu_khong_doi_hanh_vi(ws):
    spec = mc.get("VieNeu-TTS-v3-Turbo (GPU)")
    with patch.object(mc, "is_downloaded", return_value=True):
        d = ws._mo_ta_model(spec, has_torch=False, has_cuda=False)

    assert d["available"] == d["compatible"] is False
    assert ".bat" not in d["unavailable_reason"]


def test_model_khong_tuong_thich_van_bao_dung_trang_thai_da_tai(ws):
    spec = mc.get("VieNeu-TTS-v3-Turbo (GPU)")
    with patch.object(mc, "is_downloaded", return_value=True):
        d = ws._mo_ta_model(spec, has_torch=False, has_cuda=False)

    assert d["compatible"] is False
    assert d["downloaded"] is True   # không nói dối là chưa tải


def test_danh_sach_model_giu_du_truong_frontend_cu_dang_doc(ws):
    spec = mc.get("VieNeu-TTS-v3-Turbo (int8)")
    with patch.object(mc, "is_downloaded", return_value=True):
        d = ws._mo_ta_model(spec, has_torch=False, has_cuda=False)

    for khoa in ("id", "name", "description", "supports_cloning",
                 "supports_streaming", "precision", "device", "available"):
        assert khoa in d, f"thiếu trường {khoa} mà frontend đang đọc"


@pytest.mark.parametrize("downloaded", [True, False])
def test_gpu_setup_required_even_when_model_already_downloaded(ws, downloaded):
    with patch.object(mc, "is_downloaded", return_value=downloaded), \
         patch.object(mc, "frozen_gpu_autoinstall_possible", return_value=True), \
         patch.object(ws, "cuda_is_available", return_value=False):
        d = ws._mo_ta_model(mc.get("VieNeu-TTS-v3-Turbo (GPU)"), has_torch=False, has_cuda=True)
    assert d["compatible"] is True
    assert d["downloaded"] is downloaded
    assert d["needs_gpu_setup"] is True


def test_cpu_does_not_request_gpu_setup(ws):
    with patch.object(mc, "is_downloaded", return_value=True), \
         patch.object(mc, "frozen_gpu_autoinstall_possible", return_value=True):
        d = ws._mo_ta_model(mc.get("VieNeu-TTS-v3-Turbo (int8)"), has_torch=False, has_cuda=False)
    assert d["needs_gpu_setup"] is False
