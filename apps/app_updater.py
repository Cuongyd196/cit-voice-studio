"""Tự cập nhật trên Windows: tải bộ cài bản mới về rồi cài đè, không mở trình duyệt.

Chỉ chạy khi app được cài bằng bộ cài Inno Setup (có ``unins000.exe`` cạnh file
.exe) và desktop_app gắn ``quit_handler``. Bản chạy từ mã nguồn, Linux (.deb cần
quyền root) và macOS (.dmg kéo thả) vẫn mở trang tải như cũ.

An toàn:
- Chỉ tải từ link của đúng kho phát hành, file đúng tên bộ cài Windows của bản mới
  (``app_update.pick_installer``).
- Kiểm tra cỡ file và mã sha256 GitHub công bố, cả lúc tải xong lẫn ngay trước khi
  chạy. Sai là xoá file, không chạy.
- Bộ cài chạy ``/SILENT``: chỉ hiện thanh tiến trình, không hỏi gì; dùng lại thư
  mục và tuỳ chọn của lần cài trước. Inno tự hoàn tác nếu cài lỗi giữa chừng.
  ``/RELAUNCH=1`` bảo bộ cài mở lại app khi xong (xem [Run] trong installer.iss).
- Giọng đã nhân bản, lịch sử, cài đặt, mô hình đã tải nằm ngoài ``_internal`` nên
  không mất (giống cài đè bằng tay).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException

from apps import app_update
from apps.app_version import APP_VERSION
from apps.remote_access import require_this_machine
from apps.runtime_paths import https_context

# desktop_app gắn hàm thoát app vào đây (như server_settings.restart_handler).
quit_handler: Optional[Callable[[], None]] = None

CHUNK = 1024 * 1024
TIMEOUT_SECONDS = 30
# Chừa thêm chỗ trống ngoài cỡ bộ cài: bộ cài giải nén ~760 MB vào thư mục app.
DISK_MARGIN_BYTES = 1500 * 1024 * 1024
INSTALL_LOG = "install.log"

_lock = threading.Lock()
_state: dict = {"state": "idle"}
_cancel = threading.Event()


def updates_dir() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "updates"


def _install_dir() -> Path:
    return Path(sys.executable).resolve().parent


def supported() -> bool:
    """Máy này tự cập nhật được không: Windows, bản đóng gói, cài bằng bộ cài."""
    return (
        sys.platform == "win32"
        and bool(getattr(sys, "frozen", False))
        and quit_handler is not None
        and (_install_dir() / "unins000.exe").is_file()
    )


def get_state() -> dict:
    with _lock:
        return dict(_state)


def _set(**kw) -> None:
    with _lock:
        _state.clear()
        _state.update(kw)


def _progress(downloaded: int) -> None:
    with _lock:
        _state["downloaded"] = downloaded


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _clean_old(keep: Optional[str] = None) -> None:
    """Xoá bộ cài cũ/tải dở, trừ file ``keep`` và nhật ký lần cài gần nhất."""
    folder = updates_dir()
    if not folder.is_dir():
        return
    for item in folder.iterdir():
        if item.name not in (keep, INSTALL_LOG):
            try:
                item.unlink()
            except OSError:
                pass


def _download(version: str, installer: dict) -> None:
    folder = updates_dir()
    target = folder / installer["name"]
    part = target.with_suffix(".part")
    try:
        folder.mkdir(parents=True, exist_ok=True)
        _clean_old()
        free = shutil.disk_usage(folder).free
        if free < installer["size"] + DISK_MARGIN_BYTES:
            need = (installer["size"] + DISK_MARGIN_BYTES) / 1024 ** 3
            raise RuntimeError(f"Ổ đĩa không đủ chỗ trống: cần khoảng {need:.1f} GB.")
        request = urllib.request.Request(installer["url"], headers={
            "User-Agent": f"CIT-Voice-Studio/{APP_VERSION}",
        })
        h = hashlib.sha256()
        done = 0
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS,
                                    context=https_context()) as response, open(part, "wb") as out:
            while True:
                if _cancel.is_set():
                    raise InterruptedError()
                block = response.read(CHUNK)
                if not block:
                    break
                out.write(block)
                h.update(block)
                done += len(block)
                if done > installer["size"]:
                    raise RuntimeError("File tải về lớn hơn công bố.")
                _progress(done)
        if done != installer["size"] or h.hexdigest() != installer["sha256"]:
            raise RuntimeError("File tải về không khớp mã kiểm tra (có thể bị hỏng khi tải). Hãy thử lại.")
        os.replace(part, target)
        _set(state="ready", version=version, downloaded=done, total=installer["size"])
    except InterruptedError:
        _remove(part)
        _set(state="idle")
    except Exception as e:  # noqa: BLE001 - mọi lỗi đều báo lên giao diện
        _remove(part)
        detail = str(e) if isinstance(e, RuntimeError) else (
            "Không tải được bản mới (mất mạng hoặc GitHub không phản hồi). Hãy thử lại.")
        _set(state="error", version=version, error=detail)


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _latest_installer() -> tuple[str, dict]:
    # Đọc kết quả kiểm tra đã lưu (không gọi check(): khi tắt tự kiểm tra, check()
    # không trả bản đã biết, dù người dùng vừa bấm "Kiểm tra cập nhật" bằng tay).
    latest = app_update.cached_latest() or {}
    installer = latest.get("installer")
    version = str(latest.get("version") or "")
    if not (version and app_update.is_newer(version) and isinstance(installer, dict)
            and installer.get("name") == app_update.windows_asset_name(version)):
        raise HTTPException(status_code=409, detail="Không có bản mới để cài tự động. Hãy mở trang tải.")
    return version, installer


router = APIRouter(dependencies=[Depends(require_this_machine)])


@router.get("/api/app/update/download")
def download_status():
    return get_state()


@router.post("/api/app/update/download", status_code=202)
def start_download():
    if not supported():
        raise HTTPException(status_code=409, detail="Bản cài này không tự cập nhật được. Hãy mở trang tải.")
    version, installer = _latest_installer()
    with _lock:
        if _state.get("state") == "downloading":
            return dict(_state)
        if _state.get("state") == "ready" and _state.get("version") == version \
                and (updates_dir() / installer["name"]).is_file():
            return dict(_state)
        _cancel.clear()
        _state.clear()
        _state.update(state="downloading", version=version, downloaded=0, total=installer["size"])
    threading.Thread(target=_download, args=(version, installer), name="app-update-download",
                     daemon=True).start()
    return get_state()


@router.delete("/api/app/update/download")
def cancel_download():
    _cancel.set()
    with _lock:
        if _state.get("state") != "downloading":
            _state.clear()
            _state.update(state="idle")
    return get_state()


@router.post("/api/app/update/install", status_code=202)
def install():
    if not supported():
        raise HTTPException(status_code=409, detail="Bản cài này không tự cập nhật được. Hãy mở trang tải.")
    version, installer = _latest_installer()
    state = get_state()
    path = updates_dir() / installer["name"]
    if state.get("state") != "ready" or state.get("version") != version or not path.is_file():
        raise HTTPException(status_code=409, detail="Chưa tải xong bản mới.")
    # Kiểm tra lại ngay trước khi chạy: file nằm trên đĩa từ lúc tải tới giờ.
    if path.stat().st_size != installer["size"] or sha256_of(path) != installer["sha256"]:
        _remove(path)
        _set(state="idle")
        raise HTTPException(status_code=409, detail="File bản mới không còn nguyên vẹn. Hãy tải lại.")
    log = updates_dir() / INSTALL_LOG
    cmd = [str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
           "/RELAUNCH=1", f"/LOG={log}"]
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(cmd, cwd=str(updates_dir()), close_fds=True, creationflags=flags)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Không chạy được bộ cài: {e}")
    _set(state="installing", version=version)
    # Trả lời trước rồi mới thoát để giao diện kịp hiện "Đang cài…". Bộ cài đợi app
    # thoát (Restart Manager, /CLOSEAPPLICATIONS) rồi mới ghi đè.
    handler = quit_handler
    threading.Timer(1.0, handler).start()
    return {"state": "installing", "version": version}


def cleanup_after_update() -> None:
    """Gọi lúc mở app: xoá bộ cài đã dùng (~370 MB) và file tải dở của lần trước."""
    try:
        keep = None
        folder = updates_dir()
        if folder.is_dir():
            for item in folder.glob("*.exe"):
                ver = app_update.parse_version(item.name)
                if ver and ver > app_update.parse_version(APP_VERSION):
                    keep = item.name  # bản mới hơn đã tải nhưng chưa cài: giữ lại
        _clean_old(keep=keep)
    except OSError:
        pass


