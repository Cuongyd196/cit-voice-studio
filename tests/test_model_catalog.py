"""Catalog mô hình: khai báo file, cờ tương thích, và cờ đã-tải.

Không test nào ở đây chạm mạng. `is_downloaded` được test bằng cách vá
`huggingface_hub.hf_hub_download`.
"""
from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

import pytest

from apps import model_catalog as mc


def test_moi_model_co_id_duy_nhat():
    ids = [s.id for s in mc.MODELS]
    assert len(ids) == len(set(ids))


def test_get_tra_ve_dung_spec_va_none_khi_khong_co():
    assert mc.get("VieNeu-TTS-v3-Turbo (int8)").precision == "int8"
    assert mc.get("khong-ton-tai") is None


def test_repo_files_phai_co_dung_mot_trong_files_hoac_patterns():
    with pytest.raises(ValueError):
        mc.RepoFiles(repo="r", files=("a",), patterns=("b",))
    with pytest.raises(ValueError):
        mc.RepoFiles(repo="r")


def test_allow_patterns_ghep_subfolder_vao_ten_file():
    src = mc.RepoFiles(repo="r", subfolder="onnx_int8", files=("config.json", "a.onnx"))
    assert src.allow_patterns == ("onnx_int8/config.json", "onnx_int8/a.onnx")


def test_allow_patterns_khong_ghep_gi_khi_khong_co_subfolder():
    src = mc.RepoFiles(repo="r", files=("denoiser.onnx",))
    assert src.allow_patterns == ("denoiser.onnx",)


def test_marker_paths_mac_dinh_bang_allow_patterns_voi_nguon_kieu_files():
    src = mc.RepoFiles(repo="r", subfolder="onnx_int8", files=("config.json",))
    assert src.marker_paths == ("onnx_int8/config.json",)


def test_marker_paths_dung_markers_khi_nguon_kieu_patterns():
    src = mc.RepoFiles(repo="r", patterns=("update/*",), markers=("update/config.json",))
    assert src.marker_paths == ("update/config.json",)


@pytest.mark.parametrize(
    "requires, has_torch, has_cuda, mong_doi",
    [
        ((), False, False, True),               # ONNX CPU chạy mọi máy
        ((), True, True, True),
        (("torch",), False, False, False),
        (("torch",), True, False, True),
        (("torch", "cuda"), True, False, False),
        (("torch", "cuda"), True, True, True),
        (("torch", "cuda"), False, False, False),
    ],
)
def test_compatible_theo_tung_to_hop(requires, has_torch, has_cuda, mong_doi):
    spec = mc.ModelSpec(
        id="x", name="x", description="x",
        sources=(mc.RepoFiles(repo="r", files=("a",)),),
        requires=requires, approx_bytes=1,
    )
    ok, ly_do = mc.compatible(spec, has_torch=has_torch, has_cuda=has_cuda)
    assert ok is mong_doi
    if mong_doi:
        assert ly_do is None
    else:
        assert ly_do and ly_do.strip()


def test_ly_do_thieu_torch_khac_ly_do_thieu_gpu():
    spec = mc.get("VieNeu-TTS-v3-Turbo (GPU)")
    _, thieu_torch = mc.compatible(spec, has_torch=False, has_cuda=False)
    _, thieu_gpu = mc.compatible(spec, has_torch=True, has_cuda=False)
    assert thieu_torch != thieu_gpu
    assert "bộ hỗ trợ GPU" in thieu_torch
    assert ".bat" not in thieu_torch


def test_can_autoinstall_torch_bo_qua_thieu_torch_nhung_van_doi_cuda():
    """Bản .exe có `uv`: thiếu torch không còn chặn — nhưng thiếu GPU thật vẫn chặn."""
    spec = mc.get("VieNeu-TTS-v3-Turbo (GPU)")
    ok, ly_do = mc.compatible(spec, has_torch=False, has_cuda=False, can_autoinstall_torch=True)
    assert ok is False
    assert "GPU NVIDIA" in ly_do  # chặn vì thiếu cuda, không phải vì thiếu torch

    ok, ly_do = mc.compatible(spec, has_torch=False, has_cuda=True, can_autoinstall_torch=True)
    assert ok is True
    assert ly_do is None


def test_can_autoinstall_torch_mac_dinh_tat_khong_doi_hanh_vi_cu():
    spec = mc.get("VieNeu-TTS-v3-Turbo (GPU)")
    # Co GPU nhung thieu torch: mac dinh khong tu cai torch -> van chan.
    ok, _ = mc.compatible(spec, has_torch=False, has_cuda=True)
    assert ok is False


@pytest.mark.parametrize("uv, possible", [(None, False), ("tools/uv.exe", True)])
def test_python_backend_autoinstall_uses_available_installer(uv, possible):
    with patch("apps.gpu_installer.find_uv", return_value=uv):
        assert mc.frozen_gpu_autoinstall_possible() is possible


def test_check_has_physical_nvidia_gpu_khong_nem_loi():
    """Chỉ cần chạy không vỡ; kết quả tuỳ máy nên không khẳng định True/False."""
    assert isinstance(mc.check_has_physical_nvidia_gpu(), bool)


def test_is_downloaded_true_khi_moi_marker_resolve_duoc():
    with patch("huggingface_hub.hf_hub_download", return_value="/cache/x") as m:
        assert mc.is_downloaded(mc.get("VieNeu-TTS-v3-Turbo (int8)")) is True
    assert m.called
    # Bắt buộc offline: dò cache không được ra mạng.
    assert all(c.kwargs.get("local_files_only") is True for c in m.call_args_list)


def test_is_downloaded_false_khi_mot_marker_thieu():
    def gia_lap(repo_id, filename, **kw):
        if filename.endswith("tokenizer.json"):
            raise OSError("thiếu file")
        return "/cache/x"

    with patch("huggingface_hub.hf_hub_download", side_effect=gia_lap):
        assert mc.is_downloaded(mc.get("VieNeu-TTS-v3-Turbo (int8)")) is False


def test_catalog_khong_keo_theo_torch():
    """Chạy trong tiến trình con: test_factory.py nhét torch giả vào sys.modules."""
    ma = (
        "import sys; import apps.model_catalog; "
        "assert 'torch' not in sys.modules, 'model_catalog keo theo torch'; "
        "assert 'onnxruntime' not in sys.modules, 'model_catalog keo theo onnxruntime'"
    )
    r = subprocess.run([sys.executable, "-c", ma], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_khong_lech_voi_ban_chep_vendored():
    """`_v3_turbo_engine/onnx_runtime_lite.py` giữ bản chép riêng vì thuộc upstream.

    Nó phải khớp với catalog, nếu không thì tải trước một đằng, engine đọc một nẻo.
    """
    from vieneu._v3_turbo_engine import onnx_runtime_lite as orl

    assert tuple(orl._GRAPH_FILES) == mc.GRAPH_FILES
    assert tuple(orl._CODEC_FILES) == mc.CODEC_FILES
    assert orl._V3_REPO == mc.V3_REPO
    assert orl._CODEC_REPO == mc.CODEC_REPO


def test_fetch_models_dung_chung_danh_sach_voi_catalog():
    import fetch_models

    assert fetch_models.GRAPH_FILES is mc.GRAPH_FILES
    assert fetch_models.CODEC_FILES is mc.CODEC_FILES
    assert fetch_models.ROOT_FILES is mc.ROOT_FILES


