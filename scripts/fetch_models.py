"""Tải sẵn mô hình vào `models/hf_cache` để đóng gói kèm bản phát hành.

    python fetch_models.py              # đường CPU/ONNX int8 (mặc định)
    python fetch_models.py --fp32       # thêm bản fp32 (chất lượng tối đa, nặng hơn)
    python fetch_models.py --check      # chỉ kiểm tra, không tải

Vì sao cần: lần chạy đầu ứng dụng phải tải ~286 MB từ HuggingFace. Với người dùng
phổ thông đó là 5-15 phút im lặng, và là điểm chết nếu HuggingFace bị chặn, quá tải,
hoặc repo bị đổi tên. Tải sẵn rồi gói kèm thì bỏ hẳn được rủi ro đó.

Danh sách file bám theo `_GRAPH_FILES` / `_CODEC_FILES` trong
`src/vieneu/_v3_turbo_engine/onnx_runtime_lite.py`. Sửa bên đó thì sửa cả ở đây.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Console Windows mặc định là cp1252 — in tiếng Việt có dấu sẽ ném
# UnicodeEncodeError và giết cả script. Các entry point trong apps/ đều đã xử lý
# như thế này.
if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

ROOT = Path(__file__).resolve().parents[1]  # gốc repo (script nằm trong scripts/)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.runtime_paths import setup_hf_home  # noqa: E402  (phải chạy trước huggingface_hub)

# Danh sách file và repo lấy từ apps/model_catalog.py — nguồn sự thật duy nhất,
# dùng chung với trình tải lúc chạy trong apps/model_downloader.py.
from apps.model_catalog import (  # noqa: E402
    V3_REPO, CODEC_REPO, GRAPH_FILES, CODEC_FILES, ROOT_FILES,
)


def human(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp32", action="store_true", help="tải thêm bản fp32 (onnx_update)")
    ap.add_argument("--check", action="store_true", help="chỉ báo cáo, không tải")
    args = ap.parse_args()

    cache = setup_hf_home()
    print(f"HF_HOME = {cache}")

    if args.check:
        total = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file())
        print(f"Cache hiện có: {human(total)}")
        return 0

    from huggingface_hub import HfApi, hf_hub_download

    # GHIM REVISION. Không ghim thì mỗi lần chạy có thể rơi vào một revision khác,
    # và cache kết thúc với nhiều snapshot mà KHÔNG snapshot nào đủ file: lúc đóng
    # gói offline, Voice Cloning chết vì `speaker_encoder.onnx` nằm ở revision cũ
    # còn `refs/main` lại trỏ sang revision mới. Máy Windows không bật Developer
    # Mode còn không tạo được symlink nên mỗi snapshot là một bản copy đầy đủ —
    # vừa thiếu file vừa nhân đôi dung lượng.
    api = HfApi()
    revisions: dict[str, str] = {}
    for repo in (V3_REPO, CODEC_REPO):
        revisions[repo] = api.model_info(repo).sha
        print(f"Ghim {repo} @ {revisions[repo][:12]}")

    jobs: list[tuple[str, str, str | None]] = []
    for fn in ROOT_FILES:
        jobs.append((V3_REPO, fn, None))
    for fn in GRAPH_FILES:
        jobs.append((V3_REPO, fn, "onnx_int8"))
    if args.fp32:
        for fn in GRAPH_FILES:
            jobs.append((V3_REPO, fn, "onnx_update"))
    for fn in CODEC_FILES:
        jobs.append((CODEC_REPO, fn, None))

    failed: list[str] = []
    for i, (repo, fn, sub) in enumerate(jobs, 1):
        label = f"{repo}/{sub + '/' if sub else ''}{fn}"
        try:
            p = hf_hub_download(repo, fn, repo_type="model", subfolder=sub,
                                revision=revisions[repo])
            print(f"[{i}/{len(jobs)}] OK   {label}  ({human(Path(p).stat().st_size)})")
        except Exception as e:
            print(f"[{i}/{len(jobs)}] MISS {label}  -> {e}")
            failed.append(label)

    prune_old_revisions(revisions)
    pin_main_refs(revisions)

    total = sum(f.stat().st_size for f in cache.rglob("*") if f.is_file())
    print(f"\nTổng cache: {human(total)} tại {cache}")
    if failed:
        print(f"Không tải được {len(failed)} file:")
        for f in failed:
            print(f"  - {f}")
        print("Các file này sẽ được tải lúc chạy nếu thật sự cần.")
    return 0


def pin_main_refs(revisions: dict[str, str]) -> None:
    """Ghi ``refs/main`` = revision vừa ghim cho mỗi repo.

    Tải theo mã commit (``revision=<sha>``) thì huggingface_hub KHÔNG ghi refs/main,
    mà app đọc offline bằng ``hf_hub_download(..., local_files_only=True)`` với
    revision mặc định "main" - thiếu refs/main là không thấy file, phải lên mạng.
    Máy dev không lộ lỗi vì refs/main còn từ những lần tải cũ; máy build CI sạch thì
    bản Linux/macOS kèm mô hình vẫn đòi mạng ở lần mở đầu, và copy_release_models.py
    báo "chưa tải" (2026-09-28)."""
    hub = Path(os.environ["HF_HOME"]) / "hub"
    for repo, sha in revisions.items():
        ref = hub / f"models--{repo.replace('/', '--')}" / "refs" / "main"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(sha, encoding="utf-8")


def prune_old_revisions(keep: dict[str, str]) -> None:
    """Xoá mọi revision cũ, chỉ giữ revision vừa ghim.

    Cần thiết vì không có symlink thì mỗi revision thừa là một bản copy đầy đủ —
    lần đo thực tế: 199 MB trùng lặp đi thẳng vào gói gửi cho khách.
    """
    from huggingface_hub import scan_cache_dir

    try:
        info = scan_cache_dir()
    except Exception as e:
        print(f"Bỏ qua bước dọn revision cũ: {e}")
        return

    doomed = [
        rev.commit_hash
        for repo in info.repos
        if repo.repo_id in keep
        for rev in repo.revisions
        if rev.commit_hash != keep[repo.repo_id]
    ]
    if not doomed:
        return

    strategy = info.delete_revisions(*doomed)
    freed = strategy.expected_freed_size_str
    # Xoá TRƯỚC rồi mới in: một lỗi mã hoá console không được phép làm hỏng bước dọn.
    strategy.execute()
    print(f"Đã dọn {len(doomed)} revision cũ, giải phóng {freed}")

    # Dọn nốt bằng tay. API cache của HF giả định blobs + symlink; trên Windows
    # không bật Developer Mode thì file nằm thẳng trong snapshot nên kế toán của nó
    # lệch và vẫn bỏ sót (đo thực tế: sót một file 50 MB).
    import shutil
    stuck: list[Path] = []
    for repo_id, keep_sha in keep.items():
        snap_root = Path(os.environ["HF_HOME"]) / "hub" / f"models--{repo_id.replace('/', '--')}" / "snapshots"
        if not snap_root.is_dir():
            continue
        for d in snap_root.iterdir():
            if not d.is_dir() or d.name == keep_sha:
                continue
            # KHÔNG dùng ignore_errors: Windows khoá file mà ONNX Runtime đang mmap,
            # nuốt lỗi thì script báo dọn xong trong khi vẫn còn hàng chục MB rác
            # đi thẳng vào gói phát hành.
            try:
                shutil.rmtree(d)
                print(f"  bỏ snapshot thừa {repo_id}@{d.name[:12]}")
            except Exception as e:
                stuck.append(d)
                print(f"  KHÔNG xoá được {repo_id}@{d.name[:12]}: {e}")

    if stuck:
        print("\nCÒN RÁC TRONG CACHE — đóng gói bây giờ sẽ thừa dung lượng.")
        print("Thường do một tiến trình đang giữ file. Đóng hết ứng dụng rồi chạy lại,")
        print("hoặc xoá tay các thư mục sau:")
        for d in stuck:
            print(f"  {d}")


if __name__ == "__main__":
    sys.exit(main())
