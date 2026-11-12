import base64
import io
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from vieneu_utils.core_utils import V3_GAP_SILENCE
from vieneu_utils.subtitles import (
    CUE_MAX_CHARS,
    LINE_CHARS,
    build_units,
    display_text,
    to_srt,
    unit_cues,
)

PARA, SENT = V3_GAP_SILENCE["para"], V3_GAP_SILENCE["sentence"]


def test_units_by_sentence_with_gaps():
    units = build_units("Câu thứ nhất khá là dài. Câu thứ hai cũng khá dài.\nĐoạn mới ở đây nhé bạn.")
    assert [(u.text, u.pause_after) for u in units] == [
        ("Câu thứ nhất khá là dài.", SENT),
        ("Câu thứ hai cũng khá dài.", PARA),
        ("Đoạn mới ở đây nhé bạn.", 0.0),
    ]


def test_short_sentences_merged():
    units = build_units("Xin chào. Hôm nay trời rất đẹp và mát mẻ. Ừ.")
    assert [u.text for u in units] == ["Xin chào. Hôm nay trời rất đẹp và mát mẻ. Ừ."]


def test_pause_tags_split_units_exact_pause():
    units = build_units("[nghỉ 1s] AI tạo sinh đang thay đổi [nghỉ 2s] mọi ngành nghề hiện nay.")
    assert [(u.text, u.pause_after) for u in units] == [
        ("", 1.0), ("AI tạo sinh đang thay đổi", 2.0), ("mọi ngành nghề hiện nay.", 0.0)]


def test_display_text_strips_tags():
    assert display_text("Xin chào [cười]  bạn <|emotion_2|> nhé") == "Xin chào bạn nhé"
    assert display_text("Xong rồi [cười].") == "Xong rồi."


def test_long_sentence_split_into_readable_cues():
    text = ("Chương trình khuyến mãi lớn nhất năm, áp dụng cho toàn bộ sản phẩm, "
            "kéo dài từ hôm nay cho đến hết ngày cuối cùng của tháng mười hai năm nay.")
    cues = unit_cues(text, 1.0, 9.0)
    assert len(cues) > 1
    assert cues[0].start == 1.0 and cues[-1].end == 9.0
    for a, b in zip(cues, cues[1:]):
        assert a.end == pytest.approx(b.start)
    for c in cues:
        assert len(c.text.replace("\n", " ")) <= CUE_MAX_CHARS
        assert all(len(line) <= LINE_CHARS + 10 for line in c.text.split("\n"))
    assert " ".join(c.text.replace("\n", " ") for c in cues) == text


def test_srt_format():
    cues = unit_cues("Xin chào các bạn thân mến.", 0.0, 3661.5)
    assert to_srt(cues) == "1\n00:00:00,000 --> 01:01:01,500\nXin chào các bạn thân mến.\n"


# ---------------------------------------------------------------- endpoint

SR = 48000
PER_CHAR = 480  # engine giả: 10 ms audio mỗi ký tự


@pytest.fixture
def ws(tmp_path, monkeypatch):
    from apps import pronunciation_settings as ps
    from apps import web_stream as ws

    monkeypatch.setattr(ps, "dict_path", lambda: tmp_path / "pronunciation-dict.json")
    monkeypatch.setattr(ps, "_cache_key", None)
    engine = Mock()
    engine.infer.side_effect = lambda text, **k: np.full(len(text) * PER_CHAR, 0.5, dtype=np.float32)
    monkeypatch.setattr(ws, "vieneu", engine)
    monkeypatch.setattr(ws, "current_model_info", {"sample_rate": SR})
    with TestClient(ws.app) as c:
        yield c, engine


def test_endpoint_timings_match_real_audio(ws):
    c, engine = ws
    text = "Học sinh nhận SGK tại KTX hôm nay. [nghỉ 1s] Mọi người nhớ mang theo giấy tờ [cười]."
    r = c.post("/api/tts/generate-with-subtitles", json={"text": text})
    assert r.status_code == 200, r.text
    body = r.json()
    audio, sr = sf.read(io.BytesIO(base64.b64decode(body["audio_base64"])), dtype="float32")
    assert sr == SR and body["format"] == "wav"

    spoken = [call.args[0] for call in engine.infer.call_args_list]
    # Từ điển mặc định áp cho giọng đọc...
    assert spoken[0] == "Học sinh nhận sách giáo khoa tại ký túc xá hôm nay."
    # ...nhưng phụ đề giữ chữ gốc, bỏ thẻ cảm xúc.
    texts = [cue["text"].replace("\n", " ") for cue in body["cues"]]
    assert texts == ["Học sinh nhận SGK tại KTX hôm nay.", "Mọi người nhớ mang theo giấy tờ."]

    d1 = len(spoken[0]) * PER_CHAR / SR
    d2 = len(spoken[1]) * PER_CHAR / SR
    first, second = body["cues"]
    assert first["start"] == 0 and first["end"] == pytest.approx(d1, abs=0.002)
    assert second["start"] == pytest.approx(d1 + 1.0, abs=0.002)  # thẻ nghỉ 1s
    assert second["end"] == pytest.approx(d1 + 1.0 + d2, abs=0.002)
    assert len(audio) / SR == pytest.approx(second["end"], abs=0.002)
    assert body["srt"].startswith("1\n00:00:00,000 --> ")


def test_endpoint_rejects_pause_only(ws):
    c, engine = ws
    assert c.post("/api/tts/generate-with-subtitles", json={"text": "[nghỉ 2s]"}).status_code == 400
    engine.infer.assert_not_called()


def test_endpoint_mp3(ws):
    c, _ = ws
    body = c.post("/api/tts/generate-with-subtitles", json={"text": "Xin chào các bạn thân mến.", "format": "mp3"}).json()
    assert body["format"] in ("mp3",) and len(base64.b64decode(body["audio_base64"])) > 0
