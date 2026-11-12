"""Đóng gói bản source để người dùng tải về, giải nén và bấm run_desktop_app.bat là chạy.

    python make_source_zip.py

Kết quả: dist/CIT-Voice-Studio-source.zip

Loại bỏ những thứ KHÔNG được phép đi theo bản phát hành:
  - `.venv` / `.xpu_venv`: venv do uv tạo dùng trampoline trỏ cứng vào đường dẫn
    interpreter của máy build. Copy sang máy khác sẽ lỗi "uv trampoline failed to
    spawn Python child process". Người dùng phải để run_desktop_app.bat tự tạo venv mới.
  - `dist/`, `build/`: sản phẩm build, vừa nặng vừa vô dụng với bản source.
  - `node_modules`: cài lại bằng npm khi cần.
  - `.env`: có thể chứa token riêng.
Giữ lại `app-desktop/cit-voice-app/dist` (giao diện React đã build) để run_stream.bat
và desktop_app.py chạy được ngay mà không cần Node.js.
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # gốc repo (script nằm trong scripts/)
TOP = "CIT-Voice-Studio"

# Tên thư mục bị loại ở bất kỳ cấp nào
SKIP_DIR_NAMES = {
    ".git", ".venv", ".xpu_venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".husky",
    "outputs", "merged_models_cache", ".idea", ".vscode",
}
# Đường dẫn bị loại, tính từ gốc repo (không đụng app-desktop/cit-voice-app/dist)
# CLAUDE.md: ghi chú nội bộ; gpu_venv/: GPU tự cài (vài GB); addons/: bộ tách âm Kokoro
# tự cài (có espeak-ng GPL, không được phát hành kèm); public/: bản clone repo công khai.
SKIP_ROOT_PATHS = {"dist", "build", "wheels", "models", "gpu_venv", "addons", "public"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".spec", ".zip", ".log"}
# chan-doan.txt: báo cáo chẩn đoán của máy đang build.
SKIP_NAMES = {".env", "CIT-Voice-Studio.spec", "CLAUDE.md", "chan-doan.txt"}

HUONG_DAN = """CIT VOICE STUDIO - HUONG DAN SU DUNG
====================================================================

YEU CAU: Windows 10/11 + ket noi Internet (chi can cho lan chay dau).
Khong can cai Python, khong can cai Node.js.

CACH CHAY
--------------------------------------------------------------------
1. Giai nen TOAN BO thu muc nay ra o dia (vi du: D:\\CIT-Voice-Studio).
   KHONG chay truc tiep tu ben trong file .zip.

2. Bam dup vao file:  run_desktop_app.bat

3. Lan chay dau se lau (5-15 phut) vi may phai tai ve:
   - Cong cu uv va Python 3.12
   - Cac thu vien can thiet
   - Mo hinh giong noi (vai tram MB)
   Cac lan sau chi mat vai giay.

4. Ung dung mo trong cua so rieng (hoac trinh duyet, xem LOI THUONG GAP).

DUNG UNG DUNG
--------------------------------------------------------------------
Bam dup vao:  stop.bat

CAC FILE CHAY KHAC
--------------------------------------------------------------------
run_desktop_app.bat Ung dung Desktop (cua so rieng)
run_stream.bat      Chi chay may chu, mo bang trinh duyet - cong 8001
run_gpu.bat         Ban GPU - CHI danh cho may co card NVIDIA
stop.bat            Dong tat ca tien trinh dang chay

MAY CO CARD NVIDIA
--------------------------------------------------------------------
Ban mac dinh chay tren CPU va da nhanh gap ~2 lan thoi gian thuc, nen
PHAN LON NGUOI DUNG KHONG CAN BAN GPU.

Chi dung run_gpu.bat khi ban doc kich ban dai / lam podcast nhieu luot:
ban GPU gop ca kich ban vao mot lan xu ly nen nhanh hon han o che do do.

Luu y truoc khi chay run_gpu.bat:
  - Lan cai dau phai tai khoang 3.5 GB (thu vien torch CUDA).
  - Can con trong it nhat 12 GB o dia.
  - Can driver NVIDIA moi. Script se tu kiem tra va hoi truoc khi tai.
  - May khong co card NVIDIA thi dung run_desktop_app.bat.

LOI THUONG GAP
--------------------------------------------------------------------
* Windows bao chan file .bat vi tai tu Internet:
  Chuot phai vao file .zip TRUOC KHI giai nen > Properties > tich Unblock > OK.

* Bao "uv sync that bai":
  Kiem tra ket noi mang, tat tam VPN/proxy roi chay lai.

* Bao loi "DLL load failed while importing onnxruntime_pybind11_state":
  May thieu Microsoft Visual C++ Redistributable. Tai va cai ban x64
  (mien phi, cua Microsoft) roi chay lai:
  https://aka.ms/vs/17/release/vc_redist.x64.exe
  Ban dong goi .exe khong dinh loi nay vi no tu mang san cac file do.

* Ung dung mo bang TRINH DUYET thay vi cua so rieng:
  Khong phai loi. May thieu Microsoft Edge WebView2 Runtime nen ung dung tu
  chuyen sang trinh duyet. Moi tinh nang van dung duoc binh thuong.
  Muon co cua so rieng thi cai WebView2 Runtime (mien phi, cua Microsoft):
  https://go.microsoft.com/fwlink/p/?LinkId=2124703

* Cua so mo ra nhung TRANG TRON:
  Da sua tu ban nay. Nguyen nhan la registry Windows bi phan mem khac ghi sai
  kieu file (.js thanh "text/plain"), khien trinh duyet tu choi chay ma giao
  dien. Ung dung gio tu ep lai kieu dung luc khoi dong.

* Bao cong dang bi chiem:
  Chay stop.bat truoc, roi chay lai run_desktop_app.bat.

====================================================================
Tac gia: Cuong IT (https://me.cuongit.net)
Phat trien dua tren VieNeu-TTS (Pham Nguyen Ngoc Bao) - Apache 2.0
"""


def bundled_model_files() -> set:
    """Đường dẫn (tương đối ROOT) các file mô hình kèm sẵn - cùng danh sách với
    copy_release_models.py. Không kèm cả models/hf_cache: cache máy dev có thể chứa
    mô hình khác (Kokoro, fp32...) và blobs trùng lặp."""
    import copy_release_models as crm

    pairs, refs, missing = crm.plan_copy(crm.SOURCE_HUB, crm.SOURCE_HUB)
    if missing:
        raise SystemExit("LOI: cache mo hinh thieu file: " + ", ".join(missing)
                         + ". Chay truoc: python fetch_models.py")
    files = {src.relative_to(ROOT).as_posix() for src, _ in pairs}
    files |= {(crm.repo_dir(crm.SOURCE_HUB, repo) / "refs" / "main").relative_to(ROOT).as_posix()
              for repo in refs}
    return files


def skipped(rel: Path, with_models: bool, model_files: frozenset = frozenset()) -> bool:
    parts = rel.parts
    if any(p in SKIP_DIR_NAMES for p in parts):
        return True
    if any(p.endswith(".egg-info") for p in parts):
        return True
    posix = rel.as_posix()
    if with_models and posix.startswith("models/hf_cache/"):
        return posix not in model_files   # chỉ mô hình kèm sẵn
    if any(posix == s or posix.startswith(s + "/") for s in SKIP_ROOT_PATHS):
        return True
    return rel.name in SKIP_NAMES or rel.suffix.lower() in SKIP_SUFFIXES


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-models", action="store_true",
                    help="kèm models/hf_cache (~312 MB) để chạy được ngay, không cần tải")
    args = ap.parse_args()

    if args.with_models and not (ROOT / "models" / "hf_cache").exists():
        print("LOI: chua co models/hf_cache. Chay truoc: python fetch_models.py")
        return 1

    suffix = "-source-with-models" if args.with_models else "-source"
    out = ROOT / "dist" / f"{TOP}{suffix}.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    model_files = frozenset(bundled_model_files()) if args.with_models else frozenset()
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if skipped(rel, args.with_models, model_files):
                continue
            zf.write(path, f"{TOP}/{rel.as_posix()}")
            count += 1
        note = HUONG_DAN
        if args.with_models:
            note = note.replace(
                "3. Lan chay dau se lau (5-15 phut) vi may phai tai ve:\n"
                "   - Cong cu uv va Python 3.12\n"
                "   - Cac thu vien can thiet\n"
                "   - Mo hinh giong noi (vai tram MB)\n"
                "   Cac lan sau chi mat vai giay.",
                "3. Ban nay DA KEM SAN MO HINH GIONG NOI, khong phai tai ve nua.\n"
                "   Lan chay dau chi tai cong cu uv, Python 3.12 va cac thu vien\n"
                "   (vai phut). Cac lan sau chi mat vai giay.")
        zf.writestr(f"{TOP}/HUONG-DAN.txt", note.replace("\n", "\r\n"))
        count += 1

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"OK: {out}")
    print(f"    {count} file, {size_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
