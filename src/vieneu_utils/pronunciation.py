"""
Từ điển phát âm do người dùng tự định nghĩa (thay thế ở tầng CHỮ).

Normalizer của sea-g2p coi chữ viết tắt IN HOA là tiếng Anh và đánh vần từng chữ
cái kiểu Anh ("AI" -> ``<en>a i</en>`` -> "ÊI AI"). Viết sẵn cách đọc bằng chữ
Việt ("ây ai") thì normalizer để nguyên và model đọc đúng giọng Việt, nên chỉ cần
thay từ -> cách đọc TRƯỚC khi text vào pipeline. Không dùng ``phoneme_dict`` của
sea-g2p vì nó đòi nhập IPA - người dùng thường không tự viết được.

Quy tắc khớp:
- Chỉ khớp NGUYÊN TỪ: "AI" không đụng tới "OpenAI" hay "AIDS".
- Mặc định phân biệt hoa/thường: "AI" không đụng tới đại từ "ai". Mục nào đặt
  ``match_case=False`` thì khớp mọi kiểu viết hoa.
- Từ dài được thử trước từ ngắn ("API" thắng "AI" dù thứ tự nhập thế nào).
- Không đụng vào thẻ cảm xúc ``[cười]`` / ``<|emotion_k|>``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Mapping

# Thẻ cảm xúc - phải giữ nguyên nguyên văn để phonemize_text nhận ra (xem
# _EMOTION_SPLIT_RE trong phonemize_text.py).
_PROTECTED_RE = re.compile(r"(\[[^\]]+\]|<\|emotion_\d+\|>)")

MAX_WORD_LEN = 64
MAX_READING_LEN = 200
MAX_ENTRIES = 2000

# Bộ mặc định khi người dùng chưa lưu từ điển nào - cũng là ví dụ trên giao diện.
# Chỉ gồm viết tắt mà normalizer KHÔNG biết nên đánh vần từng chữ cái ("KTX" ->
# "ca tê ích"). Viết tắt phổ biến (CLB, THPT, HLV...) normalizer
# đã tự đọc đúng, không cần thêm.
DEFAULT_ENTRIES: list[dict] = [
    {"word": "KTX", "reading": "ký túc xá", "match_case": True},
    {"word": "SGK", "reading": "sách giáo khoa", "match_case": True},
]


@dataclass(frozen=True)
class PronunciationEntry:
    word: str
    reading: str
    match_case: bool = True


def validate_entries(raw: Iterable[Mapping]) -> list[PronunciationEntry]:
    """Kiểm tra + chuẩn hoá danh sách mục từ. Lỗi thì ném ``ValueError`` (tiếng Việt)."""
    entries: list[PronunciationEntry] = []
    exact: set[str] = set()        # từ phân biệt hoa/thường, giữ nguyên
    insensitive: set[str] = set()  # từ không phân biệt, dạng chữ thường
    all_folded: set[str] = set()   # mọi từ, dạng chữ thường
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"Mục {i} không hợp lệ.")
        word = str(item.get("word") or "").strip()
        reading = " ".join(str(item.get("reading") or "").split())
        match_case = item.get("match_case", True)
        if not isinstance(match_case, bool):
            raise ValueError(f"Mục {i}: 'match_case' phải là true/false.")
        if not word:
            raise ValueError(f"Mục {i}: từ cần thay không được để trống.")
        if not reading:
            raise ValueError(f"Mục {i} ('{word}'): cách đọc không được để trống.")
        if len(word) > MAX_WORD_LEN:
            raise ValueError(f"Mục {i}: từ dài quá {MAX_WORD_LEN} ký tự.")
        if len(reading) > MAX_READING_LEN:
            raise ValueError(f"Mục {i} ('{word}'): cách đọc dài quá {MAX_READING_LEN} ký tự.")
        if _PROTECTED_RE.search(word):
            raise ValueError(f"Mục {i}: không được thay thẻ cảm xúc '{word}'.")
        # Hai mục trùng nhau khi cùng khớp được một chuỗi: so theo chữ thường nếu
        # một trong hai không phân biệt hoa/thường.
        folded = word.lower()
        clash = (
            (word in exact or folded in insensitive)
            if match_case
            else folded in all_folded
        )
        if clash:
            raise ValueError(f"Từ '{word}' bị khai báo trùng.")
        (exact if match_case else insensitive).add(word if match_case else folded)
        all_folded.add(folded)
        entries.append(PronunciationEntry(word, reading, match_case))
    if len(entries) > MAX_ENTRIES:
        raise ValueError(f"Từ điển tối đa {MAX_ENTRIES} mục.")
    return entries


class PronunciationDict:
    """Bộ thay thế đã biên dịch sẵn: một regex duy nhất cho mọi mục từ."""

    def __init__(self, entries: Iterable[PronunciationEntry]):
        self.entries = list(entries)
        self._exact = {e.word: e.reading for e in self.entries if e.match_case}
        self._folded = {e.word.lower(): e.reading for e in self.entries if not e.match_case}
        if not self.entries:
            self._re = None
            return
        # Dài trước ngắn: alternation của regex lấy nhánh khớp ĐẦU TIÊN.
        ordered = sorted(self.entries, key=lambda e: len(e.word), reverse=True)
        alts = [
            re.escape(e.word) if e.match_case else f"(?i:{re.escape(e.word)})"
            for e in ordered
        ]
        # Ranh giới "nguyên từ" theo \w Unicode (có dấu tiếng Việt), không dùng \b
        # vì \b không hoạt động khi từ bắt đầu/kết thúc bằng ký tự như "." ("A.I.").
        self._re = re.compile(r"(?<!\w)(?:" + "|".join(alts) + r")(?!\w)")

    def _reading_for(self, m: re.Match) -> str:
        s = m.group(0)
        if s in self._exact:
            return self._exact[s]
        return self._folded.get(s.lower(), s)

    def apply(self, text: str) -> str:
        if not text or self._re is None:
            return text
        parts = _PROTECTED_RE.split(text)
        for i in range(0, len(parts), 2):  # chỉ số lẻ là thẻ cảm xúc - bỏ qua
            parts[i] = self._re.sub(self._reading_for, parts[i])
        return "".join(parts)


def apply_pronunciations(text: str, entries: Iterable[Mapping]) -> str:
    """Tiện ích một lần: validate ``entries`` rồi thay trong ``text``."""
    return PronunciationDict(validate_entries(entries)).apply(text)
