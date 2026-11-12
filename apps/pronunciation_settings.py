"""Lưu từ điển phát âm của người dùng và cung cấp API chỉnh sửa cho giao diện.

File nằm ở ``%LOCALAPPDATA%/CitVoiceStudio/pronunciation-dict.json`` (cùng chỗ với
``server-settings.json``) để giữ nguyên qua các lần cài lại/nâng cấp app. Người
dùng sửa tay file này cũng được: app đọc lại khi thời điểm sửa file thay đổi, không
cần khởi động lại.
"""
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vieneu_utils.pronunciation import (
    DEFAULT_ENTRIES,
    MAX_ENTRIES,
    PronunciationDict,
    validate_entries,
)


def dict_path() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "pronunciation-dict.json"


_lock = threading.Lock()
# (đường dẫn, mtime) của lần nạp gần nhất; None = chưa nạp. mtime None = chưa có file.
_cache_key: tuple | None = None
_cache: PronunciationDict = PronunciationDict(validate_entries(DEFAULT_ENTRIES))


def _read_file(path: Path) -> PronunciationDict:
    """Đọc file từ điển. File hỏng thì dùng bộ mặc định và KHÔNG ghi đè file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data["entries"] if isinstance(data, dict) else data
        return PronunciationDict(validate_entries(raw))
    except FileNotFoundError:
        return PronunciationDict(validate_entries(DEFAULT_ENTRIES))
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"⚠️ Từ điển phát âm lỗi ({path}): {e} - tạm dùng bộ mặc định.")
        return PronunciationDict(validate_entries(DEFAULT_ENTRIES))


def current_dict() -> PronunciationDict:
    """Từ điển đang dùng; tự nạp lại khi file bị sửa từ bên ngoài."""
    global _cache_key, _cache
    path = dict_path()
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        key = (str(path), None)
    with _lock:
        if key != _cache_key:
            _cache = _read_file(path)
            _cache_key = key
        return _cache


def apply(text: str) -> str:
    """Thay các từ trong ``text`` theo từ điển đang dùng."""
    return current_dict().apply(text)


def save_entries(raw: list) -> PronunciationDict:
    """Validate rồi ghi nguyên tử (file tạm + os.replace). Lỗi dữ liệu -> ValueError."""
    global _cache_key, _cache
    entries = validate_entries(raw)
    path = dict_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "entries": [
            {"word": e.word, "reading": e.reading, "match_case": e.match_case}
            for e in entries
        ],
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as f:
            temporary = Path(f.name)
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    with _lock:
        _cache = PronunciationDict(entries)
        _cache_key = (str(path), path.stat().st_mtime_ns)
    return _cache


def _as_json(d: PronunciationDict) -> list:
    return [{"word": e.word, "reading": e.reading, "match_case": e.match_case} for e in d.entries]


router = APIRouter()


class EntryModel(BaseModel):
    word: str = Field(max_length=200)
    reading: str = Field(max_length=500)
    match_case: bool = True


class EntriesReq(BaseModel):
    entries: List[EntryModel] = Field(max_length=MAX_ENTRIES)


class PreviewReq(BaseModel):
    text: str = Field(max_length=5000)
    # Bản nháp chưa lưu trên giao diện; bỏ trống thì dùng từ điển đang lưu.
    entries: List[EntryModel] | None = Field(default=None, max_length=MAX_ENTRIES)


@router.get("/api/pronunciations", tags=["Pronunciation"])
def get_pronunciations():
    """Từ điển phát âm hiện tại + bộ mặc định (cho nút khôi phục)."""
    return {
        "entries": _as_json(current_dict()),
        "defaults": DEFAULT_ENTRIES,
        "path": str(dict_path()),
    }


@router.put("/api/pronunciations", tags=["Pronunciation"])
def put_pronunciations(req: EntriesReq):
    """Lưu toàn bộ từ điển phát âm (thay thế danh sách cũ)."""
    try:
        d = save_entries([e.model_dump() for e in req.entries])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail="Không lưu được từ điển phát âm. Hãy kiểm tra quyền ghi cấu hình.",
        ) from e
    return {"entries": _as_json(d), "path": str(dict_path())}


@router.post("/api/pronunciations/preview", tags=["Pronunciation"])
def preview_pronunciations(req: PreviewReq):
    """Xem trước văn bản sau khi thay theo từ điển (chưa lưu cũng thử được)."""
    if req.entries is None:
        d = current_dict()
    else:
        try:
            d = PronunciationDict(validate_entries([e.model_dump() for e in req.entries]))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"text": d.apply(req.text)}
