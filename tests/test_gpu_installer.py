"""GPU setup regression checks; no downloads or physical GPU required."""
import io
import json
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps import gpu_installer as gi, model_catalog as mc


PATCH = f"{gi._runtime_tag()}.{sys.version_info.micro}"
EXE_REL = "python/python.exe" if sys.platform == "win32" else "python/bin/python3"


def _make_link(link, target):
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))  # như uv, không cần quyền admin
    else:
        link.symlink_to(target, target_is_directory=True)


def _downloads(*versions):
    return json.dumps([
        {"implementation": "cpython", "variant": v[1], "os": "windows" if sys.platform == "win32" else "linux",
         "arch": "x86_64", "version": v[0], "url": f"https://releases.astral.sh/github/x/{v[0]}-{v[1]}.tar.gz"}
        for v in versions
    ])


def _fake_download(url, dest, check_cancel, report, label="GPU"):
    """Gói python-build-standalone thu nhỏ: chỉ có python/python.exe."""
    check_cancel()
    report("Đang tải Python cho GPU... 1/1 MB")
    with tarfile.open(dest, "w:gz") as tar:
        data = b"fake"
        info = tarfile.TarInfo(EXE_REL)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


@pytest.fixture
def setup_env(monkeypatch, tmp_path):
    venv = tmp_path / "gpu" / gi._runtime_tag()
    monkeypatch.setattr(gi, "gpu_venv_dir", lambda: venv)
    monkeypatch.setattr(gi, "find_uv", lambda: "bundled-uv")
    monkeypatch.setattr(gi, "activate_gpu_venv", lambda: True)
    monkeypatch.setattr(gi.shutil, "disk_usage", lambda _: SimpleNamespace(free=20 * 1024**3))
    monkeypatch.setattr(gi, "_verify_cuda", Mock(side_effect=[ImportError("torch"), None]))
    monkeypatch.setattr(gi, "_download", Mock(side_effect=_fake_download))
    calls = []
    listing = {"out": _downloads((PATCH, "default"), (PATCH, "freethreaded"))}

    def run(args, check, **kwargs):
        check()
        calls.append(args)
        if args[1:3] == ["python", "list"]:
            return listing["out"] if args[3] == PATCH else _downloads(
                (f"{gi._runtime_tag()}.99", "default"), (f"{gi._runtime_tag()}.7", "default"))
        if args[1] == "venv":
            base = Path(args[args.index("--python") + 1])
            gi._venv_python(venv).parent.mkdir(parents=True, exist_ok=True)
            gi._venv_python(venv).touch()
            (venv / "pyvenv.cfg").write_text(f"home = {base.parent}" + chr(10), encoding="utf-8")
        venv.mkdir(parents=True, exist_ok=True)
        return ""

    monkeypatch.setattr(gi, "_run", run)
    return venv, calls, listing


def test_bundled_uv_available_without_path(monkeypatch, tmp_path):
    exe = tmp_path / "tools" / ("uv.exe" if sys.platform == "win32" else "uv")
    exe.parent.mkdir()
    exe.touch()
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(gi.shutil, "which", lambda _: None)
    assert gi.find_uv() == str(exe)
    assert mc.frozen_gpu_autoinstall_possible()
    assert mc.compatible(mc.get("VieNeu-TTS-v3-Turbo (GPU)"), has_torch=False,
                         has_cuda=True, can_autoinstall_torch=mc.frozen_gpu_autoinstall_possible())[0]


def test_install_uses_matching_python_separate_indexes_and_checks_cuda(setup_env):
    venv, calls, _ = setup_env
    progress = []
    gi.install_gpu_deps(on_progress=progress.append)
    assert not any(c[1:3] == ["python", "install"] for c in calls)  # uv python install tạo junction -> 448
    assert calls[0][:4] == ["bundled-uv", "python", "list", PATCH]
    assert gi._download.call_args.args[0].endswith(f"{PATCH}-default.tar.gz")  # không lấy bản freethreaded
    venv_call = next(c for c in calls if c[1] == "venv")
    base = Path(venv_call[venv_call.index("--python") + 1])
    assert gi._base_python_root() in base.parents and base.exists()
    assert "--managed-python" not in venv_call
    installs = [c for c in calls if c[1:3] == ["pip", "install"]]
    assert len(installs) == 2
    assert "torch==2.8.0" in installs[0]
    assert gi._PYTORCH_INDEX in installs[0]
    assert "transformers==4.57.6" in installs[1]
    assert "https://pypi.org/simple" in installs[1]
    assert "torch.ones" in calls[-1][-1]
    assert gi.gpu_deps_ready()
    assert len(progress) >= 4


def test_failed_validation_never_marks_ready(monkeypatch, setup_env):
    venv, _, _ = setup_env
    monkeypatch.setattr(gi, "_run", Mock(side_effect=RuntimeError("driver")))
    with pytest.raises(RuntimeError, match="driver"):
        gi.install_gpu_deps()
    assert not gi.gpu_deps_ready()


def test_retry_keeps_downloaded_runtime_when_current_process_needs_restart(monkeypatch, setup_env):
    monkeypatch.setattr(gi, "_verify_cuda", Mock(side_effect=ImportError("module already loaded")))
    with pytest.raises(RuntimeError, match="Khởi động lại"):
        gi.install_gpu_deps()
    assert gi.gpu_deps_ready()


def test_no_download_when_cuda_already_works(monkeypatch, setup_env):
    _, calls, _ = setup_env
    monkeypatch.setattr(gi, "_verify_cuda", lambda: None)
    gi.install_gpu_deps()
    assert calls == []


def test_disk_full_fails_before_downloading(monkeypatch, setup_env):
    _, calls, _ = setup_env
    monkeypatch.setattr(gi.shutil, "disk_usage", lambda _: SimpleNamespace(free=100))
    with pytest.raises(RuntimeError, match="12 GB"):
        gi.install_gpu_deps()
    assert calls == []


def test_cancel_stops_before_any_download(setup_env):
    _, calls, _ = setup_env
    class Cancelled(Exception):
        pass
    def cancel():
        raise Cancelled()
    with pytest.raises(Cancelled):
        gi.install_gpu_deps(check_cancel=cancel)
    assert calls == []


def test_marker_rejects_old_python_or_incomplete_install(monkeypatch, tmp_path):
    monkeypatch.setattr(gi, "gpu_venv_dir", lambda: tmp_path)
    marker = tmp_path / gi._MARKER_NAME
    marker.write_text("ok", encoding="utf-8")
    assert not gi.gpu_deps_ready()
    marker.write_text(gi._marker_value(), encoding="utf-8")
    assert gi.gpu_deps_ready()


def test_subprocess_nonzero_reports_output(tmp_path, monkeypatch):
    monkeypatch.setattr(gi, "gpu_venv_dir", lambda: tmp_path / "venv")
    with pytest.raises(RuntimeError, match="fixture-error"):
        gi._run([sys.executable, "-c", "import sys; sys.exit('fixture-error')"], lambda: None)


def test_cancel_terminates_running_installer(monkeypatch, tmp_path):
    monkeypatch.setattr(gi, "gpu_venv_dir", lambda: tmp_path / "venv")
    process = Mock(pid=999999, returncode=None)
    process.communicate.side_effect = [gi.subprocess.TimeoutExpired("uv", 0.5), ("", "")]
    monkeypatch.setattr(gi.subprocess, "Popen", Mock(return_value=process))
    kill = Mock()
    monkeypatch.setattr(gi.subprocess, "run", kill)
    checks = 0
    class Cancelled(Exception):
        pass
    def check():
        nonlocal checks
        checks += 1
        if checks == 3:
            raise Cancelled()
    with pytest.raises(Cancelled):
        gi._run(["uv", "pip", "install"], check)
    if sys.platform == "win32":
        assert kill.call_args.args[0] == ["taskkill", "/PID", "999999", "/T", "/F"]
    else:
        process.terminate.assert_called_once()


def test_junction_cua_ban_cu_bi_xoa(setup_env):
    """Bản cũ dùng `uv python install` và để lại junction `cpython-3.12-…`. uv quét
    thư mục đó mỗi lần tìm Python -> os error 448, nên junction phải biến mất."""
    install_dir = gi._python_install_dir()
    real = install_dir / f"cpython-{PATCH}-windows-x86_64-none"
    real.mkdir(parents=True)
    _make_link(install_dir / f"cpython-{gi._runtime_tag()}-windows-x86_64-none", real)
    gi.install_gpu_deps()
    assert not any(gi._is_link_dir(d) for d in install_dir.iterdir())
    assert real.exists()  # chỉ gỡ liên kết, không xoá thư mục đích


def test_venv_cu_khong_dung_python_goc_thi_dung_lai(setup_env):
    venv, calls, _ = setup_env
    gi._venv_python(venv).parent.mkdir(parents=True, exist_ok=True)
    gi._venv_python(venv).touch()
    old_home = gi._python_install_dir() / f"cpython-{gi._runtime_tag()}-windows-x86_64-none"
    (venv / "pyvenv.cfg").write_text(f"home = {old_home}" + chr(10), encoding="utf-8")
    assert not gi._venv_built_from_base_python(venv)

    gi.install_gpu_deps()
    assert any(c[1] == "venv" for c in calls)
    assert gi._venv_built_from_base_python(venv)


def test_khong_co_dung_ban_patch_thi_lay_ban_moi_nhat_cung_minor(setup_env):
    venv, calls, listing = setup_env
    listing["out"] = "[]"
    gi.install_gpu_deps()
    assert [c[3] for c in calls if c[1:3] == ["python", "list"]] == [PATCH, gi._runtime_tag()]
    assert gi._download.call_args.args[0].endswith(f"{gi._runtime_tag()}.99-default.tar.gz")


def test_python_goc_da_giai_nen_thi_khong_tai_lai(setup_env):
    gi.install_gpu_deps()
    gi._download.reset_mock()
    gi.gpu_venv_dir().joinpath(gi._MARKER_NAME).unlink()
    gi._verify_cuda.side_effect = [ImportError("torch"), None]
    gi.install_gpu_deps()
    gi._download.assert_not_called()


def test_tai_python_co_user_agent_va_lui_ve_github(monkeypatch, tmp_path):
    seen = []

    def fake_one(url, dest, check, report, label="GPU"):
        seen.append(url)
        if url.startswith(gi._ASTRAL_MIRROR):
            raise OSError("HTTP Error 403: Forbidden")

    monkeypatch.setattr(gi, "_download_one", fake_one)
    gi._download(gi._ASTRAL_MIRROR + "python-build-standalone/releases/download/1/a.tar.gz",
                 tmp_path / "a.tar.gz", lambda: None, lambda _m: None)
    assert seen[1] == "https://github.com/astral-sh/python-build-standalone/releases/download/1/a.tar.gz"


def test_ban_exe_thieu_module_con_thu_vien_chuan_thi_lay_tu_python_goc(monkeypatch, tmp_path):
    """Lỗi thật: bộ GPU cài xong nhưng nạp torch báo "No module named 'unittest.mock'".
    Gói `unittest` đã nạp từ bản .exe nên Python chỉ tìm `mock` trong
    `unittest.__path__` (thư mục `_internal`), không tra `sys.path`."""
    bundled = tmp_path / "_internal" / "cit_fakestd"
    bundled.mkdir(parents=True)
    (bundled / "__init__.py").write_text("", encoding="utf-8")
    base_home = tmp_path / "base-python" / "python"
    lib = base_home / ("Lib" if sys.platform == "win32" else f"lib/python{gi._runtime_tag()}")
    (lib / "cit_fakestd").mkdir(parents=True)
    (lib / "cit_fakestd" / "__init__.py").write_text("", encoding="utf-8")
    (lib / "cit_fakestd" / "mock.py").write_text("OK = 'tu python goc'", encoding="utf-8")
    venv = tmp_path / "venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text(f"home = {base_home}" + chr(10), encoding="utf-8")

    monkeypatch.syspath_prepend(str(bundled.parent))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    for name in ("cit_fakestd", "cit_fakestd.mock"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    import cit_fakestd
    with pytest.raises(ModuleNotFoundError):
        import cit_fakestd.mock  # noqa: F401  # đúng như trong bản .exe

    gi._append_base_stdlib(venv)
    import cit_fakestd.mock as m
    assert m.OK == "tu python goc"
    assert cit_fakestd.__file__.startswith(str(bundled))  # gói của bản .exe vẫn thắng


def test_chay_tu_source_khong_dung_toi_meta_path(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    before = list(sys.meta_path)
    gi._append_base_stdlib(tmp_path)
    assert sys.meta_path == before


def test_doi_ten_thu_muc_giai_nen_thu_lai_khi_bi_khoa(tmp_path, monkeypatch):
    """Defender giữ khoá thư mục vừa giải nén: lần đầu WinError 5, sau đó được."""
    from pathlib import Path

    from apps import gpu_installer as gi

    src = tmp_path / "3.12.13.extract"
    src.mkdir()
    dst = tmp_path / "3.12.13"
    goc = Path.replace
    lan = {"n": 0}

    def replace_bi_khoa(self, target):
        lan["n"] += 1
        if lan["n"] < 3:
            raise PermissionError(5, "Access is denied")
        return goc(self, target)

    monkeypatch.setattr(Path, "replace", replace_bi_khoa)
    gi._replace_retrying(src, dst, delay=0)
    assert dst.is_dir() and not src.exists() and lan["n"] == 3


def test_doi_ten_van_khoa_mai_thi_bao_loi(tmp_path, monkeypatch):
    from pathlib import Path

    import pytest

    from apps import gpu_installer as gi

    def luon_khoa(self, target):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", luon_khoa)
    with pytest.raises(PermissionError):
        gi._replace_retrying(tmp_path / "a", tmp_path / "b", attempts=3, delay=0)
