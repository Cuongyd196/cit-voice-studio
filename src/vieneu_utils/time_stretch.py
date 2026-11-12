"""
Đổi tốc độ đọc mà giữ cao độ, bằng WSOLA (Waveform Similarity Overlap-Add).

Trước đây dùng ``librosa.effects.time_stretch`` (phase vocoder): nó ghép lại pha
của từng dải tần, với giọng nói nghe rè/kim loại, càng nhanh càng rè (người dùng
báo, 2026-10). WSOLA cắt-ghép các đoạn sóng THẬT của audio gốc, mỗi đoạn được dời
trong một khoảng nhỏ cho khớp sóng với đoạn trước, nên giọng giữ tự nhiên ở
1,2–1,5 lần. Chỉ cần numpy: không kéo librosa/torch vào đường CPU.
"""

from __future__ import annotations

import numpy as np

FRAME_MS = 30.0      # độ dài khung: đủ chứa vài chu kỳ cao độ giọng nói
TOLERANCE_MS = 12.0  # khoảng dời tối đa để tìm chỗ khớp sóng
SEARCH_RATE = 12000  # tìm chỗ khớp trên tín hiệu thưa hơn rồi chỉnh lại cho nhanh


def _best_offset(region: np.ndarray, target: np.ndarray, step: int) -> int:
    """Vị trí trong ``region`` mà khung dài ``len(target)`` giống ``target`` nhất."""
    coarse = np.correlate(region[::step], target[::step], mode="valid")
    best = int(np.argmax(coarse)) * step
    if step == 1:
        return best
    lo = max(0, best - step)
    hi = min(len(region) - len(target), best + step)
    fine = np.correlate(region[lo:hi + len(target)], target, mode="valid")
    return lo + int(np.argmax(fine))


def time_stretch(audio: np.ndarray, rate: float, sr: int) -> np.ndarray:
    """Đọc nhanh ``rate`` lần (``rate`` < 1 là chậm lại); độ dài ra ≈ ``len / rate``."""
    x = np.asarray(audio, dtype=np.float32)
    if abs(rate - 1.0) < 0.02 or len(x) == 0:
        return x
    n = max(64, int(sr * FRAME_MS / 1000)) & ~1
    hop = n // 2
    tol = max(1, int(sr * TOLERANCE_MS / 1000))
    step = max(1, sr // SEARCH_RATE)
    # Cửa sổ Hann tuần hoàn: chồng 50% thì tổng hai cửa sổ đúng bằng 1.
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)).astype(np.float32)

    out_len = int(round(len(x) / rate))
    frames = out_len // hop + 1
    pad = tol + hop
    xp = np.concatenate([np.zeros(pad, np.float32), x,
                         np.zeros(2 * n + tol + int(np.ceil(hop * rate)), np.float32)])
    y = np.zeros(frames * hop + n, dtype=np.float32)

    prev = pad
    for k in range(frames):
        nominal = pad + int(round(k * hop * rate))
        if k == 0:
            pos = nominal
        else:
            # Đoạn "nối tự nhiên" của khung trước: khung mới phải giống nó nhất.
            target = xp[prev + hop: prev + hop + n]
            lo = max(0, nominal - tol)
            hi = min(len(xp) - n, nominal + tol)
            pos = lo + _best_offset(xp[lo:hi + n], target, step)
        y[k * hop: k * hop + n] += xp[pos: pos + n] * win
        prev = pos
    return y[:out_len]
