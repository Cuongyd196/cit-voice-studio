"""
Thẻ nghỉ ``[nghỉ 2s]`` - chèn khoảng lặng có độ dài chính xác giữa hai đoạn đọc.

Không đưa thẻ vào model: khoảng nghỉ dài nhất pipeline tự tạo là ngắt đoạn 0,7s
(xem ``V3_GAP_SILENCE`` trong core_utils), và normalizer còn đọc thành tiếng thẻ
lạ trong ngoặc vuông ("[nghỉ 2s]" -> "nghỉ hai giây"). Thay vào đó, caller tách
văn bản tại thẻ, đọc từng đoạn như bình thường rồi chèn đúng số giây im lặng.

Cú pháp (không phân biệt hoa/thường, có dấu hay không dấu):
    [nghỉ 2s]  [nghỉ 1.5s]  [nghỉ 1,5 giây]  [nghỉ 500ms]  [pause 2s]  [nghỉ]
Không ghi đơn vị -> giây; ``[nghỉ]`` trống -> ``DEFAULT_PAUSE_S``. Thẻ viết sai
(``[nghỉ abc]``) bị bỏ đi (nghỉ 0s) để không bị đọc thành tiếng.
"""

from __future__ import annotations

import re

DEFAULT_PAUSE_S = 1.0
# Trần cho MỖI thẻ: gõ nhầm "[nghỉ 200s]" không được tạo ra vài phút im lặng.
MAX_PAUSE_S = 10.0

_TAG_RE = re.compile(r"\[\s*(?:nghỉ|nghi|pause)(?![^\W\d_])([^\]]*)\]", re.IGNORECASE)
_ARG_RE = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*(ms|s|giây|giay|sec|seconds?)?\s*$", re.IGNORECASE
)


def parse_pause(arg: str) -> float:
    """Phần sau chữ "nghỉ" trong thẻ -> số giây (đã chặn trần). Sai cú pháp -> 0."""
    if not arg.strip():
        return DEFAULT_PAUSE_S
    m = _ARG_RE.match(arg)
    if not m:
        return 0.0
    value = float(m.group(1).replace(",", "."))
    if (m.group(2) or "").lower() == "ms":
        value /= 1000.0
    return min(max(value, 0.0), MAX_PAUSE_S)


def has_pause_tags(text: str) -> bool:
    return bool(text) and _TAG_RE.search(text) is not None


def split_pauses(text: str) -> list[tuple[str, float]]:
    """Tách ``text`` thành ``[(đoạn, giây_nghỉ_sau_đoạn), ...]``.

    Đoạn có thể rỗng (thẻ nằm đầu văn bản, hoặc hai thẻ liền nhau - khi đó số giây
    được cộng dồn vào cùng một khoảng nghỉ). Không có thẻ -> ``[(text, 0.0)]``.
    """
    out: list[tuple[str, float]] = []
    pos = 0
    for m in _TAG_RE.finditer(text):
        seg = text[pos:m.start()].strip()
        pause = parse_pause(m.group(1))
        if not seg and out:
            prev_seg, prev_pause = out[-1]
            out[-1] = (prev_seg, prev_pause + pause)
        else:
            out.append((seg, pause))
        pos = m.end()
    tail = text[pos:].strip()
    if tail or not out:
        out.append((tail, 0.0))
    return out
