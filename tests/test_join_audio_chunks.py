"""join_audio_chunks ghép một lần (tuyến tính) phải cho kết quả Y HỆT bản cũ ghép dồn
(đường v1/v2); đường v3 (``silence_ps``) chỉ chèn phần khoảng nghỉ còn thiếu."""
from typing import List, Optional

import numpy as np
import pytest

from vieneu_utils.core_utils import join_audio_chunks, pause_pad_samples


# Bản cũ (trước khi sửa lỗi hết RAM với bài ~2 giờ), giữ làm chuẩn so sánh.
def _join_cu(
    chunks: List[np.ndarray],
    sr: int,
    silence_p: float = 0.0,
    crossfade_p: float = 0.0,
    silence_ps: Optional[List[float]] = None,
) -> np.ndarray:
    """Ghép các chunk audio. ``silence_ps`` (tuỳ chọn) cho im lặng RIÊNG từng khe
    nối — ``silence_ps[i]`` là im lặng (giây) giữa chunk ``i`` và ``i+1`` — dùng để
    nghỉ dài/ngắn khác nhau theo loại ranh giới. Khi truyền ``silence_ps`` thì
    ``silence_p``/``crossfade_p`` bị bỏ qua.
    """
    if not chunks:
        return np.array([], dtype=np.float32)
    if len(chunks) == 1:
        return chunks[0]

    silence_samples   = int(sr * silence_p)
    crossfade_samples = int(sr * crossfade_p)
    final_wav = chunks[0]

    for i in range(1, len(chunks)):
        next_chunk = chunks[i]
        if silence_ps is not None:
            gap_samples = int(sr * silence_ps[i - 1]) if i - 1 < len(silence_ps) else 0
            if gap_samples > 0:
                silence   = np.zeros(gap_samples, dtype=np.float32)
                final_wav = np.concatenate([final_wav, silence, next_chunk])
            else:
                final_wav = np.concatenate([final_wav, next_chunk])
        elif silence_samples > 0:
            silence   = np.zeros(silence_samples, dtype=np.float32)
            final_wav = np.concatenate([final_wav, silence, next_chunk])
        elif crossfade_samples > 0:
            overlap = min(len(final_wav), len(next_chunk), crossfade_samples)
            if overlap > 0:
                fade_out  = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
                fade_in   = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
                blended   = final_wav[-overlap:] * fade_out + next_chunk[:overlap] * fade_in
                final_wav = np.concatenate([final_wav[:-overlap], blended, next_chunk[overlap:]])
            else:
                final_wav = np.concatenate([final_wav, next_chunk])
        else:
            final_wav = np.concatenate([final_wav, next_chunk])

    return final_wav


def _chunks(rng, n, tiny=False):
    out = []
    for _ in range(n):
        size = int(rng.integers(0, 40)) if tiny and rng.random() < 0.5 else int(rng.integers(50, 400))
        out.append(rng.standard_normal(size).astype(np.float32))
    return out


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("mode", ["none", "silence", "crossfade"])
def test_ghep_mot_lan_giong_het_ban_cu(seed, mode):
    rng = np.random.default_rng(seed)
    chunks = _chunks(rng, int(rng.integers(1, 30)), tiny=seed % 2 == 0)
    sr = 1000
    kw = {}
    if mode == "silence":
        kw["silence_p"] = 0.02
    elif mode == "crossfade":
        kw["crossfade_p"] = 0.05   # 50 mẫu, dài hơn nhiều đoạn "tiny"
    moi = join_audio_chunks([c.copy() for c in chunks], sr, **kw)
    cu = _join_cu([c.copy() for c in chunks], sr, **kw)
    assert moi.dtype == cu.dtype
    np.testing.assert_allclose(moi, cu, rtol=0, atol=1e-6)


def test_nhieu_doan_khong_ghep_don():
    """1000 đoạn: bản cũ chép lại mảng đang lớn ~1000 lần; bản mới chỉ một lần."""
    chunks = [np.ones(100, dtype=np.float32)] * 1000
    out = join_audio_chunks(chunks, 1000, silence_ps=[0.01] * 999)
    assert len(out) == 1000 * 100 + 999 * 10


def test_khoang_nghi_v3_chi_chen_phan_con_thieu():
    """silence_ps là TỔNG khoảng nghỉ tối thiểu: im lặng sẵn ở đuôi/đầu chunk được tính."""
    sr = 1000
    speech = np.full(100, 0.5, dtype=np.float32)
    quiet_tail = np.concatenate([speech, np.zeros(200, dtype=np.float32)])   # đuôi im 0,2 s
    out = join_audio_chunks([quiet_tail, speech], sr, silence_ps=[0.5])
    assert len(out) == 300 + 300 + 100          # chỉ bù 0,3 s
    out = join_audio_chunks([quiet_tail, speech], sr, silence_ps=[0.1])
    assert len(out) == 300 + 100                # đuôi đã dài hơn: không chèn
    assert pause_pad_samples(speech, speech, sr, 0.5) == 500


@pytest.mark.parametrize("seed", range(6))
def test_khoang_nghi_v3_khop_tung_khe(seed):
    rng = np.random.default_rng(seed)
    chunks = _chunks(rng, int(rng.integers(2, 30)))
    gaps = [float(rng.choice([0.0, 0.01, 0.03])) for _ in range(len(chunks) - 1)]
    out = join_audio_chunks([c.copy() for c in chunks], 1000, silence_ps=gaps)
    pads = [pause_pad_samples(chunks[i], chunks[i + 1], 1000, g) for i, g in enumerate(gaps)]
    assert len(out) == sum(len(c) for c in chunks) + sum(pads)
