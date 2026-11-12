"""Bản .app macOS: dữ liệu ghi được phải nằm NGOÀI gói (apps/runtime_paths_macos.py)."""
import sys
from pathlib import Path

from apps import runtime_paths, runtime_paths_macos as rm


def _fake_mac_app(monkeypatch, tmp_path):
    home = tmp_path / "home"
    bundle = tmp_path / "CIT Voice Studio.app" / "Contents"
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bundle / "MacOS" / "CIT Voice Studio"))
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle / "Frameworks"), raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home, bundle


def test_app_root_tren_mac_nam_ngoai_goi_app(monkeypatch, tmp_path):
    home, bundle = _fake_mac_app(monkeypatch, tmp_path)
    root = runtime_paths.app_root()
    assert root == home / "Library" / "Application Support" / "CIT Voice Studio"
    assert bundle not in root.parents


def test_windows_linux_van_dung_thu_muc_file_chay(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "CIT-Voice-Studio"))
    assert runtime_paths.app_root() == (tmp_path / "app").resolve()


def test_lan_dau_chep_mo_hinh_di_kem_ra_cache(monkeypatch, tmp_path):
    home, bundle = _fake_mac_app(monkeypatch, tmp_path)
    src = bundle / "Frameworks" / "models" / "hf_cache" / "hub" / "models--x" / "snapshots" / "abc"
    src.mkdir(parents=True)
    (src / "model.onnx").write_bytes(b"onnx")
    cache = rm.data_dir() / "models" / "hf_cache"

    rm.seed_bundled_models(cache)
    assert (cache / "hub" / "models--x" / "snapshots" / "abc" / "model.onnx").read_bytes() == b"onnx"
    assert not cache.with_name("hf_cache.seeding").exists()


def test_da_co_cache_thi_khong_chep_lai(monkeypatch, tmp_path):
    home, bundle = _fake_mac_app(monkeypatch, tmp_path)
    (bundle / "Frameworks" / "models" / "hf_cache" / "hub" / "moi").mkdir(parents=True)
    cache = tmp_path / "cache"
    (cache / "hub" / "cu").mkdir(parents=True)
    rm.seed_bundled_models(cache)
    assert not (cache / "hub" / "moi").exists()  # không đè lên mô hình người dùng đã tải thêm


def test_khong_kem_mo_hinh_thi_bo_qua(monkeypatch, tmp_path):
    _fake_mac_app(monkeypatch, tmp_path)
    cache = tmp_path / "cache"
    rm.seed_bundled_models(cache)
    assert not cache.exists()


def test_setup_hf_home_tren_mac_chep_mo_hinh_va_tro_ra_ngoai_goi(monkeypatch, tmp_path):
    home, bundle = _fake_mac_app(monkeypatch, tmp_path)
    (bundle / "Frameworks" / "models" / "hf_cache" / "hub" / "m").mkdir(parents=True)
    # setenv trước để monkeypatch ghi nhận biến và trả lại như cũ sau test —
    # setup_hf_home() tự ghi HF_HOME, không dọn thì rò sang test khác.
    monkeypatch.setenv("HF_HOME", "tam")
    monkeypatch.delenv("HF_HOME")
    cache = runtime_paths.setup_hf_home()
    assert cache == rm.data_dir() / "models" / "hf_cache"
    assert (cache / "hub" / "m").is_dir()
