"""Đổi tốc độ bằng WSOLA: đúng độ dài, giữ cao độ, không méo biên độ."""
import numpy as np
import pytest

from vieneu_utils.time_stretch import time_stretch

SR = 48000


def _tone(freq=220.0, seconds=2.0):
    t = np.arange(int(SR * seconds)) / SR
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _pitch(x):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.argmax(spec) * SR / len(x)


@pytest.mark.parametrize("rate", [0.8, 1.25, 1.5])
def test_dung_do_dai_va_giu_cao_do(rate):
    x = _tone()
    y = time_stretch(x, rate, SR)
    assert len(y) == round(len(x) / rate)
    assert y.dtype == np.float32
    mid = y[len(y) // 4: 3 * len(y) // 4]
    assert _pitch(mid) == pytest.approx(220.0, abs=3.0)
    # Biên độ giữ nguyên (cửa sổ chồng 50% cộng đúng bằng 1, sóng ghép khớp pha).
    assert np.max(np.abs(mid)) == pytest.approx(0.5, abs=0.03)


def test_toc_do_1_tra_nguyen_va_rong():
    x = _tone(seconds=0.5)
    assert time_stretch(x, 1.0, SR) is not None and np.array_equal(time_stretch(x, 1.0, SR), x)
    assert len(time_stretch(np.zeros(0, np.float32), 1.5, SR)) == 0


def test_audio_rat_ngan():
    y = time_stretch(_tone(seconds=0.01), 1.5, SR)
    assert len(y) == round(480 / 1.5)
