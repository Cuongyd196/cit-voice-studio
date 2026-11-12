"""Supertonic 3 (giọng nước ngoài, 1.0.3): engine với phiên ONNX giả, danh mục, API."""
import json
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps import history_store as hs
from apps import model_catalog
from apps import supertonic_engine as st
from apps import web_stream as ws

SR = 1000
BASE_CHUNK, COMPRESS, LATENT = 10, 2, 3


class _Session:
    """Phiên ONNX giả: ghi lại input, trả output đúng hình dạng."""

    def __init__(self, fn):
        self.fn = fn
        self.calls = []

    def run(self, _outputs, feeds):
        self.calls.append(feeds)
        return [self.fn(feeds)]


def _model_dir(tmp_path):
    (tmp_path / "onnx").mkdir(parents=True)
    (tmp_path / "voice_styles").mkdir()
    cfg = {"ae": {"sample_rate": SR, "base_chunk_size": BASE_CHUNK},
           "ttl": {"chunk_compress_factor": COMPRESS, "latent_dim": LATENT}}
    (tmp_path / "onnx" / "tts.json").write_text(json.dumps(cfg))
    indexer = [-1] * 65536
    for i, code in enumerate(range(32, 0x2000)):
        indexer[code] = i
    (tmp_path / "onnx" / "unicode_indexer.json").write_text(json.dumps(indexer))
    for v in st.VOICES:
        style = {"style_ttl": {"dims": [1, 2, 3], "data": [0.0] * 6},
                 "style_dp": {"dims": [1, 2, 2], "data": [0.0] * 4}}
        (tmp_path / "voice_styles" / f"{v}.json").write_text(json.dumps(style))
    return tmp_path


def _engine(tmp_path, seconds_per_char=0.01):
    dp = _Session(lambda f: np.array([f["text_ids"].shape[1] * seconds_per_char], dtype=np.float32))
    enc = _Session(lambda f: np.zeros((1, 4, f["text_ids"].shape[1]), dtype=np.float32))
    est = _Session(lambda f: f["noisy_latent"] + 0.01)
    voc = _Session(lambda f: np.full((1, f["latent"].shape[2] * BASE_CHUNK * COMPRESS), 0.1, dtype=np.float32))
    eng = st.SupertonicTTS(_model_dir(tmp_path), sessions=(dp, enc, est, voc))
    return eng, dp, est


# --- chữ -------------------------------------------------------------------------

def test_tu_nhan_ngon_ngu():
    assert st.detect_language("Xin chào các bạn") == "vi"
    assert st.detect_language("Hello world") == "en"
    assert st.detect_language("こんにちは") == "ja"
    assert st.detect_language("안녕하세요") == "ko"


def test_the_goc_supertonic_giu_nguyen_va_bo_khoi_phu_de():
    from vieneu_utils.subtitles import display_text
    text = "Wow <laugh> ok <breath> fine <sigh>."
    assert st.convert_tags(text) == text
    assert "<breath>" in st.preprocess(text, "en")
    assert display_text(text) == "Wow ok fine."


def test_doi_the_cam_xuc_bo_the_la():
    out = st.convert_tags("Ha [cười] ừm [thở dài] e [hắng giọng] x [nghỉ 2s].")
    assert "<laugh>" in out and "<sigh>" in out
    assert "hắng" not in out and "nghỉ" not in out


def test_chuan_hoa_boc_the_ngon_ngu_va_them_dau_cham():
    assert st.preprocess("Hello  world", "en") == "<en>Hello world.</en>"
    assert st.preprocess("Wait — what?", "en") == "<en>Wait - what?</en>"


def test_chia_doan_khong_cat_so_thap_phan():
    chunks = st.chunk_text("Price is 3.5 dollars. Dr. Smith agreed! Ok?", max_len=25)
    assert "3.5" in " ".join(chunks)
    assert all(len(c) <= 25 for c in chunks[:-1])
    assert st.chunk_text("一つ。二つ。", max_len=3) == ["一つ。", "二つ。"]


# --- engine ----------------------------------------------------------------------

def test_engine_doc_ra_audio_dung_do_dai(tmp_path):
    eng, dp, est = _engine(tmp_path)
    wav = eng.infer("Hello there.", voice="m2", lang="en", speed=1.0)
    n_chars = len(st.preprocess("Hello there.", "en"))
    assert wav.dtype == np.float32 and len(wav) == int(n_chars * 0.01 * SR)
    assert len(est.calls) == st.DEFAULT_STEPS
    assert dp.calls[0]["text_ids"].dtype == np.int64


def test_engine_bo_ky_tu_khong_biet(tmp_path):
    eng, dp, _ = _engine(tmp_path)
    eng.infer("Hi \U0001f600 the\U00012000re", lang="en")
    assert dp.calls[0]["text_ids"].shape[1] == len(st.preprocess("Hi there", "en"))


def test_engine_van_ban_dai_chia_doan_co_nghi(tmp_path):
    eng, dp, _ = _engine(tmp_path)
    text = " ".join(["This is a fairly long sentence for testing."] * 12)
    parts = list(eng.infer_stream(text, lang="en"))
    assert len(parts) == len(dp.calls) > 1
    gap = int(SR * st.CHUNK_SILENCE_S)
    assert np.all(parts[1][:gap] == 0)


def test_engine_giong_va_seed(tmp_path):
    eng, _, _ = _engine(tmp_path)
    assert eng.resolve_voice_name("f3") == "F3" and eng.resolve_voice_name("Hải Đăng") is None
    assert [v for _, v in eng.list_preset_voices()] == list(st.VOICES)
    assert not hasattr(eng, "add_voice")
    with pytest.raises(ValueError):
        eng.infer("Hi", voice="X9")
    np.random.seed(1); a = eng.infer("Hello.", lang="en")
    np.random.seed(1); b = eng.infer("Hello.", lang="en")
    assert np.array_equal(a, b)


def test_danh_muc_khop_engine():
    spec = model_catalog.get(model_catalog.SUPERTONIC_ID)
    assert spec is not None and spec in model_catalog.MODELS
    assert set(model_catalog.SUPERTONIC_FILES) == set(st.MODEL_FILES)
    assert spec.sources[0].revision == model_catalog.SUPERTONIC_REVISION
    # OpenRAIL-M: giấy phép phải đi cùng trọng số, và tải ở một commit cố định.
    assert model_catalog.SUPERTONIC_REVISION.startswith("aafc6e3")
    assert len(model_catalog.SUPERTONIC_REVISION) == 40
    assert {"LICENSE", "README.md"} <= set(model_catalog.SUPERTONIC_FILES)
    assert not spec.supports_cloning and spec.sample_rate == 44_100
    assert model_catalog.BUNDLED_MODEL_ID != spec.id


# --- API -------------------------------------------------------------------------

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "history_dir", lambda: tmp_path / "history")
    monkeypatch.setattr(ws.pronunciation_settings, "apply", lambda t: t)
    eng, _, _ = _engine(tmp_path / "model")
    calls = []
    real = eng.infer

    def infer(text, **kw):
        calls.append(kw)
        return real(text, **kw)

    eng.infer = infer
    monkeypatch.setattr(ws, "vieneu", eng)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {
        "name": model_catalog.SUPERTONIC_ID, "sample_rate": SR,
        "languages": [{"code": k, "name": v} for k, v in st.LANGUAGES.items()]})
    return TestClient(ws.app), calls


def test_api_language_truyen_toi_engine(api):
    client, calls = api
    r = client.post("/api/tts/generate", json={"text": "Bonjour.", "voice_id": "F2", "language": "fr"})
    assert r.status_code == 200
    assert calls[-1]["lang"] == "fr" and calls[-1]["voice"] == "F2"
    r = client.post("/api/tts/generate", json={"text": "Hello."})
    assert r.status_code == 200 and "lang" not in calls[-1]  # bỏ trống: engine tự nhận


def test_api_language_sai_tra_400(api):
    client, _ = api
    r = client.post("/api/tts/generate", json={"text": "Hi.", "language": "xx"})
    assert r.status_code == 400 and "/health" in r.json()["detail"]


def test_health_bao_ngon_ngu_va_khong_nhan_ban(api):
    client, _ = api
    h = client.get("/health").json()
    assert h["supports_cloning"] is False
    assert {"code": "ja", "name": "Tiếng Nhật"} in h["languages"]
    assert client.post("/api/voices/custom", data={"name": "x"},
                       files={"ref_audio": ("a.wav", b"RIFF", "audio/wav")}).status_code == 400


def test_giong_supertonic_khong_co_vung_mien(api):
    client, _ = api
    voices = client.get("/voices").json()
    assert [v["id"] for v in voices][:2] == ["F1", "F2"]
    assert all(v["region"] is None for v in voices)
    assert voices[5]["gender"] == "male"
    assert (voices[0]["name"], voices[5]["name"]) == ("F1", "M1")  # khớp voice_id của API


def test_cau_nghe_thu_co_du_moi_ngon_ngu():
    assert set(st.PREVIEW_TEXTS) == set(st.LANGUAGES)


def test_nghe_thu_doc_bang_ngon_ngu_dang_chon(api, tmp_path, monkeypatch):
    client, calls = api
    monkeypatch.setattr(ws, "voice_preview_dir", lambda: tmp_path / "previews")
    assert client.get("/api/voices/preview", params={"voice_id": "M2", "language": "ja"}).status_code == 200
    assert calls[-1]["lang"] == "ja"
    assert client.get("/api/voices/preview", params={"voice_id": "M2"}).status_code == 200
    assert calls[-1]["lang"] == "en"
    assert len(list((tmp_path / "previews").iterdir())) == 2  # mỗi ngôn ngữ một bản cache


def test_language_bi_bo_qua_voi_vieneu(monkeypatch):
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": 48000})
    assert ws._language_kwargs("en") == {}
    assert ws._language_kwargs("xx") == {}
