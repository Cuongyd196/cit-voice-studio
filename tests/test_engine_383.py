"""Các sửa lỗi chất lượng lấy từ vieneu 3.8.3."""
import json
from collections import OrderedDict
from unittest.mock import Mock

import numpy as np

from vieneu.v3turbo import V3TurboVieNeuTTS
from vieneu_utils.core_utils import (
    CODEC_SAMPLES_PER_FRAME,
    ENCODER_PAD_CODE,
    SINGLE_WORD_MAX_FRAMES,
    max_expected_frames,
    pad_to_codec_frame,
    strip_encoder_pad_frame,
)


def make_tts():
    tts = V3TurboVieNeuTTS.__new__(V3TurboVieNeuTTS)
    tts.default_style = "tu_nhien"
    tts._preset_voices = {}
    tts._voice_aliases = {}
    tts._default_voice = None
    tts._ref_cache = OrderedDict()
    tts.engine = Mock()
    tts.engine.prepare_reference.return_value = (np.zeros(192, np.float32), np.zeros((5, 16), np.int64))
    tts._preclean_reference_audio = lambda p: p
    return tts


def test_giong_da_luu_bang_ban_cu_bo_frame_dem_cuoi(tmp_path):
    """Giọng nhân bản bằng bản cũ mang frame đệm (codebook-0 = 455) ở cuối: tiếng lạ
    trong mọi lượt đọc (upstream issue #198). Nạp lại thì bỏ đi."""
    codes = np.arange(4 * 16).reshape(4, 16)
    codes[-1, 0] = ENCODER_PAD_CODE
    path = tmp_path / "custom.json"
    path.write_text(json.dumps({"presets": {
        "Cũ": {"speaker_emb": [0.1] * 192, "codes": codes.tolist()},
        "Sạch": {"speaker_emb": [0.1] * 192, "codes": codes[:3].tolist()},
    }}), encoding="utf-8")
    tts = make_tts()
    assert tts.load_extra_voices(path) == 2
    assert tts._preset_voices["Cũ"]["codes"].shape == (3, 16)
    assert tts._preset_voices["Sạch"]["codes"].shape == (3, 16)
    assert tts._preset_voices["Cũ"]["is_custom"] is True
    assert tts._preset_voices["Cũ"]["featured"] is None


def test_strip_va_pad_frame_codec():
    assert strip_encoder_pad_frame(None) is None
    one = np.array([[ENCODER_PAD_CODE] * 16])
    assert strip_encoder_pad_frame(one).shape == (1, 16)     # không bỏ frame duy nhất
    wav = np.ones(CODEC_SAMPLES_PER_FRAME + 1, np.float32)
    assert len(pad_to_codec_frame(wav)) == 2 * CODEC_SAMPLES_PER_FRAME
    assert len(pad_to_codec_frame(wav, 24_000)) == len(wav)   # chỉ áp ở 48 kHz


def test_nhan_ban_cung_noi_dung_khac_duong_dan_khong_xu_ly_lai(tmp_path):
    """Mỗi lần tải lên là một file tạm mới: khoá theo nội dung nên vẫn trúng cache."""
    a, b, c = tmp_path / "a.wav", tmp_path / "b.wav", tmp_path / "c.wav"
    a.write_bytes(b"cung-noi-dung")
    b.write_bytes(b"cung-noi-dung")
    c.write_bytes(b"khac")
    tts = make_tts()
    tts.add_voice("Một", a)
    tts.encode_reference(b)
    assert tts.engine.prepare_reference.call_count == 1
    tts.encode_reference(c)
    assert tts.engine.prepare_reference.call_count == 2


def test_tran_frame_cau_ngan_theo_so_tieng():
    one = max_expected_frames("tʃˈaː2w.")
    two = max_expected_frames("tʃˈaː2w bˈaː6n.")
    assert one == SINGLE_WORD_MAX_FRAMES
    assert one < two <= SINGLE_WORD_MAX_FRAMES + 5
    # Chunk chỉ có thẻ cảm xúc cũng bị chặn, không sinh dài vô hạn.
    assert max_expected_frames("<|emotion_1|>") == SINGLE_WORD_MAX_FRAMES
