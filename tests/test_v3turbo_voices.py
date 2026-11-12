"""Bộ giọng v3 Turbo lấy từ vieneu 3.8.3: 25 giọng, giọng tác giả chọn xếp đầu,
tên cũ vẫn gọi được. Không nạp mô hình — chỉ phần đăng ký giọng."""
import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from apps import web_stream as ws
from tests.test_custom_voices import make_tts

VOICES_FILE = Path(__file__).resolve().parents[1] / "src" / "vieneu" / "assets" / "voices_v3_turbo.json"


def test_file_giong_co_25_giong_va_mac_dinh_hai_dang():
    tts = make_tts()
    assert len(tts._preset_voices) == 25
    assert tts._default_voice == "Hải Đăng"
    for name in ("Adam bựa", "Thiện Minh", "Hải Đăng", "Thiền Tâm Đức", "Quốc Tuấn"):
        assert name in tts._preset_voices
    # Giọng cũ không mất tên nào (lịch sử, API cũ vẫn gọi được).
    for name in ("Adam", "Ngọc Huyền", "Minh Đức", "Xuân Vĩnh", "Trúc Ly"):
        assert name in tts._preset_voices


def test_giong_tac_gia_chon_dung_dau_theo_thu_hang():
    tts = make_tts()
    ids = [vid for _, vid in tts.list_preset_voices()]
    data = json.loads(VOICES_FILE.read_text(encoding="utf-8"))["presets"]
    featured = sorted((v["featured"], n) for n, v in data.items() if v.get("featured"))
    assert ids[: len(featured)] == [n for _, n in featured]
    assert len(ids) == 25 and len(set(ids)) == 25


def test_ten_cu_tro_toi_giong_moi():
    tts = make_tts()
    assert tts.resolve_voice_name("Minh Quân") == "Hải Đăng"
    assert tts.resolve_voice_name("Minh Quân Pro") == "Hải Đăng"
    assert tts.get_preset_voice("Minh Quân") is tts._preset_voices["Hải Đăng"]
    emb, _ = tts._resolve_ref("Minh Quân", None, True, True)
    assert np.array_equal(emb, tts._preset_voices["Hải Đăng"]["speaker_emb"])
    assert tts.resolve_voice_name("Không có") is None


def test_giong_that_thang_ten_cu_trung_ten():
    tts = make_tts()
    tts._preset_voices["Minh Quân"] = dict(tts._preset_voices["Adam"])
    assert tts.resolve_voice_name("Minh Quân") == "Minh Quân"


def test_giong_nguoi_dung_luu_khong_duoc_danh_dau_va_khong_dang_ky_ten_cu(tmp_path):
    tts = make_tts()
    extra = tmp_path / "custom.json"
    extra.write_text(json.dumps({"presets": {"Giọng tôi": {
        "speaker_emb": [0.0] * 192, "codes": [[1, 2]], "featured": 1, "aliases": ["Adam bựa 2"],
    }}}), encoding="utf-8")
    assert tts.load_extra_voices(extra) == 1
    assert tts._preset_voices["Giọng tôi"]["featured"] is None
    assert tts.resolve_voice_name("Adam bựa 2") is None
    assert tts._default_voice == "Hải Đăng"


def test_api_voices_gan_co_featured(monkeypatch):
    tts = make_tts()
    monkeypatch.setattr(ws, "vieneu", tts)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": 48_000})
    body = TestClient(ws.app).get("/voices").json()
    voices = body["voices"] if isinstance(body, dict) else body
    assert len(voices) == 25
    assert sum(v["featured"] for v in voices) == 10
    assert all(v["featured"] for v in voices[:10])
