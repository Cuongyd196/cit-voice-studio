"""Tự dựng venv riêng và cài PyTorch/CUDA cho bản đóng gói (.exe) khi cần.

Vì sao cần: bản .exe (PyInstaller --onedir) cố tình không đóng gói torch - nó đi
ngược cam kết torch-free và torch+cuda (vài GB) không hợp với bundle onedir. Khi
người dùng chọn một mô hình cần torch (v3 Turbo GPU) trên máy NVIDIA, ta dựng
một virtualenv RIÊNG cạnh exe, cài nhóm phụ thuộc tương đương `gpu-app` vào đó, rồi
nạp site-packages của venv đó vào `sys.path` tiến trình đang chạy.

KHÔNG giữ `model_lock` ở đây - module này chỉ được gọi từ thread nền của
`apps/model_downloader.py`, trước bước áp dụng (bước duy nhất giữ khoá).
"""
from __future__ import annotations

import importlib
import json
import os
from contextlib import contextmanager
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

from apps.runtime_paths import app_root, _is_writable, https_context

_TORCH_VERSION = "2.8.0"
_TORCHAUDIO_VERSION = "2.8.0"
_PYTORCH_INDEX = "https://download.pytorch.org/whl/cu128"
_MARKER_NAME = ".gpu_deps_ready"
_DLL_HANDLES = {}


def find_uv() -> Optional[str]:
    """Ưu tiên công cụ đi kèm app; không yêu cầu người dùng cấu hình PATH."""
    root = Path(getattr(sys, "_MEIPASS", app_root()))
    bundled = root / "tools" / ("uv.exe" if sys.platform == "win32" else "uv")
    return str(bundled) if bundled.is_file() else shutil.which("uv")


def _runtime_tag() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _marker_value() -> str:
    return json.dumps({"python": _runtime_tag(), "torch": _TORCH_VERSION, "schema": 1})


def _verify_cuda() -> None:
    import torch
    import torchaudio  # noqa: F401
    import transformers  # noqa: F401
    import safetensors  # noqa: F401
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch chưa nhận được GPU NVIDIA. Hãy cập nhật driver NVIDIA rồi thử lại.")
    value = (torch.ones(1, device="cuda") + 1).item()
    if value != 2:
        raise RuntimeError("Phép tính thử trên GPU thất bại.")


@contextmanager
def _external_dll_search():
    """Python con không được dùng DLL trong bundle PyInstaller của app."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes
    kernel = ctypes.windll.kernel32
    old = ctypes.create_unicode_buffer(32768)
    kernel.GetDllDirectoryW(len(old), old)
    kernel.SetDllDirectoryW(None)
    try:
        yield
    finally:
        kernel.SetDllDirectoryW(old.value or None)


def _run(args, check_cancel, *, timeout=3600, what="bộ hỗ trợ GPU",
         hint="Kiểm tra mạng, dung lượng và driver rồi thử lại.", strip_package_env=False):
    """Chạy nền, cho phép huỷ và không mở cửa sổ console trên Windows.

    `what`/`hint` chỉ đổi câu báo lỗi: bộ cài Kokoro (apps/kokoro_installer.py)
    dùng chung hàm này nhưng không liên quan GPU hay driver.
    `strip_package_env`: bỏ mọi biến UV_*/PIP_* của máy (UV_EXTRA_INDEX_URL,
    UV_FIND_LINKS, PIP_INDEX_URL...) để không nguồn gói nào khác chen vào bản cài -
    bộ cài Kokoro bật cờ này; bộ cài GPU giữ nguyên như cũ."""
    import time
    check_cancel()
    env = os.environ.copy()
    if strip_package_env:
        for key in [k for k in env if k.upper().startswith(("UV_", "PIP_"))]:
            del env[key]
    # Không cho Python riêng kế thừa môi trường Python của app đóng gói.
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env["UV_NO_PROGRESS"] = "1"
    env["UV_NO_CONFIG"] = "1"
    storage = gpu_venv_dir().parent
    env["UV_CACHE_DIR"] = str(storage / "cache")
    env["UV_PYTHON_INSTALL_DIR"] = str(storage / "python")
    if sys.platform != "win32":
        from apps.gpu_installer_linux import clean_child_env
        clean_child_env(env)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with _external_dll_search():
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace",
                                env=env, creationflags=flags)
    deadline = time.monotonic() + timeout
    try:
        while True:
            check_cancel()
            if time.monotonic() > deadline:
                raise RuntimeError(f"Cài {what} quá thời gian chờ. Kiểm tra mạng rồi thử lại.")
            try:
                out, err = proc.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, creationflags=flags)
        else:
            proc.terminate()
        proc.communicate()
        raise
    if proc.returncode:
        raise RuntimeError(f"Không cài/kiểm tra được {what}. {hint}\n{(err or out).strip()[-1500:]}")
    return out


def gpu_venv_dir() -> Path:
    """Thư mục venv riêng cho phụ thuộc GPU - cạnh exe, hoặc %LOCALAPPDATA% nếu chỉ đọc."""
    d = app_root() / "gpu_venv" / _runtime_tag()
    if _is_writable(d.parent):
        return d
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "CitVoiceStudio" / "gpu_venv" / _runtime_tag()


def _python_install_dir() -> Path:
    """Nơi uv cài Python riêng của nó (khớp `UV_PYTHON_INSTALL_DIR` trong `_run`).

    Bản mới không cài gì vào đây nữa; chỉ còn dọn junction do bản cũ để lại."""
    return gpu_venv_dir().parent / "python"


def _base_python_root() -> Path:
    """Python gốc tự tải + giải nén, KHÔNG do uv quản lý (xem `_install_base_python`)."""
    return gpu_venv_dir().parent / "base-python"


def _is_link_dir(p: Path) -> bool:
    try:
        return p.is_symlink() or p.is_junction()
    except OSError:
        return False


def _remove_minor_links(install_dir: Path) -> None:
    """Xoá junction `cpython-3.12-…` mà bản cũ (dùng `uv python install`) để lại.

    Còn junction thì uv quét thư mục cài Python là chết `os error 448` (xem
    `_install_base_python`). Xoá junction chỉ gỡ liên kết, không đụng thư mục đích.
    """
    if not install_dir.is_dir():
        return
    for entry in install_dir.iterdir():
        if entry.name.startswith("cpython-") and _is_link_dir(entry):
            if entry.is_junction():
                os.rmdir(entry)
            else:
                entry.unlink()


def _venv_home(venv_dir: Path) -> Optional[Path]:
    try:
        for line in (venv_dir / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "home":
                return Path(value.strip())
    except OSError:
        pass
    return None


def _venv_built_from_base_python(venv_dir: Path) -> bool:
    """Venv của bản cũ trỏ `home` vào Python do uv quản lý (qua junction) - hỏng
    vĩnh viễn trên máy chặn junction, phải dựng lại từ Python gốc tự giải nén."""
    home = _venv_home(venv_dir)
    return home is not None and _base_python_root() in home.parents


def _pick_download(entries: list, version: str) -> Optional[dict]:
    """Chọn bản CPython thường (không freethreaded/debug) cho đúng máy này."""
    import platform

    arch = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    os_name = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    ok = [
        e for e in entries
        if e.get("implementation") == "cpython" and e.get("variant") == "default"
        and e.get("os") == os_name and e.get("arch") == arch and e.get("url")
        and str(e.get("version", "")).startswith(version)
    ]
    if not ok:
        return None
    return max(ok, key=lambda e: tuple(int(x) for x in str(e["version"]).split(".") if x.isdigit()))


_ASTRAL_MIRROR = "https://releases.astral.sh/github/"
_GITHUB = "https://github.com/astral-sh/"


def _download(url: str, dest: Path, check_cancel, report, label: str = "GPU") -> None:
    """Tải có User-Agent (releases.astral.sh trả 403 cho UA mặc định của urllib);
    mirror của Astral lỗi thì lùi về chính file đó trên GitHub."""
    urls = [url]
    if url.startswith(_ASTRAL_MIRROR):
        urls.append(_GITHUB + url[len(_ASTRAL_MIRROR):])
    for i, u in enumerate(urls):
        try:
            _download_one(u, dest, check_cancel, report, label)
            return
        except OSError:  # URLError/HTTPError đều là OSError
            if i == len(urls) - 1:
                raise


def _download_one(url: str, dest: Path, check_cancel, report, label: str = "GPU") -> None:
    import urllib.request

    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "CIT-Voice-Studio (python-urllib)"})
    with urllib.request.urlopen(req, timeout=60, context=https_context()) as resp, \
            open(tmp, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            check_cancel()
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                report(f"Đang tải Python cho {label}... {done >> 20}/{total >> 20} MB")
    tmp.replace(dest)


def _install_base_python(uv: str, check_cancel, report=lambda _m: None, label: str = "GPU") -> Path:
    """Tải Python standalone cùng bản với app, giải nén vào thư mục THƯỜNG rồi trả
    về đường dẫn `python.exe`.

    Vì sao không dùng `uv python install`: uv 0.11 luôn tạo thêm junction
    `cpython-3.12-…` trỏ sang bản patch rồi đọc lại nó. Windows 11 bật Redirection
    Guard chặn đi qua junction do tài khoản thường tạo -> `Failed to create Python
    minor version link directory ... untrusted mount point (os error 448)`, và uv
    không có tuỳ chọn tắt junction. Nên chỉ hỏi uv địa chỉ tải (`uv python list
    --only-downloads`, không ghi gì ra đĩa), còn tải + giải nén ta tự làm.

    Xin đúng bản patch của app; không có thì lùi về bản mới nhất cùng minor - cùng
    ABI nên extension native vẫn nạp được.
    """
    import json
    import tarfile

    root = _base_python_root()
    exe_rel = "python/python.exe" if sys.platform == "win32" else "python/bin/python3"
    for existing in sorted(root.glob("*/" + exe_rel)) if root.is_dir() else []:
        return existing

    patch = f"{_runtime_tag()}.{sys.version_info.micro}"
    chosen = None
    for request in (patch, _runtime_tag()):
        out = _run([uv, "python", "list", request, "--only-downloads", "--output-format", "json"],
                   check_cancel, timeout=120)
        try:
            chosen = _pick_download(json.loads(out or "[]"), request)
        except ValueError:
            chosen = None
        if chosen:
            break
    if not chosen:
        raise RuntimeError(f"Không tìm thấy bản Python phù hợp cho {label}.")

    target = root / str(chosen["version"])
    archive = root / "python.tar.gz"
    staging = root / (target.name + ".extract")
    root.mkdir(parents=True, exist_ok=True)
    if staging.exists():
        shutil.rmtree(staging)
    report(f"Đang tải Python cho {label}...")
    _download(chosen["url"], archive, check_cancel, report, label)
    report(f"Đang giải nén Python cho {label}...")
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(staging, filter="data")
    archive.unlink(missing_ok=True)
    if target.exists():
        shutil.rmtree(target)
    _replace_retrying(staging, target)
    exe = target / exe_rel
    if not exe.exists():
        raise RuntimeError("Gói Python tải về không đúng cấu trúc.")
    return exe


def _replace_retrying(src: Path, dst: Path, attempts: int = 30, delay: float = 0.5) -> None:
    """Đổi tên thư mục vừa giải nén. Windows Defender quét các file mới tạo và giữ
    khoá thư mục vài giây, nên `replace` báo "Access is denied" (WinError 5) ngay
    sau giải nén; thử lại tối đa ~15 giây trước khi báo lỗi thật."""
    import time

    for i in range(attempts):
        try:
            src.replace(dst)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(delay)


def _venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _venv_site_packages(venv_dir: Path) -> Optional[Path]:
    if sys.platform == "win32":
        lib = venv_dir / "Lib" / "site-packages"
        return lib if lib.exists() else None
    for p in (venv_dir / "lib").glob("python*/site-packages"):
        return p
    return None


def gpu_deps_ready() -> bool:
    """Marker cho biết venv GPU đã cài xong ở lần chạy trước chưa."""
    try:
        return (gpu_venv_dir() / _MARKER_NAME).read_text(encoding="utf-8") == _marker_value()
    except OSError:
        return False


class _BaseStdlibFinder:
    """Tìm module thư viện chuẩn còn thiếu trong Python gốc, theo ĐỦ tên có chấm.

    Không thể chỉ thêm `Lib` vào `sys.path`: `unittest` đã nạp từ bản .exe thì
    `unittest.mock` chỉ được tìm trong `unittest.__path__` (thư mục trong `_internal`),
    không bao giờ tra `sys.path`. Finder này tự ghép `Lib/unittest/` rồi tìm `mock`.
    Đứng CUỐI `sys.meta_path` nên chỉ được hỏi khi FrozenImporter và PathFinder đều
    chịu - module bản .exe đã có luôn thắng.
    """

    def __init__(self, roots: list[Path]):
        self.roots = roots

    def find_spec(self, fullname, path=None, target=None):
        from importlib.machinery import PathFinder

        parts = fullname.split(".")
        dirs = [str(r.joinpath(*parts[:-1])) for r in self.roots]
        return PathFinder.find_spec(fullname, [d for d in dirs if os.path.isdir(d)])


def _append_base_stdlib(venv_dir: Path) -> None:
    """Bản .exe chỉ đóng gói những module thư viện chuẩn mà APP import. torch và
    transformers cần thêm (vd. `unittest.mock` -> "No module named 'unittest.mock'"
    dù bộ GPU đã cài xong). Lấy phần còn thiếu từ thư viện chuẩn của Python gốc -
    cùng bản với app, xem `_install_base_python`.

    Chạy từ source thì trình thông dịch đã đủ thư viện chuẩn, không cần.
    """
    if not getattr(sys, "frozen", False):
        return
    home = _venv_home(venv_dir)
    if home is None:
        return
    if sys.platform == "win32":
        roots = [home / s for s in ("Lib", "DLLs") if (home / s).is_dir()]
    else:
        from apps.gpu_installer_linux import base_stdlib_roots
        roots = base_stdlib_roots(home)
    if roots and not any(isinstance(f, _BaseStdlibFinder) for f in sys.meta_path):
        sys.meta_path.append(_BaseStdlibFinder(roots))


def activate_gpu_venv() -> bool:
    """Nạp site-packages của venv GPU vào sys.path tiến trình hiện tại.

    Gọi TRƯỚC lần `import torch` đầu tiên trong tiến trình (app khởi động, và lại
    sau khi cài xong). An toàn gọi nhiều lần - no-op nếu đã nạp hoặc chưa có venv.
    """
    if not gpu_deps_ready():
        return False
    site = _venv_site_packages(gpu_venv_dir())
    if site is None:
        return False
    site_str = str(site)
    if site_str not in sys.path:
        sys.path.insert(0, site_str)
    _append_base_stdlib(gpu_venv_dir())
    # torch mang theo DLL native trong torch/lib - trên Windows, PATH thôi không đủ
    # từ Python 3.8 trở đi, phải khai báo tường minh bằng os.add_dll_directory.
    torch_lib = site / "torch" / "lib"
    if sys.platform == "win32" and torch_lib.exists():
        try:
            if str(torch_lib) not in _DLL_HANDLES:
                _DLL_HANDLES[str(torch_lib)] = os.add_dll_directory(str(torch_lib))
        except Exception:
            pass
    return True


def run_gpu_selftest() -> Path:
    """Chẩn đoán: import bộ GPU NGAY TRONG tiến trình app, ghi kết quả ra
    `gpu-selftest.txt` cạnh app. Bật bằng `CIT_GPU_SELFTEST=1`.

    Kiểm tra trong Python riêng (`install_gpu_deps`) có thể qua trong khi nạp vào bản
    .exe vẫn hỏng - vd. thiếu `unittest.mock` - nên cần một phép thử ở đúng chỗ đó.
    """
    import traceback

    out = app_root() / "gpu-selftest.txt"
    lines = [f"gpu_deps_ready={gpu_deps_ready()} venv={gpu_venv_dir()}"]
    for mod in ("torch", "torchaudio", "safetensors", "transformers",
                "transformers.models.auto", "unittest.mock",
                "transformers.configuration_utils",
                "vieneu._v3_turbo_engine.configuration_v3_turbo",
                "vieneu._v3_turbo_engine.inference_v3_turbo", "vieneu.v3_turbo_serve.engine"):
        try:
            m = importlib.import_module(mod)
            lines.append(f"OK   {mod} {getattr(m, '__version__', '')}")
        except BaseException:
            lines.append(f"LOI  {mod}\n{traceback.format_exc()}")
    # Thuộc tính nạp lười của transformers: `import transformers` qua được nhưng lấy
    # `PretrainedConfig` mới thật sự import configuration_utils (lỗi thật khách gặp).
    try:
        from transformers import PretrainedConfig  # noqa: F401
        lines.append("OK   transformers.PretrainedConfig")
    except BaseException:
        lines.append(f"LOI  transformers.PretrainedConfig\n{traceback.format_exc()}")
    try:
        import torch
        lines.append(f"cuda={torch.cuda.is_available()}")
    except BaseException:
        pass
    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass
    return out


def install_gpu_deps(on_progress: Optional[Callable[[str], None]] = None,
                     check_cancel: Optional[Callable[[], None]] = None) -> None:
    """Chỉ tải thư viện GPU khi người dùng chọn; chạy trong worker tải mô hình."""
    report = on_progress or (lambda message: None)
    check = check_cancel or (lambda: None)
    check()
    activate_gpu_venv()
    try:
        _verify_cuda()
        return
    except Exception:
        pass

    uv = find_uv()
    if not uv:
        raise RuntimeError("Bản ứng dụng thiếu công cụ cài GPU. Hãy cập nhật hoặc cài lại bản CIT Voice Studio mới nhất.")

    venv = gpu_venv_dir()
    venv.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(venv.parent).free < 12 * 1024 ** 3:
        raise RuntimeError("Cần ít nhất 12 GB trống để tải và cài bộ hỗ trợ GPU. Dọn ổ đĩa rồi thử lại.")
    marker = venv / _MARKER_NAME
    marker.unlink(missing_ok=True)
    report("Đang chuẩn bị Python cho GPU...")
    _remove_minor_links(_python_install_dir())
    if venv.exists() and not _venv_built_from_base_python(venv):
        shutil.rmtree(venv)
    if not _venv_python(venv).exists():
        base_python = _install_base_python(uv, check, report)
        _run([uv, "venv", str(venv), "--python", str(base_python), "--no-python-downloads"], check)
    py = str(_venv_python(venv))
    _run([py, "-c", f"import sys; assert sys.version_info[:2] == {sys.version_info[:2]!r}, 'Python GPU không khớp phiên bản app'"], check, timeout=60)
    report("Đang tải và cài PyTorch/CUDA (vài GB, có thể mất nhiều phút)...")
    _run([uv, "pip", "install", "--python", py,
          f"torch=={_TORCH_VERSION}", f"torchaudio=={_TORCHAUDIO_VERSION}",
          "--index-url", _PYTORCH_INDEX], check)
    report("Đang tải các thư viện hỗ trợ giọng nói...")
    _run([uv, "pip", "install", "--python", py,
          "transformers==4.57.6", "safetensors", "--index-url", "https://pypi.org/simple"], check)
    report("Đang kiểm tra phép tính trên GPU NVIDIA...")
    _run([py, "-c", "import torch, torchaudio, transformers, safetensors; "
          "assert torch.cuda.is_available(), 'GPU chưa sẵn sàng. Hãy cập nhật driver NVIDIA'; "
          "assert (torch.ones(1, device='cuda') + 1).item() == 2"], check, timeout=120)
    check()
    marker.write_text(_marker_value(), encoding="utf-8")
    try:
        report("Đang nạp bộ hỗ trợ GPU vào ứng dụng...")
        if not activate_gpu_venv():
            raise RuntimeError("Không tìm thấy thư viện GPU vừa cài.")
        importlib.invalidate_caches()
        _verify_cuda()
    except Exception as exc:
        # Tiến trình Python riêng đã kiểm tra thành công. Giữ marker để lần mở
        # app tiếp theo nạp venv trước mọi import (tránh module cũ đang trong RAM).
        raise RuntimeError(f"Bộ GPU đã tải nhưng chưa nạp được vào app. Khởi động lại ứng dụng rồi bấm Thử lại. Chi tiết: {exc}") from exc
