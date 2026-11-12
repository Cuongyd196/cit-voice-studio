"""Ba lỗi nhỏ sau 1.0.1:

- Tên giọng sai -> API trả 500 "Voice ... not found"; hội thoại còn lặng lẽ bỏ lượt đó.
  Giờ trả 400 kèm lời nhắc tiếng Việt, trước khi đọc.
- Giao diện chọn sẵn giọng đầu danh sách (Adam bựa) còn API mặc định Hải Đăng:
  /voices giờ đưa giọng mặc định của model lên đầu.
- Bấm Dừng thì bài vẫn được đọc hết rồi lưu vào lịch sử: server giờ dừng ở đoạn kế
  tiếp và không lưu.
"""
import asyncio
import threading

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps import history_store as hs
from apps import web_stream as ws

SR = 8000


class FakeEngine:
    """Đủ giống V3TurboVieNeuTTS cho các đường API: danh mục giọng, alias, mặc định."""

    sample_rate = SR

    def __init__(self):
        self._preset_voices = {
            "Adam bựa": {"description": "Nam · Bắc · Tự nhiên", "gender": "male", "featured": 1},
            "Trúc Ly": {"description": "Nữ · Bắc · Tự nhiên", "gender": "female", "featured": 2},
            "Hải Đăng": {"description": "Nam · Bắc · Tự nhiên", "gender": "male", "featured": 5},
        }
        self._voice_aliases = {"Minh Quân": "Hải Đăng"}
        self._default_voice = "Hải Đăng"
        self.calls = []

    def list_preset_voices(self):
        return [(f"⭐ {n}", n) for n in self._preset_voices]

    def resolve_voice_name(self, name):
        if name in self._preset_voices:
            return name
        return self._voice_aliases.get(name)

    def infer(self, seg, voice=None, **kw):
        self.calls.append((seg, voice))
        return np.full(len(seg) * 10, 0.1, dtype=np.float32)

    def infer_stream(self, seg, voice=None, **kw):
        yield self.infer(seg, voice=voice)


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "history_dir", lambda: tmp_path / "history")
    monkeypatch.setattr(ws.pronunciation_settings, "apply", lambda t: t)
    engine = FakeEngine()
    monkeypatch.setattr(ws, "vieneu", engine)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": SR})
    return TestClient(ws.app), engine


# --- Giọng mặc định lên đầu -------------------------------------------------

def test_voices_puts_model_default_first(api):
    client, _ = api
    ids = [v["id"] for v in client.get("/voices").json()]
    assert ids[0] == "Hải Đăng"
    assert ids[1:] == ["Adam bựa", "Trúc Ly"]  # phần còn lại giữ thứ tự cũ


# --- Tên giọng sai -> 400 ---------------------------------------------------

@pytest.mark.parametrize("path", ["/api/tts/generate", "/api/tts/generate-with-subtitles",
                                  "/api/tts/generate-to-history"])
def test_unknown_voice_is_400_before_synthesis(api, path):
    client, engine = api
    r = client.post(path, json={"text": "Xin chào các bạn.", "voice_id": "Không Có Giọng Này"})
    assert r.status_code == 400
    assert "Không Có Giọng Này" in r.json()["detail"] and "/voices" in r.json()["detail"]
    assert engine.calls == []


def test_unknown_voice_on_stream_is_400(api):
    client, _ = api
    assert client.get("/stream", params={"text": "Xin chào.", "voice_id": "Sai Tên"}).status_code == 400


def test_alias_and_empty_voice_still_work(api):
    client, engine = api
    assert client.post("/api/tts/generate", json={"text": "Xin chào.", "voice_id": "Minh Quân"}).status_code == 200
    assert client.post("/api/tts/generate", json={"text": "Xin chào."}).status_code == 200


def test_conversation_rejects_unknown_voice_instead_of_dropping_turn(api):
    client, engine = api
    r = client.post("/api/tts/conversation", json={"turns": [
        {"speaker": "MC", "text": "Chào mừng quý vị.", "voice_id": "Hải Đăng"},
        {"speaker": "Khách", "text": "Rất vui được gặp.", "voice_id": "Không Có"},
    ]})
    assert r.status_code == 400
    assert "Khách" in r.json()["detail"]
    assert engine.calls == []  # không đọc lượt nào rồi mới báo lỗi


@pytest.mark.parametrize("failure", ["exception", "empty"])
def test_conversation_never_exports_partial_audio(api, monkeypatch, failure):
    client, _ = api
    calls = []

    def synthesize(text, *args, **kwargs):
        calls.append(text)
        if len(calls) == 2:
            if failure == "exception":
                raise RuntimeError("Lỗi mô hình")
            return np.array([], dtype=np.float32)
        return np.ones(800, dtype=np.float32)

    monkeypatch.setattr(ws, "_synthesize", synthesize)
    response = client.post("/api/tts/conversation", json={"turns": [
        {"speaker": "MC", "text": "Xin chào."},
        {"speaker": "Khách", "text": "Chào bạn."},
        {"speaker": "MC", "text": "Hẹn gặp lại."},
    ]})
    assert response.status_code == 500
    assert "lượt 2" in response.json()["detail"]
    assert "Khách" in response.json()["detail"]
    assert len(calls) == 2


# --- Bấm Dừng -> không lưu lịch sử -----------------------------------------

def test_cancelled_generation_is_not_saved(api, tmp_path):
    _, engine = api
    cancelled = threading.Event()
    real_infer = engine.infer

    def infer_then_cancel(seg, **kw):
        cancelled.set()  # người dùng bấm Dừng khi đoạn đầu đang đọc
        return real_infer(seg, **kw)

    engine.infer = infer_then_cancel
    req = ws.TtsToHistoryReq(text="Câu một. [nghỉ 1s] Câu hai. [nghỉ 1s] Câu ba.")
    with pytest.raises(ws._ClientGone):
        ws._generate_to_history(req, cancelled)
    assert len(engine.calls) == 1  # dừng ở đoạn kế tiếp
    assert hs._load() == []
    assert not any((tmp_path / "history").glob(".tmp-*"))  # file tạm đã xoá


def test_run_while_connected_turns_disconnect_into_499():
    class GoneRequest:
        async def is_disconnected(self):
            return True

    def work(cancelled):
        assert cancelled.wait(5)  # watcher đặt cờ khi trình duyệt đã ngắt
        raise ws._ClientGone()

    with pytest.raises(HTTPException) as e:
        asyncio.run(ws._run_while_connected(GoneRequest(), work))
    assert e.value.status_code == 499


def test_run_while_connected_returns_result_when_still_connected():
    class LiveRequest:
        async def is_disconnected(self):
            return False

    assert asyncio.run(ws._run_while_connected(LiveRequest(), lambda cancelled: "xong")) == "xong"


def test_uncancelled_generation_still_saved(api):
    client, _ = api
    r = client.post("/api/tts/generate-to-history", json={"text": "Xin chào các bạn.", "voice_id": "Trúc Ly"})
    assert r.status_code == 200
    assert len(hs._load()) == 1
