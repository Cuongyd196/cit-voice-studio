"""Tuỳ chọn giao diện React (sáng/tối, tự phát sau khi tạo, tốc độ phát, giọng mở sẵn…) lưu xuống
đĩa thay vì chỉ ở localStorage.

Vì sao: app desktop gọi ``webview.start()`` không kèm ``private_mode=False``, mà
PyWebView mặc định ``private_mode=True`` → localStorage bị xoá mỗi lần tắt app, người
dùng chọn giao diện tối xong mở lại thấy sáng. Ngay cả khi tắt chế độ riêng tư,
localStorage gắn theo origin: cổng đổi (8001 bận → 8002) là mất. File trên đĩa thì
không phụ thuộc cả hai.

Chỉ nhận các khoá trong ``_FIELDS``, kiểm kiểu từng khoá; khoá lạ bị bỏ qua. Không lưu
địa chỉ API (cần địa chỉ đó mới gọi được tới đây).

``%LOCALAPPDATA%\\CitVoiceStudio\\ui-prefs.json``.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from apps.remote_access import require_this_machine

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_number(lo: float, hi: float):
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi


_FIELDS = {
    "theme": lambda v: v in ("light", "dark"),
    "autoPlayOnGenerate": lambda v: isinstance(v, bool),
    "playbackSpeed": _is_number(0.25, 4.0),
    "silenceDuration": _is_number(0.0, 10.0),
    # Rỗng = dùng giọng mặc định của mô hình.
    "defaultVoiceId": lambda v: isinstance(v, str) and len(v) <= 200,
}


def settings_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "ui-prefs.json"


def _clean(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in _FIELDS and _FIELDS[k](v)}


def load() -> Dict[str, Any]:
    try:
        return _clean(json.loads(settings_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return {}


def update(changes: Any) -> Dict[str, Any]:
    """Gộp các khoá hợp lệ vào file (ghi nguyên tử) và trả toàn bộ tuỳ chọn."""
    prefs = {**load(), **_clean(changes)}
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".ui-prefs-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return prefs


@router.get("/api/ui/prefs")
def get_prefs() -> Dict[str, Any]:
    return load()


@router.put("/api/ui/prefs", dependencies=[Depends(require_this_machine)])
def put_prefs(changes: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        return update(changes)
    except OSError as e:
        logger.warning("Không lưu được tuỳ chọn giao diện: %s", e)
        return {**load(), **_clean(changes)}
