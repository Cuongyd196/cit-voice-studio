"""Tài liệu API (/docs, /openapi.json) chỉ liệt kê API dành cho phần mềm khác gọi.

API nội bộ vẫn phải chạy (giao diện dùng) — chỉ ẩn khỏi tài liệu.
"""
import json
import re
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from apps import web_stream as ws
from apps.app_version import APP_VERSION

PUBLIC = {
    "/health", "/voices", "/stream",
    "/api/tts/generate", "/api/tts/generate-with-subtitles",
    "/api/tts/conversation",
    "/cit-voice-studio.md",
}


def test_openapi_lists_only_public_endpoints():
    paths = set(TestClient(ws.app).get("/openapi.json").json()["paths"])
    assert paths == PUBLIC


def test_internal_endpoints_still_routed():
    routes = {r.path for r in ws.app.routes}
    for internal in ("/api/history", "/api/pronunciations", "/api/models",
                     "/api/settings/server-port", "/api/pdf/extract", "/api/voices/custom"):
        assert internal in routes, internal


def test_openapi_version_and_audio_response_types():
    schema = TestClient(ws.app).get("/openapi.json").json()
    assert schema["info"]["version"] == APP_VERSION
    for method in ("get", "post"):
        content = schema["paths"]["/stream"][method]["responses"]["200"]["content"]
        assert set(content) == {"audio/wav"}
    for path in ("/api/tts/generate", "/api/tts/conversation"):
        content = schema["paths"][path]["post"]["responses"]["200"]["content"]
        assert set(content) == {"audio/wav", "audio/mpeg"}
        assert content["audio/wav"]["schema"]["format"] == "binary"


def test_markdown_examples_and_version_are_valid():
    markdown = (Path(__file__).resolve().parents[1] / "docs" / "cit-voice-studio.md").read_text(encoding="utf-8")
    assert f"`{APP_VERSION}`" in markdown
    for block in re.findall(r"```json\n(.*?)\n```", markdown, re.DOTALL):
        json.loads(block)
    for block in re.findall(r"```python\n(.*?)\n```", markdown, re.DOTALL):
        compile(block, "cit-voice-studio.md", "exec")


def test_conversation_mp3_fallback_reports_actual_wav_type(monkeypatch):
    monkeypatch.setattr(ws, "vieneu", object())
    monkeypatch.setattr(ws, "_require_voice", lambda voice: None)
    monkeypatch.setattr(ws, "_tts_infer", lambda *args, **kwargs: None)
    monkeypatch.setattr(ws, "_synthesize", lambda *args, **kwargs: np.zeros(100, dtype=np.float32))
    open_output = ws._open_output

    def no_mp3(target, sr, fmt="WAV"):
        if fmt == "MP3":
            raise RuntimeError("MP3 encoder unavailable")
        return open_output(target, sr, fmt)

    monkeypatch.setattr(ws, "_open_output", no_mp3)
    response = TestClient(ws.app).post("/api/tts/conversation", json={
        "turns": [{"speaker": "MC", "text": "Xin chào"}], "format": "mp3",
    })
    assert response.status_code == 200
    assert response.content.startswith(b"RIFF")
    assert response.headers["content-type"] == "audio/wav"
