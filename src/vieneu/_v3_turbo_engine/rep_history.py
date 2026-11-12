"""Sliding-window repetition-penalty history, shared by every v3 Turbo path.

Lý do cửa sổ trượt thay vì set tích lũy: codebook chỉ có 1024 code/kênh, nên
sau vài trăm frame một set không giới hạn đã phạt gần nửa codebook — kể cả các
code hợp lệ phải lặp lại (khoảng lặng, nguyên âm kéo dài) — làm giọng trôi dần
về cuối chunk dài. Mục tiêu thật của penalty là bẻ loop CỤC BỘ, nên chỉ các
code xuất hiện trong ``window`` frame gần nhất mới bị phạt.

Mỗi kênh (codebook) nhận đúng 1 code mỗi frame, nên ``window`` tính bằng frame
cũng là số code tối đa được giữ lại mỗi kênh. ``window <= 0`` giữ hành vi cũ
(phạt vĩnh viễn, không giới hạn).
"""
from __future__ import annotations

from collections import Counter, deque

# ~2.5 s audio ở 25 frame/s: đủ dài để tóm mọi loop cục bộ, đủ ngắn để một
# nguyên âm/khoảng lặng đã kết thúc không còn bị phạt oan.
DEFAULT_REP_WINDOW = 64


class _ChannelWindow:
    """History một codebook. Bề ngoài giống ``set`` (iter/len/bool/add) nên các
    hàm sampling hiện có dùng được nguyên vẹn; bên trong là cửa sổ trượt."""

    __slots__ = ("_seen", "_order", "_window")

    def __init__(self, window: int):
        self._seen: Counter = Counter()   # code -> số lần trong cửa sổ
        self._order: deque = deque()      # code theo thứ tự sinh, để trục xuất FIFO
        self._window = int(window)

    def add(self, code: int) -> None:
        self._seen[code] += 1
        if self._window > 0:
            self._order.append(code)
            if len(self._order) > self._window:
                old = self._order.popleft()
                if self._seen[old] <= 1:
                    del self._seen[old]
                else:
                    self._seen[old] -= 1

    def __iter__(self):
        return iter(self._seen)

    def __len__(self) -> int:
        return len(self._seen)

    def __bool__(self) -> bool:
        return bool(self._seen)


class RepetitionHistory:
    """Per-codebook sliding-window history: ``hist[ch]`` là view của kênh ``ch``.

    Drop-in cho ``[set() for _ in range(n_vq)]`` ở mọi call-site cũ.
    """

    __slots__ = ("channels",)

    def __init__(self, n_channels: int, window: int = DEFAULT_REP_WINDOW):
        self.channels = [_ChannelWindow(window) for _ in range(n_channels)]

    def __getitem__(self, ch: int) -> _ChannelWindow:
        return self.channels[ch]

    def __len__(self) -> int:
        return len(self.channels)
