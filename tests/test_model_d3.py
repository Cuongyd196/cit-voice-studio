"""Mô hình VieNeu d3 (Blaze AI): khai báo trong catalog và nạp đúng trọng số.

Chỗ dễ hỏng: `load_model_instance` chọn nhánh theo chuỗi con ("gpu", "fp32") của tên
mô hình, mà tên d3 cũng chứa mấy chữ đó. Nhánh d3 đứng sai chỗ là app âm thầm nạp
trọng số VieNeu gốc - nghe gần giống nhau nên không ai phát hiện.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps import model_catalog as mc


def test_d3_co_trong_catalog_va_tro_ve_repo_mirror():
    cpu, gpu = mc.get(mc.D3_CPU_ID), mc.get(mc.D3_GPU_ID)
    assert cpu is not None and gpu is not None
    assert cpu.device == "cpu" and cpu.requires == ()
    assert gpu.device == "cuda" and set(gpu.requires) == {"torch", "cuda"}
    # Trọng số lấy từ mirror d3, không phải repo VieNeu gốc.
    assert cpu.sources[0].repo == mc.D3_REPO
    assert cpu.sources[0].subfolder == "onnx_update"
    assert cpu.sources[0].files == mc.GRAPH_FILES
    assert gpu.sources[0].repo == mc.D3_REPO
    assert all(s.repo != mc.V3_REPO for s in cpu.sources + gpu.sources)


def test_d3_khong_phai_mo_hinh_kem_san():
    assert mc.BUNDLED_MODEL_ID not in mc.D3_IDS


@pytest.fixture
def ws():
    from apps import web_stream
    return web_stream


@pytest.mark.parametrize("model_id, gpu", [(mc.D3_CPU_ID, False), (mc.D3_GPU_ID, True)])
def test_nap_d3_dung_repo_va_dtype(ws, model_id, gpu):
    fake = MagicMock()
    fake.load_extra_voices.return_value = 0
    with patch.object(ws, "Vieneu", return_value=fake) as V, \
         patch.object(ws, "cuda_is_available", return_value=True), \
         patch.object(ws, "gpu_name", return_value="Test GPU"), \
         patch.object(ws.gpu_memory, "apply"), \
         patch.object(ws, "_remember_model") as nho:
        ws.load_model_instance(model_id)

    kw = V.call_args.kwargs
    assert kw["backbone_repo"] == mc.D3_REPO
    if gpu:
        assert kw["backend"] == "pytorch"
        assert kw["dtype"] == "float32"          # bf16 làm mất phần cải tiến của d3
    else:
        assert kw["backend"] == "onnx" and kw["precision"] == "fp32"
    assert ws.current_model_info["name"] == model_id
    nho.assert_called_once_with(model_id)


def test_d3_gpu_bao_loi_khi_khong_co_cuda(ws):
    with patch.object(ws, "Vieneu") as V, \
         patch.object(ws, "cuda_is_available", return_value=False):
        with pytest.raises(RuntimeError, match="GPU"):
            ws.load_model_instance(mc.D3_GPU_ID)
    V.assert_not_called()
