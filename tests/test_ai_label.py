"""Audio app xuất ra mang thẻ "tạo bởi AI" máy đọc được (Luật Trí tuệ nhân tạo)."""
import io

import numpy as np
import soundfile as sf

from apps import ai_label, history_store

TONE = (np.sin(np.arange(24_000) / 10) * 0.3).astype(np.float32)


def _comment(data) -> str:
    with sf.SoundFile(io.BytesIO(data) if isinstance(data, bytes) else str(data)) as f:
        return f.comment


def test_the_chi_dung_ascii():
    # Chunk INFO của WAV và ID3 của LAME là Latin-1: chữ có dấu sẽ hiện thành rác.
    assert ai_label.AI_COMMENT.isascii() and ai_label.SOFTWARE.isascii()
    assert "AI-generated" in ai_label.AI_COMMENT


def test_wav_va_mp3_tra_ve_qua_api_co_the_ai():
    import apps.web_stream as ws

    wav = ws._wav_bytes(TONE, 24_000)
    assert wav[:4] == b"RIFF"
    assert _comment(wav) == ai_label.AI_COMMENT
    mp3 = ws._mp3_bytes(TONE, 24_000)
    assert b"AI-generated" in mp3


def test_file_ghi_dan_cho_bai_dai_co_the_ai(tmp_path, monkeypatch):
    import apps.web_stream as ws

    monkeypatch.setattr(ws, "_text_segments", lambda text, use_dict=True: [(text, 0.0)])
    monkeypatch.setattr(ws, "_text_blocks", lambda seg: [(seg, 0.0)])
    path = tmp_path / "take.wav"
    n = ws._synthesize_to_file("xin chào", 24_000, lambda _t: TONE, path)
    assert n == len(TONE)
    assert _comment(path) == ai_label.AI_COMMENT
    # Ghi dần ra file và ghi một lần trong bộ nhớ vẫn ra cùng từng byte.
    assert path.read_bytes() == ws._wav_bytes(TONE, 24_000)


def test_chuyen_mp3_tu_lich_su_giu_the_ai(tmp_path):
    src = tmp_path / "a.wav"
    sf.write(str(src), TONE, 24_000, subtype="PCM_16")      # file không có thẻ
    dst = tmp_path / "a.mp3"
    assert history_store.wav_file_to_mp3(src, dst)
    assert b"AI-generated" in dst.read_bytes()


def test_dinh_dang_khong_nhan_the_thi_bo_qua():
    class KhongNhan:
        def __setattr__(self, name, value):
            raise RuntimeError("không hỗ trợ")

    ai_label.label(KhongNhan())   # không ném lỗi


def test_phan_hoi_audio_co_header_ai_con_json_thi_khong():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, Response, StreamingResponse
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.add_middleware(ai_label.AiHeaderMiddleware)

    @app.get("/wav")
    def wav():
        return Response(b"RIFF", media_type="audio/wav")

    @app.get("/luong")
    def luong():
        return StreamingResponse(iter([b"a", b"b"]), media_type="audio/wav")

    @app.get("/json")
    def json_():
        return JSONResponse({"ok": True})

    client = TestClient(app)
    assert client.get("/wav").headers[ai_label.HEADER] == "true"
    r = client.get("/luong")
    assert r.headers[ai_label.HEADER] == "true" and r.content == b"ab"
    assert ai_label.HEADER not in client.get("/json").headers


def test_app_that_gan_header_va_tai_lieu_api_neu_ro():
    from fastapi.testclient import TestClient

    import apps.web_stream as ws

    assert any(m.cls is ai_label.AiHeaderMiddleware for m in ws.app.user_middleware)
    schema = TestClient(ws.app).get("/openapi.json").json()
    for path, method in (("/stream", "get"), ("/stream", "post"), ("/api/tts/generate", "post")):
        assert ai_label.HEADER in schema["paths"][path][method]["responses"]["200"]["headers"]
