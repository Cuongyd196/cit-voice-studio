"""Cài bộ tách âm cho Kokoro vào venv riêng, CHỈ khi người dùng bấm Tải về.

Vì sao không đóng gói sẵn: `kokoro-onnx` dựa vào `phonemizer` (GPLv3+) và
`espeakng-loader` (mang theo espeak-ng, GPLv3). Bộ cài CIT Voice Studio không chứa
thành phần GPL nào; các gói này do chính máy người dùng tải từ PyPI về khi họ chọn
mô hình Kokoro - giống cách `apps/gpu_installer.py` cài PyTorch.

Hai tầng, mỗi tầng một file dấu riêng trong venv:
  * Cơ bản (`install_deps`, lúc tải Kokoro): espeak - đủ cho tiếng Anh, Tây Ban
    Nha, Pháp, Ý, Bồ Đào Nha, Hindi. ~22 MB.
  * Gói ngôn ngữ (`install_pack`, khi người dùng bấm thêm): tiếng Nhật và tiếng
    Trung espeak đọc kém, nên dùng `misaki` (Apache, bộ tách âm gốc của Kokoro)
    với từ điển riêng - fugashi + unidic-lite cho tiếng Nhật (~250 MB trên đĩa,
    nhánh `cutlet` mặc định của Kokoro v1.0), jieba + pypinyin + cn2an cho tiếng
    Trung. KHÔNG cài extra `misaki[ja]`: nó kéo `pyopenjtalk`, không có wheel
    Windows (phải build bằng cmake) mà nhánh cutlet cũng không dùng - xem
    `kokoro_engine._ensure_pyopenjtalk_importable`.

Dùng lại nguyên cơ chế của bộ cài GPU (Python gốc tự giải nén để né junction
`os error 448`, `uv` đi kèm app, `_BaseStdlibFinder` cho thư viện chuẩn còn thiếu)
nhưng venv riêng và KHÔNG chứa numpy/onnxruntime. Mọi gói cài `--no-deps
--require-hashes` theo khoá trong `apps/kokoro_locks.py` (đúng phiên bản, đúng mã
băm, không kéo gói nào ngoài danh sách), và bỏ biến UV_*/PIP_* của máy để không
nguồn gói nào khác chen vào. Site-packages của venv được gắn vào CUỐI `sys.path` -
module của app luôn thắng.

KHÔNG giữ `model_lock` ở đây - chỉ được gọi từ thread nền của
`apps/model_downloader.py`, trước bước áp dụng.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from apps import gpu_installer
from apps.kokoro_locks import BASE_LOCK, PACK_LOCKS
from apps.runtime_paths import _is_writable, app_root

KOKORO_ONNX_VERSION = "0.6.1"
PHONEMIZER_VERSION = "3.4.0"
ESPEAKNG_LOADER_VERSION = "0.2.4"
# Bộ cơ bản, cài --no-deps: đây là TOÀN BỘ cây phụ thuộc của phonemizer 3.4.0
# (joblib kéo cloudpickle). Không để uv tự giải phụ thuộc: bản mới của một gói phụ
# ra sau ngày phát hành app sẽ không được kéo về. kokoro-onnx đòi thêm onnxruntime +
# numpy - app đã có, nên cố ý không có ở đây. Mã băm nằm ở apps/kokoro_locks.py.
BASE_PACKAGES = (
    f"kokoro-onnx=={KOKORO_ONNX_VERSION}", f"phonemizer=={PHONEMIZER_VERSION}",
    f"espeakng-loader=={ESPEAKNG_LOADER_VERSION}", "attrs==26.1.0", "cloudpickle==3.1.2",
    "dlinfo==2.0.0", "joblib==1.6.0", "typing-extensions==4.16.0",
)
# Ngôn ngữ đọc được chỉ với bộ cơ bản (espeak). Khớp kokoro_engine.LANGS.
BASE_LANGUAGES = frozenset({"en", "es", "fr", "it", "pt", "hi"})
# Gói ngôn ngữ, cài --no-deps: đây là TOÀN BỘ cây phụ thuộc cần cho `misaki.ja`
# (nhánh cutlet) và `misaki.zh` (v1.0) - đổi phiên bản phải kiểm lại. unidic-lite
# và jieba chỉ có sdist thuần Python: uv tự build, không cần compiler.
PACK_PACKAGES = {
    "ja": ("misaki==0.9.4", "addict==2.4.0", "fugashi==1.5.2", "unidic-lite==1.0.8",
           "jaconv==0.5.0", "mojimoji==0.0.13"),
    "zh": ("misaki==0.9.4", "addict==2.4.0", "ordered-set==4.1.0", "jieba==0.42.1",
           "pypinyin==0.55.0", "cn2an==0.5.24", "proces==0.1.7"),
}
_PACK_LABEL = {"ja": "tiếng Nhật", "zh": "tiếng Trung"}
# Câu thử viết bằng \u để dòng lệnh trên Windows không phụ thuộc bảng mã.
_PACK_PROBE = {
    "ja": ("from misaki import ja", "ja.JAG2P()('\\u3053\\u3093\\u306b\\u3061\\u306f')[0]"),
    "zh": ("from misaki import zh", "zh.ZHG2P()('\\u4f60\\u597d')[0]"),
}
_PYOPENJTALK_STUB = ("import sys, types; "
                     "sys.modules.setdefault('pyopenjtalk', types.ModuleType('pyopenjtalk')); ")
_MARKER_NAME = ".kokoro_deps_ready"
_WHAT = "bộ tách âm cho Kokoro"
_HINT = "Kiểm tra kết nối mạng và dung lượng ổ đĩa rồi thử lại."
_INDEX = ("--index-url", "https://pypi.org/simple")


def _marker_value() -> str:
    return json.dumps({
        "python": gpu_installer._runtime_tag(), "kokoro_onnx": KOKORO_ONNX_VERSION,
        "phonemizer": PHONEMIZER_VERSION, "espeakng_loader": ESPEAKNG_LOADER_VERSION,
        "schema": 1,
    })


def _pack_marker_value(code: str) -> str:
    return json.dumps({"python": gpu_installer._runtime_tag(),
                       "packages": list(PACK_PACKAGES[code]), "schema": 1})


def _pack_marker(code: str) -> Path:
    return venv_dir() / f".kokoro_pack_{code}"


def venv_dir() -> Path:
    """Cạnh app nếu ghi được, không thì %LOCALAPPDATA% (cài vào thư mục chỉ đọc)."""
    d = app_root() / "addons" / "kokoro" / gpu_installer._runtime_tag()
    if _is_writable(d.parent):
        return d
    base = os.getenv("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "CitVoiceStudio" / "addons" / "kokoro" / gpu_installer._runtime_tag()


def _base_python_present(venv: Path) -> bool:
    """Venv mượn Python gốc trong `gpu_venv/base-python` (xem `install_deps`). Người
    dùng xoá thư mục gpu_venv thì python của venv còn đó nhưng không chạy được nữa."""
    home = gpu_installer._venv_home(venv)
    return home is not None and home.is_dir()


def deps_ready() -> bool:
    """Đã cài xong VÀ venv còn dùng được: marker khớp, còn site-packages, còn Python
    gốc. Thiếu một trong số đó thì giao diện phải mời cài lại thay vì báo sẵn sàng."""
    venv = venv_dir()
    try:
        if (venv / _MARKER_NAME).read_text(encoding="utf-8") != _marker_value():
            return False
    except OSError:
        return False
    return (gpu_installer._venv_python(venv).exists()
            and gpu_installer._venv_site_packages(venv) is not None
            and _base_python_present(venv))


def pack_ready(code: str) -> bool:
    if code not in PACK_PACKAGES or not deps_ready():
        return False
    try:
        return _pack_marker(code).read_text(encoding="utf-8") == _pack_marker_value(code)
    except OSError:
        return False


def ready_languages() -> set[str]:
    """Ngôn ngữ đọc được với bộ tách âm đang có trên máy."""
    if not deps_ready():
        return set()
    return set(BASE_LANGUAGES) | {c for c in PACK_PACKAGES if pack_ready(c)}


def available() -> bool:
    """Máy này dùng được Kokoro: đã cài xong, hoặc có `uv` để cài lúc tải.

    macOS: chưa hỗ trợ (bộ cài Python gốc và espeak-ng chỉ làm cho Windows/Linux), kể
    cả khi máy có sẵn `uv` - nếu không, nút Tải về hiện ra rồi cài hỏng giữa chừng."""
    if sys.platform == "darwin":
        return False
    return deps_ready() or gpu_installer.find_uv() is not None


def activate() -> bool:
    """Gắn site-packages của venv vào CUỐI sys.path. Gọi nhiều lần vô hại."""
    if not deps_ready():
        return False
    site = gpu_installer._venv_site_packages(venv_dir())
    if site is None:
        return False
    if str(site) not in sys.path:
        sys.path.append(str(site))
    gpu_installer._append_base_stdlib(venv_dir())
    importlib.invalidate_caches()
    return True


def _verify_in_process() -> None:
    """Nạp thật trong tiến trình app và tách âm thử một câu. Bản .exe có thể thiếu
    module mà Python riêng thì có, nên phép thử ở venv chưa đủ."""
    from kokoro_onnx.tokenizer import Tokenizer

    if not Tokenizer().phonemize("Hello world.", "en-us"):
        raise RuntimeError("Bộ tách âm tiếng Anh không trả về kết quả.")


def _verify_pack_in_process(code: str) -> None:
    from apps.kokoro_engine import _ensure_pyopenjtalk_importable

    if code == "ja":
        _ensure_pyopenjtalk_importable()
        from misaki import ja

        ok = ja.JAG2P()("こんにちは")[0]
    else:
        from misaki import zh

        ok = zh.ZHG2P(version=None)("你好")[0]
    if not ok:
        raise RuntimeError(f"Bộ tách âm {_PACK_LABEL[code]} không trả về kết quả.")


def run_selftest() -> Path:
    """Chẩn đoán cho bản .exe: nạp bộ tách âm ngay trong tiến trình app và ghi kết
    quả ra `kokoro-selftest.txt` cạnh app. Bật bằng `CIT_KOKORO_SELFTEST=1`.

    Cài xong trong Python riêng chưa chắc nạp được vào bản đóng gói (thiếu module
    thư viện chuẩn hoặc module con của gói đã đóng gói, vd. `numpy.typing`)."""
    import traceback

    out = app_root() / "kokoro-selftest.txt"
    packs = [c for c in PACK_PACKAGES if pack_ready(c)]
    lines = [f"deps_ready={deps_ready()} activate={activate()} packs={packs} venv={venv_dir()}"]
    lines.append(f"torch_kokoro_device={os.getenv('CIT_KOKORO_TORCH_DEVICE', 'cuda')}")
    mods = ["phonemizer", "espeakng_loader", "joblib", "numpy.typing",
            "kokoro_onnx", "kokoro_onnx.tokenizer", "apps.kokoro_engine"]
    if "ja" in packs:
        mods += ["fugashi", "unidic_lite"]
    if "zh" in packs:
        mods += ["jieba", "pypinyin", "cn2an", "misaki.zh"]
    # Kokoro GPU: torch + transformers từ venv GPU, mã mô hình đóng gói trong app.
    from apps import gpu_installer as _gpu

    if _gpu.activate_gpu_venv():
        mods += ["torch", "transformers", "apps._kokoro_torch.model"]
    for mod in mods:
        try:
            m = importlib.import_module(mod)
            lines.append(f"OK   {mod} {getattr(m, '__version__', '')}")
        except BaseException:
            lines.append(f"LOI  {mod}\n{traceback.format_exc()}")
    checks = [("Anh", _verify_in_process)] + [
        (c, lambda c=c: _verify_pack_in_process(c)) for c in packs]
    for name, fn in checks:
        try:
            fn()
            lines.append(f"OK   tach am {name}")
        except BaseException:
            lines.append(f"LOI  tach am {name}\n{traceback.format_exc()}")
    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass
    return out


def _runner(check):
    def run(args, **kw):
        # strip_package_env: biến UV_*/PIP_* của máy (index phụ, file cấu hình...)
        # không được chen nguồn gói khác vào bản cài này.
        return gpu_installer._run(args, check, what=_WHAT, hint=_HINT,
                                  strip_package_env=True, **kw)
    return run


def _pip_install_locked(run, uv: str, py: str, lock: str, name: str) -> None:
    """Cài đúng các gói trong khoá: --no-deps (không kéo gói nào ngoài danh sách) và
    --require-hashes (file tải về phải khớp mã băm đã ghi lúc phát hành app)."""
    req = venv_dir() / f".kokoro-{name}.lock.txt"
    req.write_text(lock.strip() + "\n", encoding="utf-8")
    try:
        run([uv, "pip", "install", "--python", py, "--no-deps", "--require-hashes",
             "-r", str(req), *_INDEX])
    finally:
        req.unlink(missing_ok=True)


def install_deps(on_progress: Optional[Callable[[str], None]] = None,
                 check_cancel: Optional[Callable[[], None]] = None) -> None:
    """Dựng venv + cài bộ cơ bản, rồi nạp vào app. Đã cài và nạp được thì không làm gì."""
    report = on_progress or (lambda _m: None)
    check = check_cancel or (lambda: None)
    check()
    if activate():
        try:
            _verify_in_process()
            return
        except Exception:
            pass  # marker còn mà gói hỏng/thiếu: cài lại

    uv = gpu_installer.find_uv()
    if not uv:
        raise RuntimeError(
            "Bản ứng dụng thiếu công cụ cài bộ tách âm cho Kokoro. "
            "Hãy cập nhật hoặc cài lại bản CIT Voice Studio mới nhất."
        )
    run = _runner(check)

    venv = venv_dir()
    venv.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(venv.parent).free < 300 * 1024 ** 2:
        raise RuntimeError("Cần ít nhất 300 MB trống để cài bộ tách âm cho Kokoro. Dọn ổ đĩa rồi thử lại.")
    (venv / _MARKER_NAME).unlink(missing_ok=True)

    report("Đang chuẩn bị Python cho bộ tách âm...")
    if venv.exists() and not _base_python_present(venv):
        # Python gốc đã bị xoá (người dùng xoá gpu_venv): venv hỏng, dựng lại từ đầu.
        try:
            shutil.rmtree(venv)
        except OSError as exc:
            raise RuntimeError(
                "Không xoá được bộ tách âm cũ của Kokoro. Khởi động lại ứng dụng rồi "
                f"bấm Thử lại. Chi tiết: {exc}"
            ) from exc
    if not gpu_installer._venv_python(venv).exists():
        # Dùng chung Python gốc với bộ cài GPU: máy đã cài GPU thì không tải lại.
        base_python = gpu_installer._install_base_python(uv, check, report, label=_WHAT)
        run([uv, "venv", str(venv), "--python", str(base_python), "--no-python-downloads"])
    py = str(gpu_installer._venv_python(venv))

    report("Đang cài bộ tách âm (khoảng 22 MB)...")
    # --no-deps: kokoro-onnx đòi onnxruntime + numpy, app đã có; bản thứ hai trong
    # venv chỉ tốn chỗ và có nguy cơ bị nạp nhầm.
    venv.mkdir(parents=True, exist_ok=True)
    _pip_install_locked(run, uv, py, BASE_LOCK, "base")

    report("Đang kiểm tra bộ tách âm...")
    run([py, "-c",
         "import espeakng_loader as l; "
         "from phonemizer.backend.espeak.wrapper import EspeakWrapper as W; "
         "W.set_data_path(l.get_data_path()); W.set_library(l.get_library_path()); "
         "import phonemizer; assert phonemizer.phonemize('hello', 'en-us').strip()"],
        timeout=120)
    check()
    (venv / _MARKER_NAME).write_text(_marker_value(), encoding="utf-8")

    report("Đang nạp bộ tách âm vào ứng dụng...")
    try:
        if not activate():
            raise RuntimeError("Không tìm thấy thư viện vừa cài.")
        _verify_in_process()
    except Exception as exc:
        raise RuntimeError(
            "Bộ tách âm cho Kokoro đã cài nhưng chưa nạp được vào app. "
            f"Khởi động lại ứng dụng rồi bấm Thử lại. Chi tiết: {exc}"
        ) from exc


def install_pack(code: str, on_progress: Optional[Callable[[str], None]] = None,
                 check_cancel: Optional[Callable[[], None]] = None) -> None:
    """Cài bộ tách âm của một gói ngôn ngữ ("ja"/"zh") vào cùng venv. Cần bộ cơ
    bản - thiếu thì cài luôn. Đã cài và nạp được thì không làm gì."""
    if code not in PACK_PACKAGES:
        raise ValueError(f"Không có gói ngôn ngữ «{code}».")
    report = on_progress or (lambda _m: None)
    check = check_cancel or (lambda: None)
    ten = _PACK_LABEL[code]

    install_deps(on_progress=report, check_cancel=check)
    if pack_ready(code):
        try:
            _verify_pack_in_process(code)
            return
        except Exception:
            pass

    uv = gpu_installer.find_uv()
    if not uv:
        raise RuntimeError(
            f"Bản ứng dụng thiếu công cụ cài bộ tách âm {ten}. "
            "Hãy cập nhật hoặc cài lại bản CIT Voice Studio mới nhất."
        )
    run = _runner(check)
    venv = venv_dir()
    if shutil.disk_usage(venv.parent).free < 400 * 1024 ** 2:
        raise RuntimeError(f"Cần ít nhất 400 MB trống để cài {ten}. Dọn ổ đĩa rồi thử lại.")
    _pack_marker(code).unlink(missing_ok=True)
    py = str(gpu_installer._venv_python(venv))

    report(f"Đang cài bộ tách âm {ten}...")
    _pip_install_locked(run, uv, py, PACK_LOCKS[code], code)

    report(f"Đang kiểm tra bộ tách âm {ten}...")
    imp, probe = _PACK_PROBE[code]
    run([py, "-c", f"{_PYOPENJTALK_STUB}{imp}; assert {probe}"], timeout=300)
    check()
    _pack_marker(code).write_text(_pack_marker_value(code), encoding="utf-8")

    report(f"Đang nạp bộ tách âm {ten} vào ứng dụng...")
    try:
        importlib.invalidate_caches()
        _verify_pack_in_process(code)
    except Exception as exc:
        raise RuntimeError(
            f"Bộ tách âm {ten} đã cài nhưng chưa nạp được vào app. "
            f"Khởi động lại ứng dụng rồi bấm Thử lại. Chi tiết: {exc}"
        ) from exc
