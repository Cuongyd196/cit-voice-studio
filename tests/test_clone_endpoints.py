"""File giọng mẫu và "Giữ ổn định".

- File mẫu định dạng không đọc được (M4A/MP4/AAC/WMA/WebM trên máy không có ffmpeg)
  từng bị lưu nguyên rồi để engine báo "Format not recognised" -> giờ báo 400 rõ ràng.
- Chỉ đọc 30 giây đầu của file mẫu: bản ghi dài hàng giờ không bị đọc trọn.
- Nhân bản thẳng từ file tải lên (/api/tts/clone, clone-to-history) đã bỏ ở 1.0.2.
- seed cố định: cùng văn bản + cùng giọng ra y hệt nhau.
"""
import io
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from fastapi import HTTPException
from fastapi.testclient import TestClient

from apps import history_store as hs
from apps import web_stream as ws

SR = 8000


def _wav_bytes(seconds: float, sr: int = 16000) -> bytes:
    buf = io.BytesIO()
    t = np.arange(int(seconds * sr)) / sr
    sf.write(buf, (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), sr, format="WAV")
    return buf.getvalue()


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "history_dir", lambda: tmp_path / "history")
    monkeypatch.setattr(ws.pronunciation_settings, "apply", lambda t: t)
    fake = Mock()
    fake.infer.side_effect = lambda seg, **kw: np.full(len(seg) * 10, 0.1, dtype=np.float32)
    monkeypatch.setattr(ws, "vieneu", fake)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": SR})
    return TestClient(ws.app), fake


# ---------------------------------------------------------------------------
# Đọc file mẫu
# ---------------------------------------------------------------------------

def test_file_mau_khong_doc_duoc_bao_loi_ro_rang(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def no_decoders(name, *a, **kw):   # như máy người dùng: không librosa/ffmpeg đọc được
        if name in ("librosa", "pydub"):
            raise ImportError(name)
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", no_decoders)
    with pytest.raises(HTTPException) as e:
        ws._normalize_ref_audio(b"\x00\x00\x00\x20ftypM4A isom" + b"\x00" * 200, "ghi-am.m4a")
    assert e.value.status_code == 400
    assert ".m4a" in e.value.detail and "MP3" in e.value.detail


def test_file_mau_dai_chi_doc_30_giay_dau():
    path = ws._normalize_ref_audio(_wav_bytes(45), "dai.wav")
    try:
        info = sf.info(path)
        assert info.duration == pytest.approx(ws.REF_AUDIO_MAX_READ_SECONDS, abs=0.01)
        assert info.channels == 1
    finally:
        ws._remove_quietly(path)


def test_file_mau_stereo_ngan_giu_nguyen():
    buf = io.BytesIO()
    sf.write(buf, np.zeros((16000 * 3, 2), np.float32) + 0.1, 16000, format="WAV")
    path = ws._normalize_ref_audio(buf.getvalue(), "a.wav")
    try:
        assert sf.info(path).duration == pytest.approx(3.0)
    finally:
        ws._remove_quietly(path)


# ---------------------------------------------------------------------------
# Endpoint nhân bản
# ---------------------------------------------------------------------------

def test_khong_con_nhan_ban_tu_file(api):
    """Từ 1.0.2 chỉ tạo giọng qua bước thu âm câu đồng ý (/api/voices/custom)."""
    client, fake = api
    for path in ("/api/tts/clone", "/api/tts/clone-to-history"):
        r = client.post(path, files={"ref_audio": ("a.wav", _wav_bytes(5))}, data={"text": "Xin chào."})
        assert r.status_code in (404, 405), path
    fake.infer.assert_not_called()
    assert "/api/tts/clone" not in ws.app.openapi()["paths"]


# ---------------------------------------------------------------------------
# Giữ ổn định (seed)
# ---------------------------------------------------------------------------

def test_seed_co_dinh_cho_ket_qua_lap_lai(monkeypatch):
    fake = Mock()
    fake.infer.side_effect = lambda seg, **kw: np.random.standard_normal(100).astype(np.float32)
    monkeypatch.setattr(ws, "vieneu", fake)
    a = ws._tts_infer(7, voice="X")("Câu một.")
    b = ws._tts_infer(7, voice="X")("Câu một.")
    c = ws._tts_infer(None, voice="X")("Câu một.")
    np.testing.assert_array_equal(a, b)
    assert not np.array_equal(a, c)
    assert "seed" not in fake.infer.call_args.kwargs     # Turbo không nhận seed


def test_seed_truyen_cho_engine_nhan_tham_so_seed(monkeypatch):
    class Nano:
        def __init__(self):
            self.kw = None

        def infer(self, text, voice=None, seed=None):
            self.kw = {"voice": voice, "seed": seed}
            return np.zeros(10, np.float32)

    nano = Nano()
    monkeypatch.setattr(ws, "vieneu", nano)
    ws._tts_infer(5, voice="Y")("Câu.")
    assert nano.kw == {"voice": "Y", "seed": 5}


def test_api_generate_to_history_nhan_seed(api):
    client, fake = api
    r = client.post("/api/tts/generate-to-history", json={"text": "Xin chào.", "seed": 1234})
    assert r.status_code == 200, r.text
