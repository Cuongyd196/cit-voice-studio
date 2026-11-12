"""
Đọc file phụ đề SRT (và WebVTT đơn giản) để lồng tiếng theo mốc thời gian.

Chịu được các kiểu file hay gặp: có BOM, xuống dòng CRLF, mốc dùng ``,`` hoặc ``.``,
thiếu số thứ tự, câu nhiều dòng, thẻ định dạng ``<i>``/``<font>`` và ``{\\an8}``.
Cue trả về đã sắp theo mốc bắt đầu; cue không còn chữ sau khi bỏ thẻ bị bỏ qua.
"""

from __future__ import annotations

import re

from vieneu_utils.subtitles import Cue

_TIME = r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[,.](\d{1,3})"
_TIMING = re.compile(rf"^\s*{_TIME}\s*-->\s*{_TIME}")
_HTML_TAG = re.compile(r"<[^>]*>")
_ASS_TAG = re.compile(r"\{[^}]*\}")
_MUSIC = re.compile(r"[♪♫]")
_SPACES = re.compile(r"\s+")
_BLOCK_SPLIT = re.compile(r"\n\s*\n")


class SrtError(ValueError):
    """File không có cue hợp lệ nào."""


def _seconds(h, m, s, ms) -> float:
    # "5" là 500 ms, "05" là 50 ms: mốc luôn là phần lẻ của giây.
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def clean_text(text: str) -> str:
    """Chữ để đọc/hiện: bỏ thẻ định dạng và ký hiệu nhạc, gộp các dòng thành một."""
    text = _MUSIC.sub(" ", _ASS_TAG.sub(" ", _HTML_TAG.sub(" ", text)))
    return _SPACES.sub(" ", text).strip()


def parse_srt(content: str) -> list[Cue]:
    content = content.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in _BLOCK_SPLIT.split(content):
        lines = block.strip("\n").split("\n")
        for i, line in enumerate(lines):
            m = _TIMING.match(line)
            if m:
                start = _seconds(*m.groups()[:4])
                end = _seconds(*m.groups()[4:])
                text = clean_text(" ".join(lines[i + 1:]))
                if text:
                    cues.append(Cue(start, max(start, end), text))
                break
    if not cues:
        raise SrtError("File phụ đề không đúng định dạng SRT hoặc không có câu thoại nào.")
    cues.sort(key=lambda c: c.start)
    return cues
