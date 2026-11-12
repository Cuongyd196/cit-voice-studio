"""
Trích văn bản từ file Word .docx - chỉ dùng thư viện chuẩn (zipfile + ElementTree).

.docx là file zip chứa XML; nội dung chính nằm ở ``word/document.xml``. Không
dùng python-docx để khỏi thêm dependency (và khỏi phải khai báo thêm cho
PyInstaller - thiếu là bản .exe hỏng lúc import trên máy người dùng).

Giữ đúng ranh giới ĐOẠN VĂN của Word: mỗi đoạn một dòng, các đoạn cách nhau một
dòng trống. Pipeline TTS tách đoạn theo xuống dòng, nên đây chính là lợi thế so
với PDF (PDF ngắt dòng theo khổ trang, gây chỗ nghỉ lạ giữa câu).

Lấy: đoạn văn, chữ trong hyperlink / tracked insert / content control, bảng (mỗi
hàng một dòng, các ô nối bằng ", "). Bỏ: chữ đã xoá (tracked delete), text box,
header/footer, chú thích - những phần thường không được đọc thành tiếng.
"""

from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_EP = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"

# Chặn file zip "bom": document.xml giải nén ra tối đa chừng này byte.
MAX_XML_BYTES = 64 * 1024 * 1024

# Nhánh không đọc thành tiếng: text box / hình vẽ nằm lồng trong run, chữ đã xoá.
_SKIP = {f"{_W}txbxContent", f"{_W}del", f"{_W}delText", f"{_W}instrText",
         f"{_W}footnoteReference", f"{_W}endnoteReference"}


class DocxError(ValueError):
    """File không phải .docx hợp lệ - thông báo tiếng Việt, hiển thị thẳng cho người dùng."""


def _read_member(zf: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_XML_BYTES:
        raise DocxError("Tài liệu quá lớn để trích xuất.")
    return zf.read(info)


def _run_text(node: ET.Element, out: list[str]) -> None:
    """Gom chữ của một đoạn theo đúng thứ tự tài liệu, bỏ các nhánh trong _SKIP."""
    for child in node:
        tag = child.tag
        if tag in _SKIP:
            continue
        if tag == f"{_W}t":
            out.append(child.text or "")
        elif tag == f"{_W}tab":
            out.append(" ")
        elif tag in (f"{_W}br", f"{_W}cr"):
            out.append("\n")
        elif tag == f"{_W}noBreakHyphen":
            out.append("-")
        else:
            _run_text(child, out)


def _paragraph(p: ET.Element) -> str:
    parts: list[str] = []
    _run_text(p, parts)
    lines = ("".join(parts)).split("\n")
    return "\n".join(" ".join(line.split()) for line in lines).strip()


def _table(tbl: ET.Element) -> list[str]:
    rows: list[str] = []
    # Chỉ hàng/ô con TRỰC TIẾP (không dùng iter): bảng lồng trong ô đã được
    # _blocks(tc) lấy rồi, iter sẽ lấy lần hai.
    for tr in tbl.findall(f"{_W}tr"):
        cells = []
        for tc in tr.findall(f"{_W}tc"):
            text = " ".join(" ".join(_blocks(tc)).split())
            if text:
                cells.append(text)
        if cells:
            rows.append(", ".join(cells))
    return rows


def _blocks(container: ET.Element) -> list[str]:
    """Các khối văn bản (đoạn / hàng bảng) của body, ô bảng hay content control."""
    out: list[str] = []
    for child in container:
        if child.tag == f"{_W}p":
            text = _paragraph(child)
            if text:
                out.append(text)
        elif child.tag == f"{_W}tbl":
            out.extend(_table(child))
        elif child.tag == f"{_W}sdt":
            content = child.find(f"{_W}sdtContent")
            if content is not None:
                out.extend(_blocks(content))
    return out


def _page_count(zf: zipfile.ZipFile) -> int:
    """Số trang Word ghi lại lúc lưu (docProps/app.xml); 0 nếu không có."""
    try:
        raw = _read_member(zf, "docProps/app.xml")
        pages = ET.fromstring(raw).find(f"{_EP}Pages") if raw else None
        return int(pages.text) if pages is not None and pages.text else 0
    except (ET.ParseError, ValueError, DocxError):
        return 0


def extract_docx(data: bytes) -> tuple[str, int]:
    """Trả ``(văn bản, số trang)``. File hỏng / không phải docx -> ``DocxError``."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise DocxError(
            "File không phải định dạng .docx hợp lệ (có thể bị hỏng hoặc được đổi đuôi)."
        ) from e
    with zf:
        raw = _read_member(zf, "word/document.xml")
        if raw is None:
            raise DocxError("File .docx không có nội dung văn bản (thiếu word/document.xml).")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            raise DocxError(f"Nội dung file .docx bị hỏng: {e}") from e
        body = root.find(f"{_W}body")
        blocks = _blocks(body) if body is not None else []
        return "\n\n".join(blocks), _page_count(zf)
