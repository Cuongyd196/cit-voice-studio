"""Chép vào bản đóng gói ĐÚNG các file của mô hình kèm sẵn (VieNeu-TTS v3 Turbo int8
+ codec MOSS), theo danh sách trong apps/model_catalog.py.

Trước đây build_desktop_exe.bat dùng robocopy chép cả thư mục models/ trừ vài thư
mục đã biết, nên thứ gì khác nằm trong cache của máy dev cũng lọt vào bản phát
hành: bản 1.0.1 suýt mang theo ~650 MB mô hình Kokoro của nhánh khác. Chép theo
danh sách thì chỉ những file app cần mới vào, kể cả không bao giờ lọt giọng nhân
bản (custom_voices_*.json, giọng người thật) của máy dev.

Cách dùng (build_desktop_exe.bat gọi):
    python copy_release_models.py dist/CIT-Voice-Studio/models

Chép ra bố cục cache của huggingface_hub (refs/main + snapshots/<sha>/...), bỏ
blobs: đọc offline chỉ cần file trong snapshot. shutil.copy2 đi theo symlink nên
máy có Developer Mode (snapshot là symlink tới blobs) vẫn ra file thật.
Thoát mã 1 nếu cache thiếu file - chạy `python fetch_models.py` trước.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # gốc repo (script nằm trong scripts/)
sys.path.insert(0, str(ROOT))

from apps.model_catalog import BUNDLED_MODEL_ID, get  # noqa: E402

SOURCE_HUB = ROOT / "models" / "hf_cache" / "hub"


def repo_dir(hub: Path, repo: str) -> Path:
    return hub / ("models--" + repo.replace("/", "--"))


def pinned_revision(repo_path: Path):
    """sha của bản mô hình trong cache: ``refs/main`` nếu có, không thì snapshot duy
    nhất (fetch_models.py dọn revision cũ). Cache tải theo mã commit trên máy build
    sạch từng không có refs/main (fetch_models.py nay ghi thêm)."""
    ref = repo_path / "refs" / "main"
    if ref.is_file():
        return ref.read_text(encoding="utf-8").strip()
    snaps = [d.name for d in (repo_path / "snapshots").glob("*") if d.is_dir()]
    return snaps[0] if len(snaps) == 1 else None


def plan_copy(source_hub: Path, dest_hub: Path):
    """([(nguồn, đích)], {repo: sha}, [file thiếu])."""
    spec = get(BUNDLED_MODEL_ID)
    pairs, refs, missing = [], {}, []
    for source in spec.sources:
        if source.patterns:
            raise SystemExit(f"{BUNDLED_MODEL_ID}: nguồn {source.repo} dùng mẫu glob, không chép theo danh sách được.")
        sha = pinned_revision(repo_dir(source_hub, source.repo))
        if sha is None:
            missing.append(f"{source.repo} (chưa tải, hoặc có nhiều bản trong cache)")
            continue
        refs[source.repo] = sha
        for rel in source.allow_patterns:
            src = repo_dir(source_hub, source.repo) / "snapshots" / sha / rel
            if src.is_file():
                pairs.append((src, repo_dir(dest_hub, source.repo) / "snapshots" / sha / rel))
            else:
                missing.append(f"{source.repo}/{rel}")
    return pairs, refs, missing


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Cách dùng: python copy_release_models.py <thư mục models đích>")
        return 2
    dest = Path(argv[1])
    dest_hub = dest / "hf_cache" / "hub"
    pairs, refs, missing = plan_copy(SOURCE_HUB, dest_hub)
    if missing:
        print("[ERROR] Cache mô hình thiếu file:")
        for m in missing:
            print("    -", m)
        print('        Chạy "python fetch_models.py" rồi build lại.')
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    for repo, sha in refs.items():
        ref = repo_dir(dest_hub, repo) / "refs" / "main"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(sha, encoding="utf-8")
    total = 0
    for src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        total += dst.stat().st_size
    print(f"    Đã chép {len(pairs)} file của {BUNDLED_MODEL_ID} ({total / 1024 / 1024:.0f} MB).")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
