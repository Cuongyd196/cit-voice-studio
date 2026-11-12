"""Persist the app's PORT preference, without changing the system environment."""
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from apps.remote_access import require_this_machine


def settings_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "server-settings.json"


def configured_port() -> int:
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8"))["PORT"]
        if type(value) is int and 1 <= value <= 65535:
            return value
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        port = int(os.environ.get("PORT", "8001"))
        return port if 1 <= port <= 65535 else 8001
    except ValueError:
        return 8001


def setup_port() -> int:
    port = configured_port()
    os.environ["PORT"] = str(port)
    return port


def save_port(port: int) -> None:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Cổng phải là số nguyên từ 1 đến 65535.")
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump({"PORT": port}, file)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    # The listener keeps its current port until the next launch.
    os.environ["PORT"] = str(port)


router = APIRouter()


class PortSettings(BaseModel):
    port: int = Field(strict=True, ge=1, le=65535)


@router.get("/api/settings/server-port")
def get_server_port(request: Request):
    return {"port": configured_port(), "active_port": request.url.port or 80}


@router.put("/api/settings/server-port")
def set_server_port(settings: PortSettings, request: Request):
    try:
        save_port(settings.port)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Không lưu được cổng server. Hãy kiểm tra quyền ghi cấu hình.") from error
    return {"port": settings.port, "active_port": request.url.port or 80}


# ---- Khởi động lại ứng dụng (cho các cài đặt chỉ áp dụng lúc mở app) ----

# desktop_app gắn hàm khởi động lại vào đây. Chạy kiểu khác (run_stream, uvicorn trực
# tiếp) thì để None: server không tự mở lại được chính nó.
restart_handler: Callable[[], None] | None = None


@router.get("/api/app/restart")
def get_restart_support(request: Request):
    require_this_machine(request)
    return {"supported": restart_handler is not None}


@router.post("/api/app/restart", status_code=202)
def restart_app(request: Request):
    # Kiểm tra Origin/Host: CORS "*" nên trang web lạ cũng POST được tới 127.0.0.1.
    require_this_machine(request)
    handler = restart_handler
    if handler is None:
        raise HTTPException(
            status_code=409,
            detail="Chế độ chạy này không tự khởi động lại được. Hãy tắt rồi mở lại ứng dụng.",
        )
    # Trả lời trước rồi mới thoát, để giao diện kịp nhận kết quả.
    threading.Timer(0.5, handler).start()
    return {"status": "restarting"}
