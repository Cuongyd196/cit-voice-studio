"""
Khớp giọng đọc vào mốc thời gian của phụ đề (lồng tiếng theo SRT).

Mỗi câu được đọc ở tốc độ người dùng chọn. Câu dài hơn khung của nó thì tăng tốc cho
vừa, tối đa ``MAX_FIT_RATE`` lần; vẫn dài thì lấn sang khoảng lặng phía sau, chạm câu
kế tiếp thì đẩy câu đó lùi lại. Không bao giờ cắt chữ: cắt thì mất nội dung, còn lệch
vài trăm mili giây thì người xem gần như không nhận ra.

Chỉ tính toán, không đụng engine, để kiểm thử độc lập.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vieneu_utils.subtitles import Cue

MAX_FIT_RATE = 1.5
# Khoảng nghỉ tối thiểu giữa hai câu khi câu trước tràn sang câu sau.
MIN_GAP_SECONDS = 0.05
# Lệch dưới ngưỡng này không tính là "bị đẩy lùi" (sai số làm tròn mẫu).
PUSH_EPSILON = 0.005


def fit_rate(audio_seconds: float, slot_seconds: float, max_rate: float = MAX_FIT_RATE) -> float:
    """Hệ số tăng tốc để ``audio_seconds`` vừa khung ``slot_seconds`` (1.0 nếu đã vừa)."""
    if audio_seconds <= 0 or audio_seconds <= slot_seconds:
        return 1.0
    if slot_seconds <= 0:
        return max_rate
    return min(max_rate, audio_seconds / slot_seconds)


def place(cue_start: float, cursor: float, has_prev: bool) -> float:
    """Mốc bắt đầu thực tế: đúng mốc phụ đề, trừ khi câu trước còn đang đọc."""
    if not has_prev:
        return max(cue_start, cursor)
    return max(cue_start, cursor + MIN_GAP_SECONDS)


@dataclass
class DubStats:
    cues: int = 0
    sped_up: int = 0
    pushed: int = 0
    max_push_seconds: float = 0.0
    placed: list[Cue] = field(default_factory=list)

    def record(self, original: Cue, start: float, audio_seconds: float, rate: float) -> None:
        self.cues += 1
        if rate > 1.0:
            self.sped_up += 1
        push = start - original.start
        if push > PUSH_EPSILON:
            self.pushed += 1
            self.max_push_seconds = max(self.max_push_seconds, push)
        # Phụ đề đã chỉnh: hiện ít nhất bằng thời lượng gốc, và đủ dài cho câu đọc.
        end = start + max(audio_seconds, original.end - original.start)
        self.placed.append(Cue(start, end, original.text))

    def finish(self) -> list[Cue]:
        """Phụ đề đã chỉnh mốc; cue không đè lên cue kế tiếp."""
        for cur, nxt in zip(self.placed, self.placed[1:]):
            cur.end = min(cur.end, nxt.start)
        return self.placed
