"""
Phụ đề SRT cho audio TTS - mốc thời gian đo từ audio THẬT, không ước lượng.

Cách làm: chia văn bản thành các "đơn vị đọc" (câu, gộp câu quá ngắn), caller
đọc từng đơn vị riêng rồi đo độ dài. Engine vốn cũng sinh từng chunk độc lập rồi
ghép lại, nên đọc theo câu không đổi chất lượng; gộp câu ngắn (< ``MIN_UNIT_CHARS``)
theo đúng lý do engine gộp: chunk 1-2 từ đứng riêng làm model AR dễ ảo giác.

Phụ đề hiện VĂN BẢN GỐC của người dùng ("KTX", không phải "ký túc xá" của từ điển
phát âm) và bỏ thẻ cảm xúc. Câu dài được chia thành nhiều cue (thời gian chia theo
số ký tự trong câu đó) để mỗi cue tối đa 2 dòng dễ đọc trên video.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vieneu_utils.core_utils import V3_GAP_SILENCE, split_into_sentences
from vieneu_utils.pause_tags import split_pauses

MIN_UNIT_CHARS = 20
LINE_CHARS = 42          # chuẩn phụ đề phổ biến: ~42 ký tự/dòng
CUE_MAX_CHARS = 2 * LINE_CHARS

# Thẻ ngoặc vuông của app, token cảm xúc VieNeu, thẻ <laugh>/<breath>/<sigh> của Supertonic.
_EMOTION_TAG = re.compile(r"\[[^\]]*\]|<\|emotion_\d+\|>|<(?:laugh|breath|sigh)>", re.IGNORECASE)
_NEWLINES = re.compile(r"[\r\n]+")
_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:…])")
# Chỗ ngắt cue ưu tiên: sau dấu câu phụ.
_SOFT_BREAK = re.compile(r"(?<=[,;:])\s+")
# Kết câu không cần khoảng trắng theo sau: Nhật/Trung (。！？) và Hindi (।) — giọng
# Kokoro. split_into_sentences chỉ nhận dấu câu Latin, nên cả đoạn thành một cue.
# Dấu đóng ngoặc/ngoặc kép đi SAU dấu kết câu vẫn thuộc câu đó: 「…。」 mà cắt ngay
# sau 。 thì 」 đứng trơ trọi thành một câu riêng. Tối đa 2 dấu đóng liền nhau.
CLOSING_MARKS = "」』）)\"'”’》】"
_STOP = "[。！？।]"
_CLOSE = "[" + re.escape(CLOSING_MARKS) + "]"
NON_LATIN_STOP_PATTERN = "|".join(
    rf"(?<={_STOP}{_CLOSE * n})(?!{_CLOSE})\s*" for n in range(3))
_NON_LATIN_STOP = re.compile(NON_LATIN_STOP_PATTERN)
# Chữ Hán/kana: một ký tự ~ một từ, nên tính gấp đôi khi so với MIN_UNIT_CHARS.
_CJK_CHAR = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
# Sau dấu câu Nhật/Trung không có khoảng trắng; gộp câu cũng không được chèn.
_CJK_PUNCT_END = ("。", "！", "？", "、", "，")


@dataclass
class Unit:
    """Một lần gọi TTS. ``pause_after`` = giây nghỉ sau đơn vị.

    ``tag_pause`` False: ngắt câu/đoạn tự nhiên, ``pause_after`` là TỔNG khoảng nghỉ
    tối thiểu (im lặng sẵn ở hai mép audio được tính vào, xem
    ``core_utils.pause_pad_samples``). True: thẻ nghỉ, chèn đúng ``pause_after`` giây.
    """
    text: str
    pause_after: float
    tag_pause: bool = False


@dataclass
class Cue:
    start: float
    end: float
    text: str


def display_text(text: str) -> str:
    """Chữ hiện trên phụ đề: bỏ thẻ cảm xúc / thẻ lạ, gộp khoảng trắng."""
    text = _SPACES.sub(" ", _EMOTION_TAG.sub(" ", text)).strip()
    return _SPACE_BEFORE_PUNCT.sub(r"\1", text)  # "giấy tờ [cười]." -> "giấy tờ."


def _effective_len(text: str) -> int:
    shown = display_text(text)
    return len(shown) + len(_CJK_CHAR.findall(shown))


def _join(a: str, b: str) -> str:
    return f"{a}{b}" if a.rstrip(CLOSING_MARKS).endswith(_CJK_PUNCT_END) else f"{a} {b}"


def build_units(text: str) -> list[Unit]:
    """Chia văn bản (có thể chứa thẻ ``[nghỉ Ns]``) thành các đơn vị đọc."""
    units: list[Unit] = []
    for seg, pause in split_pauses(text):
        seg_units: list[Unit] = []
        paragraphs = [p for p in _NEWLINES.split(seg) if p.strip()]
        for para in paragraphs:
            sentences = [
                s for piece in _NON_LATIN_STOP.split(para) if piece.strip()
                for s in (split_into_sentences(piece) or [piece.strip()])
            ] or [para.strip()]
            for i, sentence in enumerate(sentences):
                gap = V3_GAP_SILENCE["para"] if i == len(sentences) - 1 else V3_GAP_SILENCE["sentence"]
                prev = seg_units[-1] if seg_units else None
                # Gộp vào đơn vị trước nếu đơn vị trước còn quá ngắn.
                if prev is not None and _effective_len(prev.text) < MIN_UNIT_CHARS:
                    prev.text = _join(prev.text, sentence)
                    prev.pause_after = gap
                else:
                    seg_units.append(Unit(sentence, gap))
        # Đơn vị cuối quá ngắn thì gộp ngược vào đơn vị trước (cùng đoạn thẻ nghỉ).
        if len(seg_units) > 1 and _effective_len(seg_units[-1].text) < MIN_UNIT_CHARS:
            last = seg_units.pop()
            seg_units[-1].text = _join(seg_units[-1].text, last.text)
            seg_units[-1].pause_after = last.pause_after
        if seg_units:
            seg_units[-1].pause_after = pause  # hết đoạn: nghỉ đúng số giây của thẻ
            seg_units[-1].tag_pause = True
            units.extend(seg_units)
        elif units:
            units[-1].pause_after += pause     # thẻ nghỉ không có chữ đi trước
            units[-1].tag_pause = True
        elif pause > 0:
            units.append(Unit("", pause, tag_pause=True))  # thẻ nghỉ ở đầu văn bản: im lặng trước câu đầu
    # Đơn vị cuối nhận pause của đoạn cuối: 0 nếu văn bản không kết thúc bằng thẻ nghỉ.
    return units


def _wrap(text: str) -> str:
    """Tối đa 2 dòng, ngắt ở ranh giới từ gần giữa nhất."""
    if len(text) <= LINE_CHARS:
        return text
    mid = len(text) // 2
    left = text.rfind(" ", 0, mid + 1)
    right = text.find(" ", mid)
    candidates = [i for i in (left, right) if i > 0]
    if not candidates:
        return text
    cut = min(candidates, key=lambda i: abs(i - mid))
    return f"{text[:cut].strip()}\n{text[cut:].strip()}"


def _split_long(text: str) -> list[str]:
    """Chia câu dài thành các phần <= CUE_MAX_CHARS: ưu tiên sau dấu phẩy, rồi theo từ."""
    if len(text) <= CUE_MAX_CHARS:
        return [text]
    pieces: list[str] = []
    buf = ""
    for part in _SOFT_BREAK.split(text):
        for word in [part] if len(part) <= CUE_MAX_CHARS else part.split(" "):
            cand = f"{buf} {word}".strip()
            if buf and len(cand) > CUE_MAX_CHARS:
                pieces.append(buf)
                buf = word
            else:
                buf = cand
    if buf:
        pieces.append(buf)
    return pieces


def unit_cues(text: str, start: float, end: float) -> list[Cue]:
    """Cue cho một đơn vị đọc kéo dài [start, end]; câu dài chia theo tỉ lệ số ký tự."""
    shown = display_text(text)
    if not shown:
        return []
    pieces = _split_long(shown)
    total = sum(len(p) for p in pieces)
    cues, t = [], start
    for p in pieces:
        dur = (end - start) * len(p) / total
        cues.append(Cue(t, t + dur, _wrap(p)))
        t += dur
    cues[-1].end = end
    return cues


def _ts(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [f"{i}\n{_ts(c.start)} --> {_ts(c.end)}\n{c.text}\n" for i, c in enumerate(cues, 1)]
    return "\n".join(blocks)
