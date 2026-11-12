"""Cài đặt lưu file của app desktop: thư mục lưu, có hỏi Save As không, tự mở file.

Người dùng góp ý: mỗi lần lưu đều phải chọn lại thư mục (hộp thoại luôn mở ở
Downloads), và lưu xong phải tự đi tìm file. Chỉ app desktop (PyWebView) dùng được:
trình duyệt không cho trang web chọn thư mục hay mở file trên máy.

Cấu hình ở ``%LOCALAPPDATA%\\CitVoiceStudio\\save-settings.json``:
``{"folder": str | null, "ask": bool, "open_after": bool}``. ``folder`` null hoặc
không còn tồn tại thì dùng Downloads.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {"folder": None, "ask": True, "open_after": False}


def settings_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "save-settings.json"


def default_folder() -> Path:
    downloads = Path.home() / "Downloads"
    return downloads if downloads.is_dir() else Path.home()


def load() -> Dict[str, Any]:
    out = dict(DEFAULTS)
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    if not isinstance(data, dict):
        return out
    if isinstance(data.get("folder"), str) and data["folder"].strip():
        out["folder"] = data["folder"]
    for key in ("ask", "open_after"):
        if isinstance(data.get(key), bool):
            out[key] = data[key]
    return out


def save(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Kiểm tra rồi ghi cấu hình (ghi nguyên tử). Thư mục phải tồn tại."""
    clean = dict(DEFAULTS)
    folder = settings.get("folder")
    if folder:
        p = Path(str(folder)).expanduser()
        if not p.is_dir():
            raise ValueError(f"Không tìm thấy thư mục: {folder}")
        clean["folder"] = str(p.resolve())
    for key in ("ask", "open_after"):
        if key in settings:
            clean[key] = bool(settings[key])
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
            tmp = Path(f.name)
            json.dump(clean, f, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return clean


def effective_folder(settings: Optional[Dict[str, Any]] = None) -> Path:
    """Thư mục lưu thật: thư mục đã chọn nếu còn tồn tại (USB rút ra, thư mục bị
    xoá…), không thì Downloads."""
    folder = (settings or load()).get("folder")
    if folder and Path(folder).is_dir():
        return Path(folder)
    return default_folder()


def unique_path(folder: Path, filename: str) -> Path:
    """Đường dẫn chưa có file: "ten.wav" -> "ten (1).wav"… Lưu thẳng không hỏi thì
    không được ghi đè file người dùng đã có."""
    name = Path(filename).name or "cit-voice.wav"
    target = folder / name
    stem, suffix = target.stem, target.suffix
    n = 1
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


def open_path(path: Path, *, reveal: bool = False) -> None:
    """Mở file bằng chương trình mặc định, hoặc (``reveal``) mở thư mục chứa nó và
    chọn sẵn file."""
    path = Path(path)
    if sys.platform == "win32":
        if reveal:
            # Phải là chuỗi lệnh tự ghép, không phải list: list2cmdline bọc cả
            # `/select,C:\...\Hải Đăng.mp3` trong một cặp ngoặc kép khi có dấu cách,
            # explorer đọc sai và mở thư mục Documents thay vì thư mục chứa file.
            subprocess.Popen(f'explorer /select,"{path}"')  # noqa: S603
        else:
            os.startfile(str(path))  # noqa: S606 - mở file người dùng vừa lưu
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if reveal else ["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if reveal else path)])
