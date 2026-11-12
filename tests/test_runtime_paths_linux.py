"""Bản .deb cài vào /opt (chỉ đọc): mô hình đi kèm phải được chép ra cache người dùng
(apps/runtime_paths_linux.py) thay vì tải lại."""
import sys

from apps import runtime_paths, runtime_paths_linux as rl


def _fake_linux_app(monkeypatch, tmp_path):
    app = tmp_path / "opt" / "cit-voice-studio"
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "CIT-Voice-Studio"))
    snap = app / "models" / "hf_cache" / "hub" / "models--x" / "snapshots" / "abc"
    snap.mkdir(parents=True)
    (snap / "model.onnx").write_bytes(b"onnx")
    return app


def test_cai_deb_chep_mo_hinh_ra_cache_nguoi_dung(monkeypatch, tmp_path):
    _fake_linux_app(monkeypatch, tmp_path)
    cache = tmp_path / "home" / "CitVoiceStudio" / "hf_cache"
    rl.seed_bundled_models(cache)
    assert (cache / "hub" / "models--x" / "snapshots" / "abc" / "model.onnx").read_bytes() == b"onnx"
    assert not cache.with_name("hf_cache.seeding").exists()


def test_ban_tar_gz_dung_tai_cho_khong_chep(monkeypatch, tmp_path):
    app = _fake_linux_app(monkeypatch, tmp_path)
    cache = app / "models" / "hf_cache"
    rl.seed_bundled_models(cache)
    assert not cache.with_name("hf_cache.seeding").exists()
    assert sorted(p.name for p in cache.iterdir()) == ["hub"]


def test_da_co_cache_thi_khong_chep_lai(monkeypatch, tmp_path):
    _fake_linux_app(monkeypatch, tmp_path)
    cache = tmp_path / "cache"
    (cache / "hub" / "cu").mkdir(parents=True)
    rl.seed_bundled_models(cache)
    assert not (cache / "hub" / "models--x").exists()


def test_setup_hf_home_khi_thu_muc_app_chi_doc(monkeypatch, tmp_path):
    app = _fake_linux_app(monkeypatch, tmp_path)
    user = tmp_path / "home"
    monkeypatch.setenv("LOCALAPPDATA", str(user))
    monkeypatch.setenv("HF_HOME", "tam")
    monkeypatch.delenv("HF_HOME")
    real = runtime_paths._is_writable
    monkeypatch.setattr(runtime_paths, "_is_writable",
                        lambda d: False if app in d.parents else real(d))
    cache = runtime_paths.setup_hf_home()
    assert cache == user / "CitVoiceStudio" / "hf_cache"
    assert (cache / "hub" / "models--x" / "snapshots" / "abc" / "model.onnx").is_file()
