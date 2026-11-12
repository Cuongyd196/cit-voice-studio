"""Audio dài không nằm trọn trong RAM (người dùng báo, 2026-09):

- Bài ~2 giờ làm backend hết bộ nhớ: "Unable to allocate 117 MiB for an array with
  shape (30557280,)" — ghép dồn từng câu + đổi tốc độ trên cả khối.
- Tạo xong, phát được ~1,2 giây thì cửa sổ app trắng: trình duyệt vừa giữ, vừa
  phát, vừa tải ngược ~690 MB lên để lưu lịch sử.

Giờ backend đọc theo khối rồi ghi dần ra file, và giao diện nhận mục lịch sử (URL)
thay vì cả khối audio.
"""
import io
import tracemalloc
from unittest.mock import Mock

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from apps import history_store as hs
from apps import web_stream as ws
from vieneu_utils.core_utils import pause_pad_samples

SR = 8000


def _cau(i: int) -> str:
    return f"Đây là câu thử số {i} của một bài rất dài, đọc cho đủ độ dài."


def _bai(n_cau: int, cau_moi_doan: int = 5) -> str:
    paras = []
    for start in range(0, n_cau, cau_moi_doan):
        paras.append(" ".join(_cau(i) for i in range(start, min(start + cau_moi_doan, n_cau))))
    return "\n".join(paras)


def _infer_theo_do_dai(seg: str) -> np.ndarray:
    # 100 mẫu mỗi ký tự: đủ để kiểm tra độ dài, không cần mô hình.
    return np.full(len(seg) * 100, 0.1, dtype=np.float32)


@pytest.fixture(autouse=True)
def khong_tu_dien(monkeypatch):
    monkeypatch.setattr(ws.pronunciation_settings, "apply", lambda t: t)


# ---------------------------------------------------------------------------
# Chia khối
# ---------------------------------------------------------------------------

def test_van_ban_ngan_la_mot_khoi_y_nguyen():
    text = _bai(10)
    assert ws._text_blocks(text) == [(text, 0.0)]


def test_van_ban_dai_chia_khoi_tai_ranh_gioi_cau_giu_du_chu():
    text = _bai(400)
    blocks = ws._text_blocks(text, limit=3000)
    assert len(blocks) > 5
    assert all(len(b) <= 3000 for b, _ in blocks)
    # Không mất, không lặp câu nào, đúng thứ tự.
    joined = " ".join(b.replace("\n", " ") for b, _ in blocks)
    assert joined.split() == text.replace("\n", " ").split()
    # Khối cuối không có khoảng lặng sau; khoảng lặng giữa khối theo ranh giới.
    assert blocks[-1][1] == 0.0
    gaps = {g for _, g in blocks[:-1]}
    assert gaps <= {ws.V3_GAP_SILENCE["para"], ws.V3_GAP_SILENCE["sentence"]}


def test_ranh_gioi_doan_van_nghi_dai_hon_ranh_gioi_cau():
    para = " ".join(_cau(i) for i in range(20))      # ~1300 ký tự mỗi đoạn
    # Ngưỡng vừa khít một đoạn: câu đầu đoạn sau không lọt, khối cắt đúng cuối đoạn.
    blocks = ws._text_blocks(f"{para}\n{para}\n{para}", limit=len(para) + 10)
    assert blocks[0][1] == ws.V3_GAP_SILENCE["para"]


def test_mot_cau_dai_hon_nguong_van_giu_nguyen():
    cau = "chữ " * 1500
    assert ws._text_blocks(cau.strip(), limit=3000) == [(cau.strip(), 0.0)]


# ---------------------------------------------------------------------------
# Ghi ra file
# ---------------------------------------------------------------------------

def test_van_ban_ngan_ghi_file_giong_tung_byte_cach_cu(tmp_path):
    text = "Xin chào các bạn. [nghỉ 1s] Hẹn gặp lại."
    cu = ws._wav_bytes(ws._synthesize(text, SR, _infer_theo_do_dai, speed=1.0), SR)
    ws._synthesize_to_file(text, SR, _infer_theo_do_dai, tmp_path / "a.wav", speed=1.0)
    assert (tmp_path / "a.wav").read_bytes() == cu


def test_van_ban_dai_doc_theo_khoi_va_chen_khoang_lang(tmp_path):
    text = _bai(400)
    calls = []
    infer = lambda seg: (calls.append(seg), _infer_theo_do_dai(seg))[1]  # noqa: E731
    n = ws._synthesize_to_file(text, SR, infer, tmp_path / "a.wav")
    blocks = ws._text_blocks(text)
    assert calls == [b for b, _ in blocks]
    gap_samples = sum(int(round(SR * g)) for _, g in blocks[:-1])
    assert n == sum(len(b) * 100 for b, _ in blocks) + gap_samples
    assert sf.info(str(tmp_path / "a.wav")).frames == n


def test_ram_khong_tang_theo_do_dai_bai(tmp_path):
    """Tổng audio ~115 MB float32 nhưng đỉnh RAM chỉ cỡ một khối."""
    text = _bai(5000)
    total_bytes = len(text) * 100 * 4
    tracemalloc.start()
    ws._synthesize_to_file(text, SR, _infer_theo_do_dai, tmp_path / "a.wav", speed=1.0)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert total_bytes > 100 * 1024 ** 2
    assert peak < total_bytes / 20, (peak, total_bytes)


def test_doi_toc_do_ap_theo_tung_khoi(tmp_path, monkeypatch):
    sizes = []
    monkeypatch.setattr(ws, "_apply_speed", lambda a, s: (sizes.append(len(a)), a)[1])
    ws._synthesize_to_file(_bai(400), SR, _infer_theo_do_dai, tmp_path / "a.wav", speed=1.1)
    assert len(sizes) == len(ws._text_blocks(_bai(400)))


def test_phu_de_ghi_file_giong_cach_cu(tmp_path):
    text = "Câu thứ nhất khá dài để không bị gộp. Câu thứ hai cũng đủ dài nhé."
    wav_cu, cues_cu = ws._synthesize_with_cues(text, SR, _infer_theo_do_dai)
    n, cues = ws._synthesize_with_cues_to_file(text, SR, _infer_theo_do_dai, tmp_path / "a.wav")
    assert n == len(wav_cu)
    assert [(c.start, c.end, c.text) for c in cues] == [(c.start, c.end, c.text) for c in cues_cu]
    assert (tmp_path / "a.wav").read_bytes() == ws._wav_bytes(wav_cu, SR)


def test_wav_sang_mp3_theo_doan(tmp_path):
    sf.write(str(tmp_path / "a.wav"), np.zeros(SR * 3, dtype=np.float32), SR, subtype="PCM_16")
    assert hs.wav_file_to_mp3(tmp_path / "a.wav", tmp_path / "a.mp3") is True
    assert sf.info(str(tmp_path / "a.mp3")).format == "MP3"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "history_dir", lambda: tmp_path / "history")
    fake = Mock()
    fake.infer.side_effect = lambda seg, **kw: _infer_theo_do_dai(seg)
    monkeypatch.setattr(ws, "vieneu", fake)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)", "sample_rate": SR})
    return TestClient(ws.app), fake


def test_api_generate_van_tra_wav_nhu_cu(api):
    client, _ = api
    text = "Xin chào các bạn. Hẹn gặp lại."
    r = client.post("/api/tts/generate", json={"text": text})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert r.content == ws._wav_bytes(ws._synthesize(text, SR, _infer_theo_do_dai), SR)
    assert float(r.headers["X-Duration-Seconds"]) > 0


def test_api_generate_mp3(api):
    client, _ = api
    r = client.post("/api/tts/generate", json={"text": "Xin chào các bạn.", "format": "mp3"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert sf.info(io.BytesIO(r.content)).format == "MP3"


def test_tao_giong_luu_thang_vao_lich_su(api, tmp_path):
    client, _ = api
    r = client.post("/api/tts/generate-to-history",
                    json={"text": _bai(400), "voice_id": "Minh Đức", "voice_name": "Minh Đức"})
    assert r.status_code == 200, r.text
    body = r.json()
    entry = body["entry"]
    assert entry["audio_url"] == f"/api/history/{entry['id']}/audio"
    assert entry["voice_name"] == "Minh Đức" and entry["format"] == "wav"
    assert body["srt"] is None and body["sample_rate"] == SR
    audio = client.get(entry["audio_url"])
    assert audio.status_code == 200
    assert abs(sf.info(io.BytesIO(audio.content)).frames - body["duration_seconds"] * SR) <= SR * 0.001
    # Không để lại file tạm; mục có trong danh sách lịch sử.
    hist = tmp_path / "history"
    assert not list(hist.glob(".tmp-*"))
    assert client.get("/api/history").json()["entries"][0]["id"] == entry["id"]


def test_tao_giong_kem_phu_de_vao_lich_su(api):
    client, _ = api
    r = client.post("/api/tts/generate-to-history",
                    json={"text": "Câu thứ nhất khá dài để không bị gộp. Câu thứ hai cũng đủ dài nhé.",
                          "subtitles": True})
    body = r.json()
    assert "-->" in body["srt"]
    assert client.get(body["entry"]["subtitles_url"]).text.strip() == body["srt"].strip()


def test_tao_giong_loi_khong_de_lai_file_tam(api, tmp_path):
    client, fake = api
    fake.infer.side_effect = RuntimeError("hỏng")
    r = client.post("/api/tts/generate-to-history", json={"text": "Xin chào."})
    assert r.status_code == 500
    assert not list((tmp_path / "history").glob(".tmp-*"))
    assert client.get("/api/history").json()["entries"] == []


def test_tai_ve_wav_va_mp3_tu_lich_su(api, tmp_path):
    client, _ = api
    entry = client.post("/api/tts/generate-to-history", json={"text": "Xin chào các bạn."}).json()["entry"]
    wav = client.get(f"{entry['audio_url']}?download=true")
    assert "attachment" in wav.headers["content-disposition"]
    mp3 = client.get(f"/api/history/{entry['id']}/mp3")
    assert mp3.status_code == 200 and mp3.headers["content-type"] == "audio/mpeg"
    assert sf.info(io.BytesIO(mp3.content)).format == "MP3"
    assert not list((tmp_path / "history").glob(".tmp-*"))


def test_export_audio_cho_ban_desktop(api, tmp_path):
    client, _ = api
    entry = client.post("/api/tts/generate-to-history", json={"text": "Xin chào các bạn."}).json()["entry"]
    out_wav = hs.export_audio(entry["id"], tmp_path / "ra.wav", "wav")
    assert out_wav.read_bytes() == client.get(entry["audio_url"]).content
    out_mp3 = hs.export_audio(entry["id"], tmp_path / "ra.mp3", "mp3")
    assert sf.info(str(out_mp3)).format == "MP3"


def test_desktop_luu_audio_lich_su_khong_qua_base64(monkeypatch, tmp_path):
    from apps import desktop_app

    goi = {}
    monkeypatch.setattr(hs, "export_audio", lambda eid, dest, fmt: (goi.update(eid=eid, dest=dest, fmt=fmt), dest)[1])
    api = desktop_app.DesktopApi()
    api.set_window(Mock())
    monkeypatch.setattr(api, "_ask_save_path", lambda name: str(tmp_path / name))
    res = api.save_history_audio("a" * 32, "bai.mp3", "mp3")
    assert res["success"] is True and goi["fmt"] == "mp3" and goi["eid"] == "a" * 32
    monkeypatch.setattr(api, "_ask_save_path", lambda name: None)
    assert api.save_history_audio("a" * 32, "bai.wav")["cancelled"] is True


# ---------------------------------------------------------------------------
# Khoảng nghỉ giữa khối / câu: TỔNG tối thiểu, chỉ bù phần thiếu (engine 3.8.3)
# ---------------------------------------------------------------------------

def _infer_co_duoi_im(seg: str) -> np.ndarray:
    """Giọng giả có sẵn 0,2 s im lặng ở đuôi, như model thật hay sinh."""
    return np.concatenate([np.full(len(seg) * 10, 0.1, dtype=np.float32),
                           np.zeros(int(0.2 * SR), dtype=np.float32)])


def test_giua_khoi_chi_bu_phan_nghi_con_thieu(tmp_path):
    text = _bai(400)
    blocks = ws._text_blocks(text)
    assert len(blocks) > 1
    n = ws._synthesize_to_file(text, SR, _infer_co_duoi_im, tmp_path / "a.wav")
    wavs = [_infer_co_duoi_im(b) for b, _ in blocks]
    pads = [pause_pad_samples(wavs[i], wavs[i + 1], SR, blocks[i][1]) for i in range(len(wavs) - 1)]
    # Đuôi im 0,2 s đã tính vào khoảng nghỉ: bù ít hơn cả khoảng nghỉ (±1 cửa sổ đo 10 ms).
    for pad, (_, gap) in zip(pads, blocks):
        assert abs(pad - (int(gap * SR) - int(0.2 * SR))) <= SR // 100
    assert n == sum(len(w) for w in wavs) + sum(pads)
    assert sf.info(str(tmp_path / "a.wav")).frames == n


def test_phu_de_nghi_tu_nhien_bu_thieu_the_nghi_chen_du(tmp_path):
    from vieneu_utils.core_utils import V3_GAP_SILENCE
    text = "Câu thứ nhất đủ dài để đứng riêng. Câu thứ hai cũng đủ dài nhé. [nghỉ 1s] Câu cuối cùng đủ dài luôn."
    units = ws.build_units(text)
    assert [u.tag_pause for u in units] == [False, True, True]

    def infer(seg):
        return np.full(SR, 0.1, dtype=np.float32)   # không có im lặng ở mép

    n, cues = ws._synthesize_with_cues_to_file(text, SR, infer, tmp_path / "b.wav")
    # _trim_edges giữ 3 đơn vị giọng nguyên (không có im lặng để cắt).
    gap1 = int(V3_GAP_SILENCE["sentence"] * SR)
    assert n == 3 * SR + gap1 + SR
    assert cues[1].start == pytest.approx((SR + gap1) / SR)
    assert cues[2].start == pytest.approx((2 * SR + gap1 + SR) / SR)
