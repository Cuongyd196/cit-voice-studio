"""Sinh build/DIEU-KHOAN.txt (UTF-8 có BOM) từ DIEU-KHOAN.md cho trang điều khoản của
trình cài Inno Setup - Inno hiện file .txt nguyên văn nên bỏ ký hiệu markdown.

DIEU-KHOAN.md ngắt dòng bằng tay (~88 ký tự). Khung điều khoản của Inno hẹp hơn và tự
xuống dòng, nên giữ các chỗ ngắt đó làm mỗi câu gãy làm hai, lởm chởm. Vì vậy mỗi
đoạn / mỗi gạch đầu dòng được nối lại thành một dòng, để khung tự xuống dòng theo bề rộng.

Dùng: python make_terms_txt.py   (make_installer.bat tự gọi)
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # gốc repo (script nằm trong scripts/)
_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s+")


def _unwrap(text: str) -> str:
    """Nối các dòng bị ngắt tay trong cùng đoạn / gạch đầu dòng; giữ dòng trống,
    tiêu đề và đầu mỗi gạch đầu dòng."""
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        starts_block = (
            not stripped
            or stripped.startswith("#")
            or _ITEM.match(line)
            or not out
            or not out[-1].strip()
            or out[-1].lstrip().startswith("#")
        )
        if starts_block:
            out.append(line.rstrip())
        else:
            out[-1] = f"{out[-1].rstrip()} {stripped}"
    return "\n".join(out)


def write(out: Path = ROOT / "build" / "DIEU-KHOAN.txt") -> Path:
    text = (ROOT / "DIEU-KHOAN.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    text = _unwrap(text)
    # Tiêu đề mục (##) viết hoa cho dễ nhận ra trong file chữ thường; giữ tên văn bản (#).
    text = re.sub(r"^##+\s*(.+)$", lambda m: m.group(1).upper(), text, flags=re.M)
    text = re.sub(r"^#\s*", "", text, flags=re.M)
    text = re.sub(r"^- ", "• ", text, flags=re.M)
    text = text.replace("**", "").replace("`", "")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text.replace("\n", "\r\n"), encoding="utf-8-sig", newline="")
    return out


if __name__ == "__main__":
    print(f"[+] {write()}")
