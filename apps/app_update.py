"""Kiểm tra bản mới trên GitHub Releases. Chỉ BÁO, không tự tải hay tự cài.

- Có bản mới: giao diện bật hộp thoại (tên các nhóm thay đổi lấy từ tiêu đề `###`
  của ghi chú phát hành). "Để sau" ghi `skipped` = bản đó, hộp thoại không bật lại
  cho tới bản kế tiếp; thanh báo nhỏ và nút kiểm tra tay vẫn còn.

- Lúc mở app, giao diện gọi GET /api/app/update. Server hỏi GitHub tối đa một lần
  mỗi ngày (kết quả lưu ở %LOCALAPPDATA%\\CitVoiceStudio\\update-check.json), chờ tối
  đa 5 giây; mất mạng thì trả `error`, giao diện im lặng.
- Đây là lần duy nhất app tự kết nối Internet, nên MẶC ĐỊNH TẮT: người dùng tự bật
  trong Cài đặt (PUT /api/app/update-check). Khi tắt, chỉ nút "Kiểm tra cập nhật"
  ở tab Thông tin (force=1) mới hỏi GitHub.
- Chỉ gửi một GET tới api.github.com, không kèm văn bản, audio hay thông tin máy.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from apps.app_version import APP_VERSION
from apps.remote_access import require_this_machine
from apps.runtime_paths import https_context

RELEASES_REPO = "Cuongyd196/cit-voice-studio"
RELEASES_PAGE = f"https://github.com/{RELEASES_REPO}/releases/latest"
LATEST_API = f"https://api.github.com/repos/{RELEASES_REPO}/releases/latest"
CHECK_INTERVAL_SECONDS = 24 * 3600
TIMEOUT_SECONDS = 5
MAX_HIGHLIGHTS = 6
_MARKDOWN = re.compile(r"[*_`]|\[([^\]]*)\]\([^)]*\)")

_lock = threading.Lock()


def config_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "update-check.json"


def parse_version(text: str) -> tuple[int, ...]:
    """"v1.0.1", "1.0.1", "CIT Voice Studio 1.2" -> (1, 0, 1) / (1, 2, 0). Không có số -> ()."""
    numbers = [int(n) for n in re.findall(r"\d+", text or "")[:3]]
    return tuple(numbers + [0] * (3 - len(numbers))) if numbers else ()


def is_newer(latest: str, current: str = APP_VERSION) -> bool:
    new, old = parse_version(latest), parse_version(current)
    return bool(new) and new > old


def _read() -> dict:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(state: dict) -> None:
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            json.dump(state, file)
        os.replace(file.name, path)
    except OSError:
        pass  # Không ghi được: lần mở sau hỏi lại GitHub, không sao.


def is_enabled() -> bool:
    return _read().get("enabled") is True


def highlights(body: str) -> list[str]:
    """Các mục `### Tiêu đề` của ghi chú phát hành, bỏ ký hiệu markdown: hộp thoại
    "Có bản mới" chỉ liệt kê tên nhóm thay đổi, chi tiết xem trên trang Releases."""
    out = []
    for line in (body or "").splitlines():
        if line.startswith("### "):
            title = _MARKDOWN.sub(lambda m: m.group(1) or "", line[4:]).strip()
            if title:
                out.append(title[:80])
        if len(out) == MAX_HIGHLIGHTS:
            break
    return out


def fetch_latest() -> dict:
    """{"version", "url", "published_at"} của bản phát hành mới nhất (bỏ qua bản nháp/thử)."""
    request = urllib.request.Request(LATEST_API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"CIT-Voice-Studio/{APP_VERSION}",
    })
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS,
                                context=https_context()) as response:
        body = json.loads(response.read().decode("utf-8"))
    url = body.get("html_url") or ""
    # Chỉ mở trang của đúng kho phát hành, không tin link lạ trong phản hồi.
    if not url.startswith(f"https://github.com/{RELEASES_REPO}/"):
        url = RELEASES_PAGE
    return {"version": str(body.get("tag_name") or ""), "url": url,
            "published_at": body.get("published_at"),
            "highlights": highlights(str(body.get("body") or ""))}


def _result(latest: dict | None, *, checked_at: float | None, error: str | None = None) -> dict:
    version = (latest or {}).get("version") or None
    notes = (latest or {}).get("highlights")
    return {
        "current": APP_VERSION,
        "enabled": is_enabled(),
        "latest": version,
        "newer": bool(version) and is_newer(version),
        "url": (latest or {}).get("url") or RELEASES_PAGE,
        "published_at": (latest or {}).get("published_at"),
        "checked_at": checked_at,
        "error": error,
        "highlights": [str(n) for n in notes][:MAX_HIGHLIGHTS] if isinstance(notes, list) else [],
        # Người dùng bấm "Để sau" ở hộp thoại của đúng bản này: không bật hộp thoại
        # nữa (thanh báo nhỏ vẫn hiện) cho tới khi có bản mới hơn.
        "skipped": bool(version) and _read().get("skipped") == version,
    }


def check(force: bool = False) -> dict:
    with _lock:
        state = _read()
        cached = state.get("latest") if isinstance(state.get("latest"), dict) else None
        checked_at = state.get("checked_at") if isinstance(state.get("checked_at"), (int, float)) else None
        if not force:
            if state.get("enabled") is not True:
                return _result(None, checked_at=None)
            if cached and checked_at and time.time() - checked_at < CHECK_INTERVAL_SECONDS:
                return _result(cached, checked_at=checked_at)
        try:
            latest = fetch_latest()
        except Exception:
            return _result(cached, checked_at=checked_at,
                           error="Không kiểm tra được bản mới (máy chưa có mạng hoặc GitHub không phản hồi).")
        now = time.time()
        _write({**state, "latest": latest, "checked_at": now})
        return _result(latest, checked_at=now)


router = APIRouter()


@router.get("/api/app/update")
def get_update(force: bool = False):
    return check(force)


class UpdateCheckSettings(BaseModel):
    enabled: bool


@router.put("/api/app/update-check")
def set_update_check(settings: UpdateCheckSettings):
    with _lock:
        _write({**_read(), "enabled": settings.enabled})
    return {"enabled": is_enabled()}


class UpdateSkip(BaseModel):
    version: str


@router.put("/api/app/update-skip", dependencies=[Depends(require_this_machine)])
def skip_update(body: UpdateSkip):
    with _lock:
        _write({**_read(), "skipped": body.version[:40]})
    return {"skipped": body.version[:40]}
