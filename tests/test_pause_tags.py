import io
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from vieneu_utils.pause_tags import (
    DEFAULT_PAUSE_S,
    MAX_PAUSE_S,
    has_pause_tags,
    parse_pause,
    split_pauses,
)


@pytest.mark.parametrize(
    ("arg", "seconds"),
    [
        (" 2s", 2.0), (" 1.5s", 1.5), (" 1,5 giây", 1.5), (" 500ms", 0.5),
        (" 3", 3.0), ("", DEFAULT_PAUSE_S), (" 2 GIAY", 2.0), (" 0s", 0.0),
        (" 200s", MAX_PAUSE_S), (" abc", 0.0), (" 2 phút", 0.0),
    ],
)
def test_parse_pause(arg, seconds):
    assert parse_pause(arg) == pytest.approx(seconds)


def test_split_basic_and_variants():
    assert split_pauses("AI tạo sinh [nghỉ 2s] sau đó mới đọc.") == [
        ("AI tạo sinh", 2.0), ("sau đó mới đọc.", 0.0)]
    assert split_pauses("A [Nghỉ 1s] B [pause 500ms] C [nghi 3] D") == [
        ("A", 1.0), ("B", 0.5), ("C", 3.0), ("D", 0.0)]


def test_no_tag_passthrough():
    assert split_pauses("Không có thẻ.") == [("Không có thẻ.", 0.0)]
    assert not has_pause_tags("Không có thẻ [cười].")


def test_adjacent_tags_add_up_and_leading_trailing():
    assert split_pauses("A [nghỉ 1s] [nghỉ 2s] B") == [("A", 3.0), ("B", 0.0)]
    assert split_pauses("[nghỉ 1s] A [nghỉ 2s]") == [("", 1.0), ("A", 2.0)]


def test_bad_tag_removed_not_read_aloud():
    assert split_pauses("A [nghỉ abc] B") == [("A", 0.0), ("B", 0.0)]


def test_other_brackets_untouched():
    # Thẻ cảm xúc và chữ bắt đầu bằng "nghi..." không phải thẻ nghỉ.
    text = "[cười] Nghiêm túc [nghiêm túc] đấy."
    assert split_pauses(text) == [(text, 0.0)]


# ---------------------------------------------------------------- web_stream

SR = 48000
SPEECH = 4800  # 0.1s mỗi đoạn giọng nói giả


@pytest.fixture
def ws_client(tmp_path, monkeypatch):
    from apps import pronunciation_settings as ps
    from apps import web_stream as ws

    monkeypatch.setattr(ps, "dict_path", lambda: tmp_path / "pronunciation-dict.json")
    monkeypatch.setattr(ps, "_cache_key", None)
    engine = Mock()
    engine.sample_rate = SR
    engine.infer.return_value = np.full(SPEECH, 0.5, dtype=np.float32)
    engine.infer_stream.side_effect = lambda *a, **k: iter([np.full(SPEECH, 0.5, dtype=np.float32)])
    monkeypatch.setattr(ws, "vieneu", engine)
    monkeypatch.setattr(ws, "current_model_info", {"sample_rate": SR})
    with TestClient(ws.app) as c:
        yield c, engine


def wav_samples(content: bytes) -> np.ndarray:
    data, sr = sf.read(io.BytesIO(content), dtype="float32")
    assert sr == SR
    return data


def test_generate_inserts_exact_silence(ws_client):
    c, engine = ws_client
    r = c.post("/api/tts/generate", json={"text": "AI tạo sinh [nghỉ 2s] sau đó mới đọc."})
    assert r.status_code == 200
    assert [call.args[0] for call in engine.infer.call_args_list] == ["AI tạo sinh", "sau đó mới đọc."]
    audio = wav_samples(r.content)
    assert len(audio) == 2 * SPEECH + 2 * SR
    assert np.all(audio[SPEECH:SPEECH + 2 * SR] == 0)
    assert float(r.headers["X-Duration-Seconds"]) == pytest.approx(2.2, abs=0.01)


def test_speed_does_not_stretch_pause(ws_client, monkeypatch):
    from apps import web_stream as ws

    # Giả lập time-stretch: tốc độ 2x -> nửa độ dài.
    monkeypatch.setattr(ws, "_apply_speed", lambda a, s: a[: int(len(a) / s)])
    c, _ = ws_client
    r = c.post("/api/tts/generate", json={"text": "A [nghỉ 1s] B", "speed": 2.0})
    assert len(wav_samples(r.content)) == 2 * (SPEECH // 2) + SR


def test_dictionary_applies_per_segment_not_to_tag(ws_client):
    c, engine = ws_client
    c.put("/api/pronunciations", json={"entries": [
        {"word": "nghỉ", "reading": "NGHỈ NGƠI"}, {"word": "KTX", "reading": "ký túc xá"}]})
    r = c.post("/api/tts/generate", json={"text": "Về KTX [nghỉ 1s] nghỉ ngơi"})
    assert r.status_code == 200
    assert [call.args[0] for call in engine.infer.call_args_list] == ["Về ký túc xá", "NGHỈ NGƠI ngơi"]
    assert len(wav_samples(r.content)) == 2 * SPEECH + SR


def test_only_pause_tag_is_rejected(ws_client):
    c, engine = ws_client
    r = c.post("/api/tts/generate", json={"text": "[nghỉ 2s]"})
    assert r.status_code == 400
    engine.infer.assert_not_called()


def test_stream_emits_silence_between_segments(ws_client):
    c, engine = ws_client
    r = c.get("/stream", params={"text": "Một [nghỉ 0.5s] Hai"})
    assert r.status_code == 200
    pcm = np.frombuffer(r.content[44:], dtype=np.int16)
    assert len(pcm) == 2 * SPEECH + SR // 2
    assert np.all(pcm[SPEECH:SPEECH + SR // 2] == 0)
    assert [call.args[0] for call in engine.infer_stream.call_args_list] == ["Một", "Hai"]


def test_conversation_turn_with_pause(ws_client):
    c, engine = ws_client
    r = c.post("/api/tts/conversation", json={
        "turns": [{"speaker": "A", "text": "Chào [nghỉ 1s] bạn"}, {"speaker": "B", "text": "Chào"}],
        "silence_duration": 0.5,
    })
    assert r.status_code == 200
    assert len(wav_samples(r.content)) == 3 * SPEECH + SR + SR // 2
