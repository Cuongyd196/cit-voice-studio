"""Phần riêng Linux của bộ tự cài GPU (apps/gpu_installer_linux.py)."""
import sys

from apps import gpu_installer_linux as gl

TAG = f"python{sys.version_info.major}.{sys.version_info.minor}"


def test_home_la_thu_muc_bin_thi_lay_lib_o_thu_muc_cha(tmp_path):
    """Lỗi thật trên máy Linux: pyvenv.cfg ghi `home = .../python/bin`, còn thư viện
    chuẩn ở `.../python/lib/python3.12`. Ghép vào `home` thì không thấy `filecmp`
    -> "Could not import module 'PretrainedConfig'"."""
    python = tmp_path / "base-python" / "3.12.3" / "python"
    lib = python / "lib" / TAG
    (lib / "lib-dynload").mkdir(parents=True)
    (python / "bin").mkdir()
    assert gl.base_stdlib_roots(python / "bin") == [lib, lib / "lib-dynload"]


def test_home_khong_phai_bin_van_tim_duoc(tmp_path):
    lib = tmp_path / "lib" / TAG
    lib.mkdir(parents=True)
    assert gl.base_stdlib_roots(tmp_path) == [lib]


def test_khong_co_thu_vien_chuan_thi_tra_rong(tmp_path):
    assert gl.base_stdlib_roots(tmp_path / "bin") == []


def test_tien_trinh_con_dung_lai_ld_library_path_goc(monkeypatch):
    env = {"LD_LIBRARY_PATH": "/app/_internal", "LD_LIBRARY_PATH_ORIG": "/usr/local/cuda/lib64"}
    gl.clean_child_env(env)
    assert env == {"LD_LIBRARY_PATH": "/usr/local/cuda/lib64"}


def test_ban_dong_goi_khong_co_ban_goc_thi_bo_ld_library_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    env = {"LD_LIBRARY_PATH": "/app/_internal"}
    gl.clean_child_env(env)
    assert "LD_LIBRARY_PATH" not in env


def test_chay_tu_source_giu_nguyen_ld_library_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    env = {"LD_LIBRARY_PATH": "/opt/cuda/lib64"}
    gl.clean_child_env(env)
    assert env == {"LD_LIBRARY_PATH": "/opt/cuda/lib64"}
