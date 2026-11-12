"""Lịch sử tạo giọng lưu trên ổ đĩa, giữ nguyên sau khi tắt/mở ứng dụng.

Vì sao không lưu ở trình duyệt: bản desktop chạy PyWebView, mà ``webview.start()``
mặc định ``private_mode=True`` - localStorage/IndexedDB bị xoá mỗi lần tắt app.

Bố cục: ``%LOCALAPPDATA%/CitVoiceStudio/history/``
    index.json        danh sách mục (mới nhất trước), ghi nguyên tử
    <tên>.wav|.mp3    audio, tên dạng "2026-09-24_20-14-12_Minh Đức_3f2a1b2c"
    <tên>.srt         phụ đề (nếu có)
(mục lưu trước khi có tên dễ đọc thì <tên> là id)

KHÔNG tự xoá: bài đã tạo là thành quả của người dùng. Trước đây app lặng lẽ xoá bài
cũ nhất khi vượt 300 bài / 1 GB - mà WAV 48 kHz ~330 MB/giờ, nên 3 bài dài 1 giờ đã
đầy, và một bài > 1 GB (~3 giờ) bị xoá ngay sau khi tạo xong. Giờ tab Lịch sử hiện
số bài + dung lượng + thư mục (``GET /api/history/info``) và nhắc người dùng tự dọn
khi vượt ``WARN_BYTES`` hoặc ổ đĩa còn dưới ``LOW_DISK_BYTES``.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

WARN_BYTES = 5 * 1024 ** 3      # lịch sử lớn hơn: nhắc dọn
LOW_DISK_BYTES = 2 * 1024 ** 3  # ổ đĩa còn trống ít hơn: nhắc dọn
MAX_UPLOAD_BYTES = 300 * 1024 * 1024
MAX_TEXT_CHARS = 200_000

_ID_RE = re.compile(r"^[0-9a-f]{32}$")  # chặn path traversal: id chỉ là uuid hex
_AUDIO_EXT = {"wav": ".wav", "mp3": ".mp3"}
_MODES = {"tts", "clone", "conversation", "pdf", "batch"}
# Ky tu cam trong ten file Windows (va ky tu dieu khien).
_BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_lock = threading.Lock()


def history_dir() -> Path:
    return Path(os.getenv("LOCALAPPDATA") or Path.home()) / "CitVoiceStudio" / "history"


def _index_path() -> Path:
    return history_dir() / "index.json"


def _load() -> list:
    try:
        data = json.loads(_index_path().read_text(encoding="utf-8"))
        return [e for e in data.get("entries", []) if isinstance(e, dict) and _ID_RE.match(str(e.get("id", "")))]
    except FileNotFoundError:
        return []
    except (OSError, ValueError, AttributeError) as e:
        # Index hỏng: KHÔNG ghi đè (còn cứu tay được); bắt đầu danh sách rỗng.
        print(f"⚠️ Lịch sử lỗi ({_index_path()}): {e}")
        return []


def _save(entries: list) -> None:
    d = history_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=d, delete=False, suffix=".tmp") as f:
            tmp = Path(f.name)
            json.dump({"version": 1, "entries": entries}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, _index_path())
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def _stem(entry: dict) -> str:
    """Ten goc cua file tren dia. Muc cu (truoc khi co truong "file") dung id.

    "file" doc tu index.json: gia tri co dang duong dan (sua tay / hong) thi bo qua.
    """
    name = entry.get("file")
    if not name or _BAD_NAME_CHARS.search(name) or name.startswith("."):
        return entry["id"]
    return name


def _friendly_stem(entry: dict) -> str:
    """Ten de doc khi mo thu muc: "2026-09-24_20-14-12_Minh Đức_3f2a1b2c".

    Kem 8 ky tu dau cua id de khong trung khi tao hai ban cung giay.
    """
    stamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(entry["timestamp"] / 1000))
    voice = _BAD_NAME_CHARS.sub("", entry.get("voice_name") or "").strip()[:40] or "voice"
    return f"{stamp}_{voice}_{entry['id'][:8]}"


def _files_of(entry: dict) -> list:
    d = history_dir()
    out = [d / f"{_stem(entry)}{_AUDIO_EXT.get(entry.get('format'), '.wav')}"]
    if entry.get("has_subtitles"):
        out.append(d / f"{_stem(entry)}.srt")
    return out


def _remove_files(entry: dict) -> None:
    for p in _files_of(entry):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass  # file đang bị khoá: để lại rác nhỏ còn hơn làm hỏng thao tác xoá


def _public(entry: dict) -> dict:
    e = dict(entry)
    e["audio_url"] = f"/api/history/{entry['id']}/audio"
    if entry.get("has_subtitles"):
        e["subtitles_url"] = f"/api/history/{entry['id']}/subtitles.srt"
    return e


def _get(entry_id: str) -> dict:
    if not _ID_RE.match(entry_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy bản đã tạo này.")
    for e in _load():
        if e["id"] == entry_id:
            return e
    raise HTTPException(status_code=404, detail="Không tìm thấy bản đã tạo này.")


router = APIRouter(tags=["History"])


@router.get("/api/history")
def list_history():
    """Toàn bộ lịch sử, mới nhất trước (không kèm audio - lấy qua ``audio_url``)."""
    with _lock:
        return {"entries": [_public(e) for e in _load()]}


@router.get("/api/history/info")
def history_info():
    """Số bài, dung lượng, thư mục và dung lượng ổ còn trống - cho dòng ghi chú ở
    tab Lịch sử. ``warn``: nên nhắc người dùng dọn bớt."""
    import shutil

    with _lock:
        entries = _load()
    d = history_dir()
    total = sum(int(e.get("size", 0)) for e in entries)
    try:
        free = shutil.disk_usage(d if d.exists() else d.parent if d.parent.exists() else Path.home()).free
    except OSError:
        free = None
    return {
        "count": len(entries),
        "bytes": total,
        "folder": str(d),
        "disk_free": free,
        "warn": total > WARN_BYTES or (free is not None and free < LOW_DISK_BYTES),
    }


@router.post("/api/history/open-folder")
def open_history_folder():
    """Mở thư mục lịch sử trong trình quản lý file (trên máy chạy server)."""
    d = history_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(d)  # noqa: S606 - thư mục của chính app
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(d)])
        else:
            subprocess.Popen(["xdg-open", str(d)])
    except OSError as e:
        raise HTTPException(status_code=500, detail="Không mở được thư mục bản đã tạo.") from e
    return {"status": "ok", "path": str(d)}


@router.post("/api/history")
async def add_history(
    audio: UploadFile = File(...),
    text: str = Form(...),
    voice_id: str = Form(""),
    voice_name: str = Form(""),
    duration_seconds: float = Form(0.0),
    format: str = Form("wav"),
    mode: str = Form("tts"),
    subtitles: Optional[str] = Form(None),
):
    """Lưu một bản audio vừa tạo (kèm phụ đề SRT nếu có) vào lịch sử."""
    fmt = format.lower()
    if fmt not in _AUDIO_EXT:
        raise HTTPException(status_code=400, detail="Định dạng audio phải là wav hoặc mp3.")
    data = await audio.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="File audio rỗng.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File audio quá lớn để lưu vào Bản đã tạo.")

    entry = _new_entry(text, voice_id, voice_name, duration_seconds, fmt, mode, subtitles, len(data))
    return _store(entry, lambda target: target.write_bytes(data), subtitles)


def _new_entry(text, voice_id, voice_name, duration_seconds, fmt, mode, subtitles, size) -> dict:
    entry = {
        "id": uuid.uuid4().hex,
        "text": text[:MAX_TEXT_CHARS],
        "voice_id": voice_id[:200],
        "voice_name": voice_name[:200],
        "duration_seconds": max(0.0, float(duration_seconds)),
        "format": fmt,
        "mode": mode if mode in _MODES else "tts",
        "timestamp": int(time.time() * 1000),
        "size": int(size),
        "has_subtitles": bool(subtitles and subtitles.strip()),
    }
    entry["file"] = _friendly_stem(entry)
    return entry


def _store(entry: dict, write_audio, subtitles: Optional[str]) -> dict:
    """Ghi audio (qua ``write_audio(đường_dẫn)``) + phụ đề, thêm vào index."""
    with _lock:
        d = history_dir()
        d.mkdir(parents=True, exist_ok=True)
        try:
            write_audio(d / f"{entry['file']}{_AUDIO_EXT[entry['format']]}")
            if entry["has_subtitles"]:
                # write_bytes: write_text trên Windows tự đổi \n -> \r\n.
                srt = subtitles.encode("utf-8")
                (d / f"{entry['file']}.srt").write_bytes(srt)
                entry["size"] += len(srt)
            _save([entry] + _load())
        except OSError as e:
            _remove_files(entry)
            raise HTTPException(status_code=500, detail="Không lưu được bản đã tạo. Hãy kiểm tra dung lượng ổ đĩa.") from e
    return _public(entry)


_TEMP_PREFIX = ".tmp-"


def new_temp_path(suffix: str = ".wav") -> Path:
    """File tạm NẰM TRONG thư mục lịch sử, để ``add_file`` chỉ cần đổi tên (cùng ổ
    đĩa) thay vì chép lại cả trăm MB. Dọn luôn file tạm cũ quá 1 ngày (app tắt
    giữa chừng)."""
    d = history_dir()
    d.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - 86400
    for old in d.glob(f"{_TEMP_PREFIX}*"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    return d / f"{_TEMP_PREFIX}{uuid.uuid4().hex}{suffix}"


def add_file(src: Path, *, text: str, voice_id: str = "", voice_name: str = "",
             duration_seconds: float = 0.0, fmt: str = "wav", mode: str = "tts",
             subtitles: Optional[str] = None) -> dict:
    """Như ``POST /api/history`` nhưng nhận file audio đã có trên đĩa (backend vừa
    tạo) và CHUYỂN nó vào lịch sử - không đọc vào RAM, không giới hạn 300 MB."""
    src = Path(src)
    entry = _new_entry(text, voice_id, voice_name, duration_seconds, fmt, mode, subtitles,
                       src.stat().st_size)
    return _store(entry, lambda target: os.replace(src, target), subtitles)


def _audio_path(entry_id: str) -> tuple:
    with _lock:
        entry = _get(entry_id)
    path = _files_of(entry)[0]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File audio của mục này đã bị xoá.")
    return entry, path


def wav_file_to_mp3(src, dst) -> bool:
    """Chuyển WAV -> MP3 theo từng đoạn 30 giây (RAM không phụ thuộc độ dài bài).
    False nếu bản libsndfile không có bộ mã MP3."""
    import soundfile as sf

    from apps import ai_label

    try:
        with sf.SoundFile(str(src)) as fin, sf.SoundFile(
            str(dst), "w", samplerate=fin.samplerate, channels=fin.channels, format="MP3"
        ) as fout:
            ai_label.label(fout)   # thẻ ID3 "tạo bởi AI" - phải đặt trước khi ghi
            for block in fin.blocks(blocksize=fin.samplerate * 30, dtype="float32"):
                fout.write(block)
        return True
    except Exception:
        Path(dst).unlink(missing_ok=True)
        return False


def export_audio(entry_id: str, dest, fmt: str = "wav") -> Path:
    """Ghi audio của mục lịch sử ra ``dest`` (nút Tải WAV/MP3 của bản desktop):
    chép thẳng, hoặc chuyển sang MP3 theo từng đoạn - không qua trình duyệt."""
    import shutil

    entry, path = _audio_path(entry_id)
    dest = Path(dest)
    if fmt == "mp3" and entry.get("format") != "mp3":
        if wav_file_to_mp3(path, dest):
            return dest
        dest = dest.with_suffix(".wav")   # bản libsndfile không có MP3: trả WAV
    shutil.copyfile(path, dest)
    return dest


def _download_headers(entry: dict, fmt: str) -> dict:
    from urllib.parse import quote

    name = f"{_stem(entry)}.{fmt}"
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"}


@router.get("/api/history/{entry_id}/audio")
def history_audio(entry_id: str, download: bool = False):
    entry, path = _audio_path(entry_id)
    fmt = "mp3" if entry.get("format") == "mp3" else "wav"
    media = "audio/mpeg" if fmt == "mp3" else "audio/wav"
    headers = _download_headers(entry, fmt) if download else None
    return FileResponse(path, media_type=media, headers=headers)


@router.get("/api/history/{entry_id}/mp3")
def history_mp3(entry_id: str):
    """Tải về dạng MP3 (bản chạy trên trình duyệt; bản desktop dùng ``export_audio``)."""
    from starlette.background import BackgroundTask

    entry, path = _audio_path(entry_id)
    if entry.get("format") == "mp3":
        return FileResponse(path, media_type="audio/mpeg", headers=_download_headers(entry, "mp3"))
    tmp = new_temp_path(".mp3")
    try:
        out = export_audio(entry_id, tmp, "mp3")
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    fmt = out.suffix.lstrip(".")
    return FileResponse(out, media_type="audio/mpeg" if fmt == "mp3" else "audio/wav",
                        headers=_download_headers(entry, fmt),
                        background=BackgroundTask(lambda: out.unlink(missing_ok=True)))


@router.get("/api/history/{entry_id}/subtitles.srt")
def history_subtitles(entry_id: str):
    with _lock:
        entry = _get(entry_id)
    path = history_dir() / f"{_stem(entry)}.srt"
    if not entry.get("has_subtitles") or not path.exists():
        raise HTTPException(status_code=404, detail="Mục này không có phụ đề.")
    return FileResponse(path, media_type="application/x-subrip; charset=utf-8")


def _reveal(path: Path) -> None:
    """Mo trinh quan ly file tai thu muc chua `path`, chon san file do (Windows)."""
    if sys.platform == "win32":
        # Explorer chi hieu dung dang: /select,"duong dan" (duong dan co the co dau
        # cach). Duong dan Windows khong the chua dau ".
        subprocess.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent)])


@router.post("/api/history/{entry_id}/reveal")
def reveal_history(entry_id: str):
    """Mở thư mục lịch sử trên máy chạy server, chọn sẵn file audio của mục này."""
    with _lock:
        entry = _get(entry_id)
    path = _files_of(entry)[0]
    if not path.exists():
        raise HTTPException(status_code=404, detail="File audio của mục này đã bị xoá.")
    try:
        _reveal(path)
    except OSError as e:
        raise HTTPException(status_code=500, detail="Không mở được thư mục chứa file.") from e
    return {"status": "ok", "path": str(path)}


@router.delete("/api/history/{entry_id}")
def delete_history(entry_id: str):
    with _lock:
        entry = _get(entry_id)
        _save([e for e in _load() if e["id"] != entry_id])
        _remove_files(entry)
    return {"status": "ok"}


@router.delete("/api/history")
def clear_history():
    with _lock:
        entries = _load()
        _save([])
        for e in entries:
            _remove_files(e)
    return {"status": "ok", "deleted": len(entries)}
