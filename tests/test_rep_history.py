"""Tests cho sliding-window repetition-penalty history (v3 Turbo)."""
import numpy as np
import pytest

from vieneu._v3_turbo_engine.rep_history import DEFAULT_REP_WINDOW, RepetitionHistory


def test_fifo_eviction():
    h = RepetitionHistory(2, window=4)
    for c in [10, 11, 12, 13]:
        h[0].add(c)
    assert set(h[0]) == {10, 11, 12, 13}
    h[0].add(14)  # đẩy 10 ra khỏi cửa sổ
    assert set(h[0]) == {11, 12, 13, 14}
    # kênh khác độc lập
    assert len(h[1]) == 0


def test_duplicate_counting():
    # Code lặp nhiều lần chỉ hết bị phạt khi MỌI bản sao đã ra khỏi cửa sổ.
    h = RepetitionHistory(1, window=3)
    h[0].add(7); h[0].add(7); h[0].add(8)
    h[0].add(9)   # đẩy bản 7 đầu tiên; 7 vẫn còn một bản trong cửa sổ
    assert set(h[0]) == {7, 8, 9}
    h[0].add(1)   # đẩy nốt bản 7 thứ hai
    assert set(h[0]) == {8, 9, 1}


def test_window_zero_is_unbounded():
    h = RepetitionHistory(1, window=0)
    for c in range(200):
        h[0].add(c)
    assert len(h[0]) == 200


def test_bounded_after_long_generation():
    # Chunk dài: số code bị phạt mỗi kênh không vượt quá window (thay vì ~45% codebook).
    rng = np.random.default_rng(0)
    h = RepetitionHistory(1, window=DEFAULT_REP_WINDOW)
    for _ in range(600):
        h[0].add(int(rng.integers(0, 1024)))
    assert len(h[0]) <= DEFAULT_REP_WINDOW


def test_setlike_interface_for_samplers():
    # Các hàm sampling dùng: truthiness, len(), iteration (sorted / np.fromiter).
    h = RepetitionHistory(1, window=8)
    assert not h[0]
    h[0].add(5); h[0].add(3)
    assert h[0]
    assert sorted(h[0]) == [3, 5]
    idx = np.fromiter(h[0], dtype=np.int64, count=len(h[0]))
    assert sorted(idx.tolist()) == [3, 5]


def test_sample_token_respects_window():
    # Không dùng importorskip("torch"): test_base_utils gán sys.modules["torch"]
    # = MagicMock() (rò rỉ sang cả session) nên importorskip vẫn "thấy" torch trên
    # CI torch-free. Dọn mock đó rồi import thật — thiếu torch thì skip.
    import sys as _sys
    from unittest.mock import MagicMock as _MM
    for _k in [k for k in _sys.modules if (k == "torch" or k.startswith("torch.")) and isinstance(_sys.modules[k], _MM)]:
        del _sys.modules[_k]
    try:
        import torch
        from vieneu._v3_turbo_engine.modeling_v3_turbo import _sample_token
    except (ImportError, ModuleNotFoundError):
        pytest.skip("PyTorch not available")

    torch.manual_seed(0)
    logits = torch.randn(1024)
    top_id = int(logits.argmax())
    n = 1500

    def hit_rate(prev):
        return sum(
            int(_sample_token(logits, temperature=0.8, top_k=25, top_p=0.95,
                              repetition_penalty=1.2, prev_tokens=prev).item()) == top_id
            for _ in range(n)
        ) / n

    baseline = hit_rate(None)
    h = RepetitionHistory(1, window=8)
    h[0].add(top_id)
    in_window = hit_rate(h[0])
    for c in range(100, 108):  # 8 code khác đẩy top_id ra khỏi cửa sổ
        h[0].add(c)
    assert top_id not in set(h[0])
    evicted = hit_rate(h[0])

    assert in_window < baseline * 0.75      # trong cửa sổ: bị phạt rõ rệt
    assert abs(evicted - baseline) < 0.05   # ra khỏi cửa sổ: hết bị phạt
