"""Lồng tiếng theo file phụ đề SRT (1.0.2): đọc SRT, khớp mốc, endpoint lưu lịch sử."""
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from apps import history_store as hs
from apps import web_stream as ws
from vieneu_utils import dubbing
from vieneu_utils.srt import SrtError, parse_srt
from vieneu_utils.subtitles import Cue

SR = 1000


# --- Đọc SRT ------------------------------------------------------------------

def test_doc_srt_chuan():
    cues = parse_srt("1\n00:00:01,000 --> 00:00:02,500\nXin chào\n\n2\n00:00:03,000 --> 00:00:04,000\nTạm biệt\n")
    assert [(c.start, c.end, c.text) for c in cues] == [(1.0, 2.5, "Xin chào"), (3.0, 4.0, "Tạm biệt")]


def test_doc_srt_bom_crlf_dau_cham_nhieu_dong_the():
    content = ("﻿1\r\n00:01:02.5 --> 00:01:03.250\r\n<i>Dòng một</i>\r\n{\\an8}dòng hai ♪\r\n\r\n"
               "00:00:00,000 --> 00:00:01,000\r\nKhông số thứ tự\r\n")
    cues = parse_srt(content)
    assert cues[0].text == "Không số thứ tự"          # đã sắp theo mốc
    assert (cues[1].start, cues[1].end, cues[1].text) == (62.5, 63.25, "Dòng một dòng hai")


def test_doc_webvtt_va_bo_cue_rong():
    cues = parse_srt("WEBVTT\n\n00:01.000 --> 00:02.000\n<b></b>\n\n00:03.000 --> 00:04.000\nCó chữ\n")
    assert [c.text for c in cues] == ["Có chữ"]


def test_file_khong_phai_srt():
    with pytest.raises(SrtError):
        parse_srt("Đây chỉ là văn bản thường.")


# --- Khớp mốc -----------------------------------------------------------------

def test_fit_rate():
    assert dubbing.fit_rate(1.0, 2.0) == 1.0
    assert dubbing.fit_rate(2.4, 2.0) == pytest.approx(1.2)
    assert dubbing.fit_rate(5.0, 2.0) == dubbing.MAX_FIT_RATE
    assert dubbing.fit_rate(1.0, 0.0) == dubbing.MAX_FIT_RATE


def test_place_day_lui_khi_cau_truoc_chua_xong():
    assert dubbing.place(3.0, 1.0, True) == 3.0
    assert dubbing.place(3.0, 3.5, True) == pytest.approx(3.55)
    assert dubbing.place(0.0, 0.0, False) == 0.0


def test_stats_phu_de_chinh_khong_de_nhau():
    s = dubbing.DubStats()
    s.record(Cue(0, 1, "a"), 0.0, 1.8, 1.5)
    s.record(Cue(1, 2, "b"), 1.85, 0.5, 1.0)
    placed = s.finish()
    assert (s.cues, s.sped_up, s.pushed) == (2, 1, 1)
    assert s.max_push_seconds == pytest.approx(0.85)
    assert placed[0].end == pytest.approx(1.8) and placed[1].end == pytest.approx(2.85)
    # Câu tràn sang câu sau thì phụ đề bị cắt ở mốc câu sau.
    s2 = dubbing.DubStats()
    s2.record(Cue(0, 3, "a"), 0.0, 1.0, 1.0)
    s2.record(Cue(2, 3, "b"), 2.0, 1.0, 1.0)
    assert s2.finish()[0].end == 2.0


# --- Endpoint -----------------------------------------------------------------

def _stretch(audio, rate):
    if abs(rate - 1.0) < 0.02:
        return audio
    return audio[: int(round(len(audio) / rate))]


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "history_dir", lambda: tmp_path / "history")
    monkeypatch.setattr(ws.pronunciation_settings, "apply", lambda t: t)
    monkeypatch.setattr(ws, "_apply_speed", _stretch)
    fake = Mock()
    # 100 mẫu (0,1 giây) mỗi ký tự.
    fake.infer.side_effect = lambda seg, **kw: np.full(len(seg) * 100, 0.1, dtype=np.float32)
    monkeypatch.setattr(ws, "vieneu", fake)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": SR})
    return TestClient(ws.app), fake


SRT = (
    "1\n00:00:01,000 --> 00:00:02,000\nabcde\n\n"          # 0,5 s: vừa khung
    "2\n00:00:03,000 --> 00:00:04,000\nabcdefghijklmnopqrst\n\n"  # 2 s: tăng 1,5x còn 1,33 s, tràn
    "3\n00:00:04,200 --> 00:00:05,000\nab\n\n"             # bị đẩy lùi
    "4\n00:00:09,000 --> 00:00:10,000\nxyz\n"
)


def test_parse_endpoint(api):
    client, _ = api
    r = client.post("/api/srt/parse", json={"srt": SRT})
    assert r.status_code == 200
    body = r.json()
    assert len(body["cues"]) == 4 and body["duration_seconds"] == 10.0
    assert client.post("/api/srt/parse", json={"srt": "rác"}).status_code == 400


def test_long_tieng_dung_timeline_va_luu_lich_su(api, tmp_path):
    client, fake = api
    r = client.post("/api/tts/dub-srt-to-history", json={"srt": SRT, "voice_id": "", "voice_name": "Giọng A"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stats"] == {"cues": 4, "sped_up": 1, "pushed": 1, "max_push_seconds": 0.18}
    assert body["duration_seconds"] == pytest.approx(10.0)
    entry = body["entry"]
    assert entry["has_subtitles"] and entry["mode"] == "pdf"
    audio, sr = sf.read(hs._audio_path(entry["id"])[1])
    assert sr == SR and len(audio) == 10 * SR
    # Câu 1 bắt đầu đúng 1,0 s; trước đó im lặng.
    assert np.all(audio[:990] == 0) and abs(audio[1005]) > 0.05
    # Câu 3 bị đẩy tới 3 + 1,333 + 0,05 ≈ 4,383 s.
    assert "00:00:04,383 -->" in body["srt"]
    assert fake.infer.call_count == 4


def test_long_tieng_srt_hong_tra_400(api):
    client, _ = api
    assert client.post("/api/tts/dub-srt-to-history", json={"srt": "abc"}).status_code == 400


def test_long_tieng_giong_sai_tra_400(api, monkeypatch):
    client, fake = api
    fake._preset_voices = {"A": {}}
    fake.resolve_voice_name = lambda v: v if v == "A" else None
    r = client.post("/api/tts/dub-srt-to-history", json={"srt": SRT, "voice_id": "B"})
    assert r.status_code == 400
