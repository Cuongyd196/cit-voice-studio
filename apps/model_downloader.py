"""Tải mô hình ở thread nền, có tiến trình và huỷ được.

Vì sao cần: trước đây chọn FP32 rồi bấm nạp là một cú `hf_hub_download` ~453MB
chạy ngay trong lòng request HTTP, dưới `model_lock` - mọi yêu cầu đọc khác bị
chặn theo, và giao diện chỉ có một spinner đứng yên vài phút.

Bất biến quan trọng nhất: trong suốt lúc tải KHÔNG giữ `model_lock`. Chỉ bước
áp dụng cuối cùng mới khoá, và nó chỉ mất vài giây.
"""
from __future__ import annotations

import threading
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from fnmatch import fnmatch

from apps import model_catalog

# Trạng thái công việc tải. Một job tại một thời điểm.
_state_lock = threading.Lock()
_cancel = threading.Event()
_thread: Optional[threading.Thread] = None

_STATE_RONG: Dict[str, Any] = {
    "state": "idle",          # idle | downloading | applying | ready | error | cancelled
    "model_id": None,
    "pack": None,             # gói ngôn ngữ Kokoro đang tải ("ja"/"zh"), None = cả mô hình
    "percent": 0.0,
    "done_bytes": 0,
    "total_bytes": 0,
    "current_file": "",
    "message": "",
}

_state: Dict[str, Any] = dict(_STATE_RONG)


class Cancelled(Exception):
    """Người dùng bấm Huỷ giữa chừng."""


def _reset_state() -> None:
    with _state_lock:
        _state.clear()
        _state.update(_STATE_RONG)


def get_state() -> Dict[str, Any]:
    """Bản sao state - người gọi sửa vào đây cũng không đụng được state thật."""
    with _state_lock:
        return dict(_state)


def _set_state(**kw: Any) -> None:
    with _state_lock:
        _state.update(kw)
        total = _state.get("total_bytes") or 0
        done = _state.get("done_bytes") or 0
        _state["percent"] = min(100.0, done * 100.0 / total) if total > 0 else 0.0


# Tiến trình của nguồn (repo) đang tải. `snapshot_download` chỉ đưa cho ta thanh
# đếm SỐ FILE, nên số byte hiển thị được suy ra: byte các nguồn đã xong, cộng
# phần tỉ lệ của nguồn hiện tại. Một job tại một thời điểm (xem `start()`), nên
# hai biến toàn cục này không cần khoá riêng.
_nguon_base_bytes = 0
_nguon_bytes = 0


def _dat_nguon(base_bytes: int, bytes_nguon: int) -> None:
    global _nguon_base_bytes, _nguon_bytes
    _nguon_base_bytes, _nguon_bytes = int(base_bytes), int(bytes_nguon)


class _ProgressTqdm:
    """Thay cho tqdm trong `snapshot_download`, để đọc tiến trình và cắt giữa chừng.

    huggingface_hub chạy `snapshot_download` qua `tqdm.contrib.concurrent.thread_map`,
    nên lớp này phải đủ giống tqdm ở ba chỗ - thiếu chỗ nào thì việc tải hỏng, và
    hỏng lặng lẽ:

      * `get_lock` / `set_lock` là **classmethod**: `ensure_lock()` gọi chúng trước
        khi mở executor. Thiếu thì cả lệnh tải chết ngay với
        ``type object '_ProgressTqdm' has no attribute 'get_lock'``.
      * Lặp được VÀ phải yield lại từng phần tử: `thread_map` bọc `ex.map(...)`
        vào thanh tiến trình rồi `list(...)` nó. Trả về iterator rỗng thì executor
        không bị tiêu thụ - không file nào được tải mà cũng không có lỗi nào.
      * `total` ở đây là SỐ FILE, không phải byte: hf không truyền `tqdm_class`
        xuống từng lượt tải file (xem docstring `snapshot_download`), nên không có
        tiến trình theo byte để đọc. Byte hiển thị suy ra từ `_dat_nguon()`.

    `snapshot_download` không nhận cờ huỷ, nên ném exception từ `update()` là
    cách duy nhất dừng được nó - huỷ có hiệu lực ở ranh giới giữa hai file.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.total = kwargs.get("total") or 0
        self.n = 0
        self._iterable = args[0] if args else kwargs.get("iterable")
        desc = kwargs.get("desc")
        if desc:
            _set_state(current_file=str(desc))

    @classmethod
    def get_lock(cls):
        lock = getattr(cls, "_lock", None)
        if lock is None:
            lock = threading.RLock()
            cls._lock = lock
        return lock

    @classmethod
    def set_lock(cls, lock: Any) -> None:
        cls._lock = lock

    def update(self, n: int = 1) -> None:
        if _cancel.is_set():
            raise Cancelled()
        self.n += n
        if self.total > 0:
            xong = min(self.n, self.total) / self.total
            _set_state(done_bytes=_nguon_base_bytes + int(_nguon_bytes * xong))

    def __iter__(self):
        if self._iterable is None:
            return
        for item in self._iterable:
            self.update(1)
            yield item

    # huggingface_hub dùng thanh tiến trình như context manager và gọi vài
    # phương thức phụ; nuốt hết cho êm.
    def __enter__(self) -> "_ProgressTqdm":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        pass

    def set_description(self, desc: Optional[str] = None, **_: Any) -> None:
        if desc:
            _set_state(current_file=str(desc))

    def set_postfix(self, *a: Any, **k: Any) -> None:
        pass

    def refresh(self, *a: Any, **k: Any) -> None:
        pass

    def reset(self, total: Optional[int] = None) -> None:
        self.total = total or 0
        self.n = 0



# web_stream trỏ cái này về `_friendly_load_error` lúc import. Mặc định là `str`
# để module chạy độc lập được trong test.
apply_error_formatter = str


def _chuoi_loi_mang(e: BaseException) -> str:
    """Đổi lỗi kỹ thuật của huggingface_hub sang câu người dùng làm theo được."""
    ten = type(e).__name__
    nhan_dang_mang = (
        "ConnectionError", "LocalEntryNotFoundError", "HfHubHTTPError",
        "ReadTimeout", "ConnectTimeout", "Timeout", "SSLError", "ProxyError",
    )
    if ten in nhan_dang_mang or "connection" in str(e).lower():
        return (
            "Không kết nối được HuggingFace để tải mô hình. "
            "Kiểm tra mạng hoặc proxy rồi bấm Thử lại. "
            "Mô hình đang dùng vẫn hoạt động bình thường."
        )
    return f"Không tải được mô hình: {e}"


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

# Bọc lại hai hàm của huggingface_hub thành tên cấp module, để test vá được
# mà không phải đụng vào thư viện.
def _model_info(repo: str, revision: Optional[str] = None):
    from huggingface_hub import HfApi

    return HfApi().model_info(repo, revision=revision, files_metadata=True)


def _prime_symlink_check(repo: str) -> None:
    """Dò trước, trong MỘT luồng, xem thư mục cache của repo có tạo được symlink không.

    Vì sao cần: `are_symlinks_supported()` của huggingface_hub ghi sẵn `True` vào
    cache rồi mới thử, và không có khoá. `snapshot_download` chạy nhiều luồng, nên
    luồng đến sau đọc được `True` tạm thời đó, gọi `os.symlink` và chết với
    `[WinError 1314] A required privilege is not held by the client` trên máy Windows
    không bật Developer Mode (đo trên máy dev: 3/4 luồng nhận `True` sai). Dò trước
    ở đây thì các luồng tải chỉ đọc kết quả đúng và tự chuyển sang chép file.

    Xoá kết quả cũ trước khi dò: lần tải hỏng trước có thể đã để lại `True` sai,
    khiến nút "Thử lại" hỏng mãi tới khi khởi động lại app.
    """
    try:
        from huggingface_hub import constants
        from huggingface_hub import file_download as fd

        folder = Path(constants.HF_HUB_CACHE) / fd.repo_folder_name(repo_id=repo, repo_type="model")
        folder.mkdir(parents=True, exist_ok=True)
        fd._are_symlinks_supported_in_dir.pop(str(folder.expanduser().resolve()), None)
        fd.are_symlinks_supported(folder)
    except Exception as e:
        # API nội bộ của huggingface_hub đổi thì bỏ qua - tệ nhất là quay về hành vi cũ.
        print(f"[Tải mô hình] Không dò trước được symlink cho {repo}: {e}")


def _snapshot_download(set_main_ref: bool = True, **kwargs):
    """`set_main_ref=False` cho nguồn ghim revision cố định trong catalog (Supertonic,
    Kokoro): sha đó không phải `main` của repo, và `is_downloaded` tự hỏi đúng sha."""
    from huggingface_hub import snapshot_download

    _prime_symlink_check(kwargs["repo_id"])
    result = snapshot_download(**kwargs)
    if set_main_ref and kwargs.get("revision"):
        _write_main_ref(kwargs["repo_id"], kwargs["revision"])
    return result


def _write_main_ref(repo: str, sha: str) -> None:
    """Trỏ `refs/main` về đúng bản vừa tải.

    Tải theo sha (bắt buộc, xem bước 3 trong `_chay`) thì huggingface_hub không ghi
    `refs/main`. Mà mọi lần tìm offline - `model_catalog.is_downloaded()` và lúc nạp
    mô hình - đều hỏi `main`, nên mô hình tải lần đầu qua nút Tải về bị báo "chưa
    tải" mãi dù đủ file. Sha này chính là `main` lúc tải (lấy từ `model_info`).
    """
    from huggingface_hub import constants
    from huggingface_hub import file_download as fd

    ref = Path(constants.HF_HUB_CACHE) / fd.repo_folder_name(repo_id=repo, repo_type="model") / "refs" / "main"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(sha)




def _hf_cache_dir() -> Path:
    import os

    return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))


def _doc_gon(n: int) -> str:
    return f"{n / (1024 * 1024):.0f} MB" if n < 1024 ** 3 else f"{n / (1024 ** 3):.1f} GB"


def _du_cho_trong_o(total_bytes: int) -> tuple[bool, str]:
    """Chặn trước khi tải, thay vì đổ 400MB xuống rồi mới vỡ vì hết ổ."""
    can = int(total_bytes * 1.2)
    try:
        con = shutil.disk_usage(str(_hf_cache_dir())).free
    except Exception:
        return True, ""  # không đo được thì cứ thử, đừng chặn oan
    if con < can:
        return False, (
            f"Ổ đĩa chỉ còn {_doc_gon(con)}, cần khoảng {_doc_gon(can)} để tải mô hình này. "
            "Dọn bớt dung lượng rồi thử lại."
        )
    return True, ""


def _khop(ten_file: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(ten_file, p) for p in patterns)


def _can_tu_cai_gpu_deps(spec) -> bool:
    """Dùng cùng điều kiện với Settings, kể cả backend chạy bằng Python riêng."""
    return "torch" in spec.requires and model_catalog.frozen_gpu_autoinstall_possible()


def _chay(spec, auto_apply: bool, apply_fn) -> None:
    """Thân worker. Chạy đồng bộ - `start()` mới là cái ném nó sang thread nền.

    KHÔNG chạm `model_lock` ở bất kỳ bước nào trừ `apply_fn` cuối cùng.
    """
    _cancel.clear()
    _set_state(
        state="downloading", model_id=spec.id, pack=None, percent=0.0, done_bytes=0,
        total_bytes=0, current_file="", message="", phase="model",
    )

    try:
        # 1. Ghim sha + đo tổng byte thật. Mạng hỏng ở đây thì cache chưa bị đụng.
        ke_hoach = []
        tong = 0
        for src in spec.sources:
            info = _model_info(src.repo, src.revision)
            byte_repo = sum(
                getattr(s, "size", 0) or 0
                for s in getattr(info, "siblings", [])
                if _khop(getattr(s, "rfilename", ""), src.allow_patterns)
            )
            tong += byte_repo
            ke_hoach.append((src, src.revision or info.sha, byte_repo))

        if tong <= 0:
            tong = spec.approx_bytes  # metadata không có size thì dùng con số ước lượng
            # Không đo được từng nguồn thì chia đều, để thanh tiến trình vẫn nhúc nhích.
            deu = tong // max(len(ke_hoach), 1)
            ke_hoach = [(src, sha, deu) for src, sha, _ in ke_hoach]
        _set_state(total_bytes=tong)

        # 2. Đủ chỗ trên ổ chưa.
        du, ly_do = _du_cho_trong_o(tong)
        if not du:
            _set_state(state="error", message=ly_do)
            return

        # 3. Tải. `revision=sha` bắt buộc: không ghim thì file rơi rải rác qua
        #    nhiều revision, `speaker_encoder.onnx` kẹt ở sha cũ, và voice
        #    cloning chết khi offline.
        da_xong = 0
        for src, sha, byte_repo in ke_hoach:
            _dat_nguon(da_xong, byte_repo)
            _snapshot_download(
                repo_id=src.repo,
                repo_type="model",
                revision=sha,
                allow_patterns=list(src.allow_patterns),
                tqdm_class=_ProgressTqdm,
                max_workers=4,
                **({"set_main_ref": False} if src.revision else {}),
            )
            da_xong += byte_repo
            _set_state(done_bytes=da_xong)

        # 3b. Bản .exe không kèm PyTorch - mô hình cần torch (v3 Turbo GPU) thì
        #     tự dựng venv riêng và cài vào đây, TRƯỚC khi giữ model_lock ở bước áp
        #     dụng. Backend Python riêng cũng dùng cùng quy trình này.
        if _can_tu_cai_gpu_deps(spec):
            _set_state(current_file="", message="Đang cài bộ hỗ trợ GPU...", phase="gpu_setup")
            from apps import gpu_installer
            def check_cancel():
                if _cancel.is_set():
                    raise Cancelled()
            gpu_installer.install_gpu_deps(
                on_progress=lambda m: _set_state(current_file=m, message=m),
                check_cancel=check_cancel,
            )
            check_cancel()

        # 3c. Kokoro cần bộ tách âm GPL - không đóng gói, cài vào máy
        #     người dùng ngay lúc này (apps/kokoro_installer.py).
        if "kokoro_deps" in spec.requires:
            _set_state(current_file="", message="Đang cài bộ tách âm cho Kokoro...", phase="addon_setup")
            from apps import kokoro_installer
            def check_cancel_addon():
                if _cancel.is_set():
                    raise Cancelled()
            kokoro_installer.install_deps(
                on_progress=lambda m: _set_state(current_file=m, message=m),
                check_cancel=check_cancel_addon,
            )
            check_cancel_addon()

        # 4. Áp dụng. Đây là chỗ DUY NHẤT giữ model_lock (bên trong apply_fn).
        #    Lỗi ở bước này KHÔNG phải lỗi tải - file đã nằm đủ trong cache rồi.
        #    Nên nó có nhánh riêng, và dùng `apply_error_formatter` mà web_stream
        #    trỏ về `_friendly_load_error` (hàm đó biết dò lỗi thiếu VC++ Redist).
        if auto_apply and apply_fn is not None:
            _set_state(state="applying", phase="model", percent=100.0, current_file="",
                       message="Đang nạp mô hình vừa tải...")
            try:
                apply_fn(spec.id)
            except Cancelled:
                raise
            except Exception as e:  # noqa: BLE001
                _set_state(state="error", current_file="",
                           message=apply_error_formatter(e))
                return

        _set_state(state="ready", percent=100.0, current_file="",
                   message=f"Đã sẵn sàng: {spec.name}")

    except Cancelled:
        _set_state(state="cancelled", current_file="",
                   message="Đã huỷ tải. File tải dở được giữ lại, lần sau tải tiếp.")
    except Exception as e:  # noqa: BLE001 - gom mọi lỗi thành câu người dùng đọc được
        _set_state(state="error", current_file="", message=_chuoi_loi_mang(e))
    finally:
        _cancel.clear()


def _chay_pack(spec, pack, auto_apply: bool, apply_fn) -> None:
    """Tải một gói ngôn ngữ Kokoro: giọng của gói + bộ tách âm riêng, rồi (tuỳ
    `apply_fn`) nạp lại Kokoro cho giọng mới hiện ra.

    Giọng tải theo ĐÚNG sha mô hình đang có trong cache, không theo `main` mới
    nhất: khác sha thì giọng rơi sang snapshot khác, còn engine chỉ đọc thư mục
    giọng cạnh `af_heart.bin` của snapshot hiện tại.
    """
    _cancel.clear()
    _set_state(
        state="downloading", model_id=spec.id, pack=pack.code, percent=0.0, done_bytes=0,
        total_bytes=0, current_file="", message="", phase="model",
    )

    def check_cancel():
        if _cancel.is_set():
            raise Cancelled()

    try:
        sha = model_catalog.KOKORO_REVISION
        if not model_catalog.is_downloaded(spec):
            _set_state(state="error", message="Hãy tải mô hình Kokoro trước rồi mới thêm ngôn ngữ.")
            return

        info = _model_info(model_catalog.KOKORO_REPO, revision=sha)
        tong = sum(
            getattr(s, "size", 0) or 0
            for s in getattr(info, "siblings", [])
            if _khop(getattr(s, "rfilename", ""), pack.patterns)
        )
        _set_state(total_bytes=tong)
        _dat_nguon(0, tong)
        _snapshot_download(
            repo_id=model_catalog.KOKORO_REPO, repo_type="model", revision=sha,
            allow_patterns=list(pack.patterns), tqdm_class=_ProgressTqdm, max_workers=4,
            set_main_ref=False,
        )
        _set_state(done_bytes=tong)
        check_cancel()

        _set_state(current_file="", message=f"Đang cài {pack.name[0].lower() + pack.name[1:]}...", phase="addon_setup")
        from apps import kokoro_installer

        kokoro_installer.install_pack(
            pack.code,
            on_progress=lambda m: _set_state(current_file=m, message=m),
            check_cancel=check_cancel,
        )
        check_cancel()

        if auto_apply and apply_fn is not None:
            _set_state(state="applying", phase="model", percent=100.0, current_file="",
                       message="Đang nạp lại mô hình...")
            try:
                apply_fn(spec.id)
            except Cancelled:
                raise
            except Exception as e:  # noqa: BLE001
                # Gói đã cài xong (marker đã ghi) - chỉ bước nạp lại hỏng. Nói rõ để
                # người dùng không tải lại cả gói, chỉ cần khởi động lại app.
                ten = pack.name[0].lower() + pack.name[1:]
                _set_state(state="error", current_file="",
                           message=f"Đã cài xong {ten} nhưng chưa nạp lại được mô hình. "
                                   f"Khởi động lại ứng dụng để dùng giọng mới. "
                                   f"Chi tiết: {apply_error_formatter(e)}")
                return

        _set_state(state="ready", percent=100.0, current_file="",
                   message=f"Đã thêm {pack.name[0].lower() + pack.name[1:]}")

    except Cancelled:
        _set_state(state="cancelled", current_file="",
                   message="Đã huỷ tải. File tải dở được giữ lại, lần sau tải tiếp.")
    except Exception as e:  # noqa: BLE001 - gom mọi lỗi thành câu người dùng đọc được
        _set_state(state="error", current_file="", message=_chuoi_loi_mang(e))
    finally:
        _cancel.clear()


def start(model_id: str, auto_apply: bool = True, apply_fn=None,
          pack: Optional[str] = None) -> tuple[bool, str]:
    """Nhận việc tải. Trả `(True, "")` nếu đã ném sang thread nền.

    `pack` ("ja"/"zh"): chỉ tải gói ngôn ngữ đó của Kokoro."""
    global _thread

    spec = model_catalog.get(model_id)
    if spec is None:
        return False, f"Không có mô hình nào tên «{model_id}»."
    goi = None
    if pack is not None:
        goi = model_catalog.kokoro_pack(pack)
        if not model_catalog.is_kokoro(spec.id) or goi is None:
            return False, f"Mô hình «{model_id}» không có gói ngôn ngữ «{pack}»."

    hien_tai = get_state()
    if hien_tai["state"] in ("downloading", "applying"):
        return False, (
            f"Đang tải {hien_tai['model_id']}, huỷ việc đó trước đã."
        )

    if goi is not None:
        target, args = _chay_pack, (spec, goi, auto_apply, apply_fn)
    else:
        target, args = _chay, (spec, auto_apply, apply_fn)
    _set_state(pack=pack)
    _thread = threading.Thread(target=target, args=args, name="model-downloader", daemon=True)
    _thread.start()
    return True, ""


def cancel() -> bool:
    """Bật cờ huỷ. Trả False nếu chẳng có gì đang chạy."""
    if get_state()["state"] not in ("downloading", "applying"):
        return False
    _cancel.set()
    return True
