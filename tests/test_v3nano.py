"""v3 Nano: engine ONNX, kho giọng riêng, và chỗ nối vào ứng dụng.

Không test nào ở đây chạm mạng hay nạp ONNX thật: các `InferenceSession` đều bị
vá. Cái cần canh là những chỗ Nano khác Turbo — 24 kHz, style tokens `[50, 256]`
thay cho `codes`, và file giọng tuỳ chỉnh tách riêng để đổi mô hình không dùng
nhầm dữ liệu giọng của mô hình kia.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from apps import model_catalog as mc
from vieneu.v3nano import OnnxV3NanoEngine, V3NanoVieNeuTTS


def make_engine(*, frames_per_run: int = 40) -> OnnxV3NanoEngine:
    """Engine với 4 phiên ONNX giả, đủ thật để chạy trọn vòng lấy mẫu Euler."""
    eng = OnnxV3NanoEngine.__new__(OnnxV3NanoEngine)
    import threading

    eng._lock = threading.RLock()
    eng.vocab = {c: i + 3 for i, c in enumerate("abcdeɤ̆ ")}
    eng.bos, eng.eos, eng.pad = 0, 1, 2
    eng.emotion_map = {"<|emotion_0|>": "a"}
    eng._oov_warned = set()
    eng.group = 6
    eng.ref_max_frames = 140
    eng.fps = 24000 / 256 / 6
    eng.null_spk = np.zeros((1, 192), dtype=np.float32)
    eng.null_style = np.zeros((1, 50, 256), dtype=np.float32)
    eng._null_ctx = np.zeros((1, 2, 8), dtype=np.float32)
    eng._null_mask = np.ones((1, 2), dtype=bool)

    eng.s_text = Mock()
    eng.s_text.run.return_value = [np.zeros((1, 4, 8), dtype=np.float32)]
    eng.s_dur = Mock()
    eng.s_dur.run.return_value = [np.array([np.log(frames_per_run / eng.fps)], dtype=np.float32)]
    eng.s_ve = Mock()
    eng.s_ve.run.side_effect = lambda _o, feeds: [np.zeros_like(feeds["x"])]
    eng.s_dec = Mock()
    eng.s_dec.run.return_value = [np.full((1, 1, 24000), 0.5, dtype=np.float32)]
    return eng


def make_tts(engine: OnnxV3NanoEngine | None = None) -> V3NanoVieNeuTTS:
    tts = V3NanoVieNeuTTS.__new__(V3NanoVieNeuTTS)
    tts.sample_rate = OnnxV3NanoEngine.SAMPLE_RATE
    tts.backend = "onnx"
    tts.default_steps = 4
    tts.default_cfg = 3.0
    tts.default_style = "tu_nhien"
    tts.watermarker = None
    tts._preset_voices = {}
    tts._default_voice = None
    tts.engine = engine or make_engine()
    return tts


def voice_pair() -> tuple[np.ndarray, np.ndarray]:
    return (np.linspace(-1, 1, 192, dtype=np.float32),
            np.zeros((50, 256), dtype=np.float32))


# ── engine ────────────────────────────────────────────────────────────────────
def test_infer_tra_ve_float32_va_goi_du_so_buoc_euler():
    eng = make_engine()
    wav = eng.infer("abc", *voice_pair(), steps=4, cfg=3.0)

    assert wav.dtype == np.float32
    assert wav.ndim == 1 and wav.size > 0
    # cfg > 0 ⇒ mỗi bước chạy hai lượt: có điều kiện và vô điều kiện.
    assert eng.s_ve.run.call_count == 8


def test_cfg_bang_khong_bo_han_luot_vo_dieu_kien():
    eng = make_engine()
    eng.infer("abc", *voice_pair(), steps=4, cfg=0.0)
    assert eng.s_ve.run.call_count == 4


def test_speed_rut_ngan_do_dai_du_doan():
    """`speed` chia thẳng vào thời lượng duration predictor đưa ra."""
    dai = make_engine()
    dai.infer("abc", *voice_pair(), steps=1, cfg=0.0, speed=1.0)
    nhanh = make_engine()
    nhanh.infer("abc", *voice_pair(), steps=1, cfg=0.0, speed=2.0)

    khung_dai = dai.s_ve.run.call_args[0][1]["x"].shape[-1]
    khung_nhanh = nhanh.s_ve.run.call_args[0][1]["x"].shape[-1]
    assert khung_nhanh < khung_dai


def test_encode_phones_doi_tag_cam_xuc_va_bo_ky_tu_ngoai_vocab():
    eng = make_engine()
    ids = eng.encode_phones("<|emotion_0|>bZc")   # 'Z' không có trong vocab

    assert ids.dtype == np.int64
    assert ids[0, 0] == eng.bos and ids[0, -1] == eng.eos
    assert ids.tolist() == [[eng.bos, eng.vocab["a"], eng.vocab["b"], eng.vocab["c"], eng.eos]]


# ── kho giọng ─────────────────────────────────────────────────────────────────
def test_preset_dong_goi_san_dung_dinh_dang_x_vector_cong_style():
    tts = make_tts()
    tts._load_nano_voices()

    assert tts._preset_voices, "assets/voices_v3_nano.json phải đi kèm gói cài"
    assert tts._default_voice in tts._preset_voices
    v = tts._preset_voices[tts._default_voice]
    assert v["speaker_emb"].shape == (192,)
    assert v["style"].shape == (50, 256)
    # `codes` là bí danh của `style` để code viết theo layout preset của v3 Turbo
    # (speaker_emb + codes) chạy được không cần sửa.
    assert v["codes"] is v["style"]


def test_them_va_luu_giong_tuy_chinh_roundtrip_custom_only():
    tts = make_tts()
    tts._load_nano_voices()
    so_preset = len(tts._preset_voices)
    tts.encode_reference = Mock(return_value=voice_pair())

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "custom_voices_v3_nano.json"
        tts.add_voice("Giọng của tôi", "ref.wav", save=True, save_path=path)

        data = json.loads(path.read_text(encoding="utf-8"))
        assert list(data["presets"]) == ["Giọng của tôi"], "custom_only phải bỏ preset dựng sẵn"

        moi = make_tts()
        moi._load_nano_voices()
        assert moi.load_extra_voices(path) == 1
        assert len(moi._preset_voices) == so_preset + 1
        giong = moi._preset_voices["Giọng của tôi"]
        assert giong["is_custom"] is True
        assert giong["style"].shape == (50, 256)
        np.testing.assert_allclose(giong["speaker_emb"], voice_pair()[0], atol=1e-5)


def test_luu_that_bai_thi_khong_de_lai_giong_nua_voi_trong_bo_nho():
    tts = make_tts()
    tts._load_nano_voices()
    tts.encode_reference = Mock(return_value=voice_pair())

    with patch.object(V3NanoVieNeuTTS, "save_voices", side_effect=OSError("đĩa đầy")):
        with pytest.raises(OSError):
            tts.add_voice("Hỏng", "ref.wav", save=True, save_path="x.json")
    assert "Hỏng" not in tts._preset_voices


def test_resolve_voice_bao_loi_ro_khi_thieu_style():
    tts = make_tts()
    with pytest.raises(ValueError):
        tts._resolve_voice({"speaker_emb": np.zeros(192, dtype=np.float32)}, None)


# ── API chung với các engine khác ─────────────────────────────────────────────
def test_infer_ghep_chunk_va_giu_24_khz():
    tts = make_tts()
    tts._load_nano_voices()
    wav = tts.infer("Câu một ở đây. Câu hai dài hơn một chút để phải tách chunk.")

    assert tts.sample_rate == 24_000
    assert wav.dtype == np.float32 and wav.size > 0


def test_infer_stream_yield_tung_chunk_da_hoan_chinh():
    tts = make_tts()
    tts._load_nano_voices()
    ra = list(tts.infer_stream("Câu một. Câu hai."))

    assert ra and all(c.dtype == np.float32 for c in ra)


def test_infer_batch_giu_nguyen_thu_tu_va_so_luong():
    tts = make_tts()
    tts._load_nano_voices()
    ra = tts.infer_batch(["Một hai ba.", "Bốn năm sáu."])
    assert len(ra) == 2


def test_factory_nhan_mode_v3nano():
    from vieneu.factory import Vieneu

    with patch("vieneu.v3nano.V3NanoVieNeuTTS") as m:
        Vieneu(mode="v3nano")
    m.assert_called_once()


# ── chỗ nối vào ứng dụng ──────────────────────────────────────────────────────
def test_kho_giong_tuy_chinh_tach_rieng_theo_mo_hinh():
    """Nano và Turbo lưu giọng ở hai file khác nhau.

    Hai mô hình lưu hai kiểu dữ liệu khác nhau (style tokens [50,256] so với
    codes rời rạc). Dùng chung một file thì đổi mô hình là nạp nhầm giọng, và
    lần lưu sau ghi đè mất giọng của mô hình kia.
    """
    import apps.web_stream as ws

    with patch.object(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Nano (preview)"}):
        nano = ws._custom_voices_path()
    with patch.object(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)"}):
        turbo = ws._custom_voices_path()

    assert nano.name == "custom_voices_v3_nano.json"
    assert turbo.name == "custom_voices_v3_turbo.json"
    assert nano != turbo


# ── catalog: danh sách file phải khớp thứ engine thật sự mở ───────────────────
def test_nano_files_trong_catalog_khop_voi_engine():
    """Tải trước một đằng, engine đọc một nẻo là lỗi chỉ lộ ra lúc offline."""
    from vieneu import v3nano

    can = set(v3nano._GRAPH_FILES) | set(v3nano._CLONE_FILES) | {v3nano._DENOISER_FILE}
    assert set(mc.NANO_FILES) == can
    assert mc.NANO_REPO == v3nano._NANO_REPO


def test_spec_nano_khai_bao_dung_24_khz_va_cpu():
    spec = mc.get("VieNeu-TTS-v3-Nano (preview)")
    assert spec is not None
    assert spec.sample_rate == 24_000
    assert spec.device == "cpu"
    assert spec.requires == (), "Nano là đường ONNX torch-free, không được đòi torch"
    ok, ly_do = mc.compatible(spec, has_torch=False, has_cuda=False)
    assert ok and ly_do is None
