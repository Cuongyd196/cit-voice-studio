"""Cho máy khác (LAN / Internet) gọi API tạo giọng, có khoá API. Mặc định TẮT.

Quy tắc:
- Request từ chính máy này (loopback, không qua proxy) không bị đụng tới - giao diện
  của app và phần mềm cục bộ vẫn chạy như cũ, không cần khoá.
- Request từ máy khác, hoặc mang header chuyển tiếp của proxy/tunnel (ngrok,
  Cloudflare Tunnel, nginx... đều kết nối từ 127.0.0.1 nên phải nhận ra bằng header):
    * tính năng đang tắt       -> 403
    * không phải API công khai -> 404 (API nội bộ: lịch sử, cài đặt, khoá... không lộ ra)
    * thiếu/sai khoá           -> 401
- Tắt có hiệu lực ngay. Bật thì cần mở lại app: lúc khởi động server mới chọn lắng
  nghe 0.0.0.0 (mọi mạng) thay vì 127.0.0.1 (chỉ máy này).
"""
from __future__ import annotations

import hmac
import ipaddress
import json
import os
import secrets
import socket
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

# Khớp danh sách API công khai trong cit-voice-studio.md / tests/test_public_api_docs.py.
PUBLIC_PATHS = frozenset({
    "/health",
    "/voices",
    "/stream",
    "/api/tts/generate",
    "/api/tts/generate-with-subtitles",
    "/api/tts/conversation",
})
# Tài liệu chỉ mô tả API công khai, đọc không cần khoá (Swagger tự tải openapi.json).
DOC_PATHS = frozenset({"/cit-voice-studio.md", "/docs", "/docs/oauth2-redirect", "/openapi.json"})

_FORWARD_HEADERS = (b"x-forwarded-for", b"forwarded", b"x-real-ip", b"cf-connecting-ip", b"x-forwarded-host")
_LOCAL_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
LISTEN_ENV = "CIT_LISTEN_HOST"

_lock = threading.Lock()
_state: dict | None = None


def config_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "remote-access.json"


def new_key() -> str:
    return "cit_" + secrets.token_urlsafe(24)


def _write(state: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(state, file)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def current() -> dict:
    """{"enabled": bool, "api_key": str}. Lần đầu tự sinh khoá và lưu lại."""
    global _state
    with _lock:
        if _state is None:
            state = {"enabled": False, "api_key": ""}
            try:
                data = json.loads(config_path().read_text(encoding="utf-8"))
                state["enabled"] = data.get("enabled") is True
                if isinstance(data.get("api_key"), str) and len(data["api_key"]) >= 20:
                    state["api_key"] = data["api_key"]
            except (OSError, ValueError, AttributeError):
                pass
            if not state["api_key"]:
                state["api_key"] = new_key()
                try:
                    _write(state)
                except OSError:
                    pass  # Không ghi được: dùng khoá trong phiên này.
            _state = state
        return dict(_state)


def _update(**changes) -> dict:
    global _state
    state = {**current(), **changes}
    _write(state)  # Lỗi ghi thì giữ nguyên trạng thái cũ.
    with _lock:
        _state = state
    return dict(state)


def reset_cache() -> None:
    global _state
    with _lock:
        _state = None


def listen_host() -> str:
    """Địa chỉ server nên lắng nghe khi khởi động."""
    return "0.0.0.0" if current()["enabled"] else "127.0.0.1"


def mark_listening(host: str) -> None:
    os.environ[LISTEN_ENV] = host


def is_listening_all() -> bool:
    return os.environ.get(LISTEN_ENV) == "0.0.0.0"


def primary_address() -> str | None:
    """IPv4 của card mạng chính (card hệ điều hành dùng để ra mạng). Các IP khác
    thường là card ảo (VirtualBox 192.168.56.1, Hyper-V, VPN) - máy khác không tới được."""
    try:
        # Không gửi gói nào: connect UDP chỉ để hệ điều hành chọn card theo bảng định tuyến.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
    except OSError:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    return None if addr.is_loopback or addr.is_unspecified or addr.is_link_local else ip


def lan_addresses() -> list[str]:
    """IPv4 của máy trong mạng LAN, card chính đứng đầu."""
    found: list[str] = []
    primary = primary_address()
    if primary:
        found.append(primary)
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass
    result = []
    for ip in found:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if not (addr.is_loopback or addr.is_link_local or addr.is_unspecified) and ip not in result:
            result.append(ip)
    return result


def _is_loopback(host: str | None) -> bool:
    if host == "testclient":  # Máy khách giả của Starlette TestClient; socket thật luôn là IP.
        return True
    try:
        addr = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_loopback


def is_remote(scope) -> bool:
    client = scope.get("client")
    if not _is_loopback(client[0] if client else None):
        return True
    return any(name in _FORWARD_HEADERS for name, _ in scope.get("headers", []))


def _key_from(scope) -> str:
    headers = {name: value.decode("latin-1") for name, value in scope.get("headers", [])}
    key = headers.get(b"x-api-key", "").strip()
    if key:
        return key
    auth = headers.get(b"authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip()
    # Cho thẻ <audio src="/stream?...&api_key=..."> - thẻ này không gửi được header.
    query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
    return (query.get("api_key") or [""])[0].strip()


class RemoteAccessMiddleware:
    """Chặn request từ máy khác theo quy tắc ở đầu file. Phải là middleware ngoài cùng."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket") or not is_remote(scope):
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        state = current()
        if not state["enabled"]:
            await _deny(scope, send, 403, "Truy cập từ máy khác đang tắt. Bật trong Cài đặt của CIT Voice Studio.")
            return
        if path not in PUBLIC_PATHS and path not in DOC_PATHS:
            await _deny(scope, send, 404, "Không tìm thấy.")
            return
        # OPTIONS là preflight CORS của trình duyệt: không mang được khoá.
        if path in PUBLIC_PATHS and scope.get("method") != "OPTIONS":
            if not hmac.compare_digest(_key_from(scope).encode(), state["api_key"].encode()):
                await _deny(scope, send, 401, "Thiếu hoặc sai khoá API. Gửi header X-API-Key: <khoá>.")
                return
        await self.app(scope, receive, send)


async def _deny(scope, send, status: int, detail: str) -> None:
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 1008})
        return
    body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode()),
        # Lỗi trả trước CORSMiddleware: thêm tay để trình duyệt đọc được thông báo.
        (b"access-control-allow-origin", b"*"),
    ]
    if status == 401:
        headers.append((b"www-authenticate", b'Bearer realm="CIT Voice Studio"'))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


# ---- API cài đặt (chỉ giao diện trên máy này) ----

router = APIRouter()


def require_this_machine(request: Request) -> None:
    """Middleware đã chặn máy khác. Ở đây chặn thêm TRANG WEB LẠ mở trên chính máy này
    (CORS đang mở "*" nên trang nào cũng fetch được 127.0.0.1): kiểm tra Origin, và
    Host để chống DNS rebinding - nếu không, trang lạ đọc được khoá rồi gửi đi."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
    if host not in _LOCAL_HOSTNAMES:
        raise HTTPException(status_code=403, detail="Chỉ đổi được từ ứng dụng trên máy này.")
    origin = request.headers.get("origin")
    if origin and origin != "null":
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in _LOCAL_HOSTNAMES:
            raise HTTPException(status_code=403, detail="Chỉ đổi được từ ứng dụng trên máy này.")


def _status(request: Request) -> dict:
    state = current()
    return {
        "enabled": state["enabled"],
        "api_key": state["api_key"],
        "listening_all": is_listening_all(),
        "port": request.url.port or 80,
        "addresses": lan_addresses(),
        "primary_address": primary_address(),
    }


class RemoteAccessUpdate(BaseModel):
    enabled: bool


@router.get("/api/remote-access")
def get_remote_access(request: Request):
    require_this_machine(request)
    return _status(request)


@router.put("/api/remote-access")
def set_remote_access(update: RemoteAccessUpdate, request: Request):
    require_this_machine(request)
    try:
        _update(enabled=update.enabled)
    except OSError as error:
        raise HTTPException(status_code=500, detail="Không lưu được cài đặt. Hãy kiểm tra quyền ghi cấu hình.") from error
    return _status(request)


@router.post("/api/remote-access/regenerate-key")
def regenerate_key(request: Request):
    require_this_machine(request)
    try:
        _update(api_key=new_key())
    except OSError as error:
        raise HTTPException(status_code=500, detail="Không lưu được khoá mới.") from error
    return _status(request)
