"""Đánh dấu "tạo bởi AI" trong file audio app xuất ra (thẻ metadata máy đọc được).

Luật Trí tuệ nhân tạo (hiệu lực 01/3/2026) yêu cầu âm thanh do AI tạo ra được đánh
dấu ở định dạng máy đọc. Thẻ metadata là cách rẻ nhất: WAV nhận chunk LIST/INFO
(ICMT, ISFT), MP3 nhận thẻ ID3 (COMM, TSSE) qua bộ mã LAME của libsndfile - không
cần thư viện mới. Thẻ không đổi âm thanh; ai cắt ghép bằng phần mềm khác có thể
làm mất thẻ, đó là giới hạn của cách này (watermark ẩn trong âm thanh cần torch).

Chỉ dùng ASCII: chunk INFO của WAV và thẻ ID3 mà LAME ghi đều là Latin-1, chữ
tiếng Việt có dấu sẽ thành ký tự lạ ở phần mềm đọc thẻ.
"""
from __future__ import annotations

from apps.app_version import APP_VERSION

# Tên app nằm cả trong ghi chú: với MP3, LAME ghi đè thẻ phần mềm bằng tên chính nó.
AI_COMMENT = "AI-generated speech (text-to-speech), CIT Voice Studio. Giong doc duoc tao bang AI."
SOFTWARE = f"CIT Voice Studio {APP_VERSION}"


HEADER = "X-AI-Generated"


class AiHeaderMiddleware:
    """Gắn header ``X-AI-Generated: true`` vào mọi phản hồi ``audio/*``.

    ``/stream`` phải giữ header WAV 44 byte trơn (client cắt cố định 44 byte) nên
    không mang được thẻ trong file; header HTTP là chỗ đánh dấu máy đọc được cho nó,
    và áp luôn cho mọi audio khác cho thống nhất. Viết dạng ASGI thuần chứ không dùng
    ``@app.middleware("http")``: BaseHTTPMiddleware của Starlette làm hỏng
    ``request.is_disconnected()``, thứ nút Dừng dựa vào."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_header(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                ctype = next((v for k, v in headers if k.lower() == b"content-type"), b"")
                if ctype.lower().startswith(b"audio/"):
                    headers.append((HEADER.lower().encode(), b"true"))
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_header)


def label(sound_file) -> None:
    """Gắn thẻ vào một ``soundfile.SoundFile`` vừa mở để GHI, trước khi ghi mẫu nào:
    bộ mã MP3 viết thẻ ID3 lúc bắt đầu, đặt sau thì mất. Định dạng nào không nhận
    thẻ thì bỏ qua - không bao giờ làm hỏng việc xuất audio."""
    for name, value in (("comment", AI_COMMENT), ("software", SOFTWARE)):
        try:
            setattr(sound_file, name, value)
        except Exception:
            pass
