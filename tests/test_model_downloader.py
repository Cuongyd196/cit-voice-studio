"""Trình tải mô hình nền: tiến trình, huỷ, và các nhánh lỗi.

Không test nào chạm mạng hay tải mô hình thật — `snapshot_download` và
`HfApi` đều bị vá.
"""
from __future__ import annotations

import threading
from unittest.mock import patch

import pytest

from apps import model_downloader as md
from apps import model_catalog as mc


@pytest.fixture(autouse=True)
def _state_sach():
    """State là global — trả lại nguyên trạng sau mỗi test."""
    md._reset_state()
    yield
    md._cancel.clear()
    md._reset_state()


def test_state_ban_dau_la_idle():
    st = md.get_state()
    assert st["state"] == "idle"
    assert st["percent"] == 0
    assert st["model_id"] is None


def test_get_state_tra_ve_ban_sao_khong_sua_duoc_state_that():
    st = md.get_state()
    st["state"] = "bi_sua"
    assert md.get_state()["state"] == "idle"


def test_progress_tqdm_quy_so_file_xong_ra_byte_va_phan_tram():
    """`total` hf đưa xuống là SỐ FILE, không phải byte (xem docstring _ProgressTqdm)."""
    md._set_state(state="downloading", total_bytes=1000, done_bytes=0)
    md._dat_nguon(0, 1000)
    bar = md._ProgressTqdm(total=4, desc="onnx_update/backbone.onnx")
    bar.update(1)
    assert md.get_state()["done_bytes"] == 250
    assert md.get_state()["percent"] == pytest.approx(25.0)
    bar.update(1)
    assert md.get_state()["done_bytes"] == 500
    assert md.get_state()["percent"] == pytest.approx(50.0)


def test_progress_tqdm_cong_them_byte_cua_cac_nguon_da_xong():
    """Mô hình nhiều repo: nguồn thứ hai chạy tiếp từ mốc của nguồn thứ nhất."""
    md._set_state(state="downloading", total_bytes=1000, done_bytes=0)
    md._dat_nguon(600, 400)
    bar = md._ProgressTqdm(total=2, desc="codec")
    bar.update(1)
    assert md.get_state()["done_bytes"] == 800


def test_progress_tqdm_du_giong_tqdm_de_thread_map_chay_duoc():
    """Hợp đồng tối thiểu của `tqdm.contrib.concurrent.thread_map`.

    Thiếu `get_lock`/`set_lock` thì cả lệnh tải chết với AttributeError; `__iter__`
    không yield lại phần tử thì executor không bị tiêu thụ và KHÔNG file nào được
    tải — mà cũng không có lỗi nào để lần ra. Cả hai đều đã xảy ra thật.
    """
    from tqdm.contrib.concurrent import ensure_lock

    md._set_state(state="downloading", total_bytes=1000, done_bytes=0)
    md._dat_nguon(0, 1000)
    with ensure_lock(md._ProgressTqdm, lock_name="") as lock:
        assert lock is not None
    assert list(md._ProgressTqdm(iter("abc"), total=3)) == ["a", "b", "c"]
    assert md.get_state()["done_bytes"] == 1000


def test_progress_tqdm_ghi_lai_ten_file_dang_tai():
    md._set_state(state="downloading", total_bytes=1000, done_bytes=0)
    md._ProgressTqdm(total=600, desc="onnx_update/backbone.onnx")
    assert md.get_state()["current_file"] == "onnx_update/backbone.onnx"


def test_percent_khong_vuot_qua_100_khi_total_doan_sai():
    md._set_state(state="downloading", total_bytes=100, done_bytes=0)
    md._dat_nguon(0, 500)
    bar = md._ProgressTqdm(total=1, desc="x")
    bar.update(5)
    assert md.get_state()["percent"] == 100.0


def test_percent_bang_0_khi_chua_biet_total():
    md._set_state(state="downloading", total_bytes=0, done_bytes=0)
    md._dat_nguon(0, 0)
    bar = md._ProgressTqdm(total=0, desc="x")
    bar.update(10)
    assert md.get_state()["percent"] == 0.0


def test_progress_tqdm_nem_cancelled_khi_co_huy_bat():
    md._set_state(state="downloading", total_bytes=1000, done_bytes=0)
    bar = md._ProgressTqdm(total=6, desc="x")
    md._cancel.set()
    with pytest.raises(md.Cancelled):
        bar.update(10)


def test_chuoi_loi_mang_ra_tieng_viet_khong_phai_traceback():
    msg = md._chuoi_loi_mang(ConnectionError("Max retries exceeded with url: ..."))
    assert "HuggingFace" in msg or "mạng" in msg
    assert "Traceback" not in msg
    assert "Max retries" not in msg


def test_set_state_an_toan_khi_goi_tu_nhieu_thread():
    md._set_state(state="downloading", done_bytes=0, total_bytes=10_000)

    def cong():
        for _ in range(500):
            md._set_state(done_bytes=md.get_state()["done_bytes"] + 1)

    ts = [threading.Thread(target=cong) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    # Không khẳng định đúng 2000 (đọc-rồi-ghi vốn có đua), chỉ đòi không vỡ
    # và state vẫn đọc được bình thường.
    assert md.get_state()["done_bytes"] > 0


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _spec_gia():
    return mc.get("VieNeu-TTS-v3-Turbo (fp32)")


class _InfoGia:
    """Thay cho HfApi().model_info(...)."""

    def __init__(self, sha="abc123", sizes=(100, 200)):
        self.sha = sha
        self.siblings = [
            type("S", (), {"rfilename": f"onnx_update/f{i}.onnx", "size": s})()
            for i, s in enumerate(sizes)
        ]


def test_worker_chay_het_va_ket_thuc_o_trang_thai_ready():
    goi = []
    with patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_snapshot_download", side_effect=lambda **kw: goi.append(kw)), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")):
        md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    assert md.get_state()["state"] == "ready"
    assert goi, "phải gọi snapshot_download"


def test_worker_luon_ghim_revision_bang_sha():
    goi = []
    with patch.object(md, "_model_info", return_value=_InfoGia(sha="deadbeef")), \
         patch.object(md, "_snapshot_download", side_effect=lambda **kw: goi.append(kw)), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")):
        md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    assert goi, "phải gọi snapshot_download"
    for kw in goi:
        assert kw["revision"] == "deadbeef", "không ghim sha thì file rơi rải rác nhiều revision"
        assert kw["tqdm_class"] is md._ProgressTqdm


def test_worker_chan_som_khi_thieu_dung_luong_o():
    with patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_du_cho_trong_o", return_value=(False, "Ổ đĩa chỉ còn 50 MB.")), \
         patch.object(md, "_snapshot_download") as tai:
        md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    tai.assert_not_called()
    st = md.get_state()
    assert st["state"] == "error"
    assert "Ổ đĩa" in st["message"]


def test_worker_bao_loi_tieng_viet_khi_mat_mang():
    with patch.object(md, "_model_info", side_effect=ConnectionError("Max retries")):
        md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    st = md.get_state()
    assert st["state"] == "error"
    assert "Max retries" not in st["message"]
    assert "HuggingFace" in st["message"] or "mạng" in st["message"]


def test_huy_giua_chung_cho_ra_trang_thai_cancelled():
    def tai_roi_bi_huy(**kw):
        raise md.Cancelled()

    with patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
         patch.object(md, "_snapshot_download", side_effect=tai_roi_bi_huy):
        md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    assert md.get_state()["state"] == "cancelled"


def test_auto_apply_goi_dung_mot_lan_voi_dung_model_id():
    da_goi = []
    with patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
         patch.object(md, "_snapshot_download"):
        md._chay(_spec_gia(), auto_apply=True, apply_fn=lambda mid: da_goi.append(mid))

    assert da_goi == ["VieNeu-TTS-v3-Turbo (fp32)"]
    assert md.get_state()["state"] == "ready"


def test_tai_xong_nhung_ap_dung_that_bai_van_bao_loi():
    """Mặc định `apply_error_formatter` là `str`, nên câu lỗi gốc lọt qua nguyên."""
    def ap_dung_hong(_mid):
        raise RuntimeError("onnxruntime nổ")

    with patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
         patch.object(md, "_snapshot_download"):
        md._chay(_spec_gia(), auto_apply=True, apply_fn=ap_dung_hong)

    st = md.get_state()
    assert st["state"] == "error"
    assert "onnxruntime" in st["message"]


def test_loi_o_buoc_ap_dung_dung_apply_error_formatter_chu_khong_phai_loi_tai():
    """Tải xong rồi mà nạp hỏng thì không được báo là "không tải được"."""
    goc = md.apply_error_formatter
    md.apply_error_formatter = lambda e: f"DICH-RIENG: {e}"
    try:
        with patch.object(md, "_model_info", return_value=_InfoGia()), \
             patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
             patch.object(md, "_snapshot_download"):
            md._chay(_spec_gia(), auto_apply=True,
                     apply_fn=lambda _mid: (_ for _ in ()).throw(RuntimeError("DLL load failed")))
    finally:
        md.apply_error_formatter = goc

    msg = md.get_state()["message"]
    assert msg.startswith("DICH-RIENG:")
    assert "Không tải được" not in msg


def test_start_tu_choi_khi_id_khong_co_trong_catalog():
    ok, ly_do = md.start("model-ma", auto_apply=False)
    assert ok is False
    assert ly_do


def test_start_tu_choi_job_thu_hai_khi_dang_tai():
    md._set_state(state="downloading", model_id="VieNeu-TTS-v3-Turbo (fp32)")
    ok, ly_do = md.start("VieNeu-TTS-v3-Turbo (int8)", auto_apply=False)
    assert ok is False
    assert "fp32" in ly_do


def test_start_khong_giu_model_lock_trong_luc_tai():
    """Bất biến cốt lõi: tải chạy được ngay cả khi model_lock đang bị giữ.

    Mất tính chất này là app lại bị treo suốt lúc tải, đúng thứ thiết kế này
    sinh ra để bỏ.
    """
    import apps.web_stream as ws

    da_tai = threading.Event()

    with ws.model_lock:  # giả lập một yêu cầu đọc đang chạy
        with patch.object(md, "_model_info", return_value=_InfoGia()), \
             patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
             patch.object(md, "_snapshot_download", side_effect=lambda **kw: da_tai.set()):
            md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    assert da_tai.is_set(), "tải bị chặn bởi model_lock"
    assert md.get_state()["state"] == "ready"


def test_du_cho_trong_o_doi_du_120_phan_tram():
    class _Usage:
        free = 100 * 1024 * 1024

    with patch("shutil.disk_usage", return_value=_Usage()):
        ok, _ = md._du_cho_trong_o(50 * 1024 * 1024)     # cần 60 MB, còn 100 MB
        assert ok is True
        ok, ly_do = md._du_cho_trong_o(90 * 1024 * 1024)  # cần 108 MB, còn 100 MB
        assert ok is False
        assert "MB" in ly_do or "GB" in ly_do


def test_can_tu_cai_gpu_deps_uses_same_capability_as_settings():
    """Backend Python riêng vẫn cài GPU nếu có công cụ, CPU luôn bỏ qua."""
    spec_gpu = mc.get("VieNeu-TTS-v3-Turbo (GPU)")   # requires torch + cuda
    spec_cpu = mc.get("VieNeu-TTS-v3-Turbo (int8)")  # không cần torch

    with patch.object(mc, "frozen_gpu_autoinstall_possible", return_value=True):
        assert md._can_tu_cai_gpu_deps(spec_gpu) is True
        assert md._can_tu_cai_gpu_deps(spec_cpu) is False
    with patch.object(mc, "frozen_gpu_autoinstall_possible", return_value=False):
        assert md._can_tu_cai_gpu_deps(spec_gpu) is False


def test_chay_goi_gpu_installer_khi_frozen_va_can_torch():
    """`_can_tu_cai_gpu_deps` bật thì worker phải gọi install_gpu_deps trước khi áp dụng."""
    from apps import gpu_installer

    goi = []
    with patch.object(md, "_can_tu_cai_gpu_deps", return_value=True), \
         patch.object(gpu_installer, "install_gpu_deps", side_effect=lambda **kw: goi.append(kw)), \
         patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
         patch.object(md, "_snapshot_download"):
        md._chay(_spec_gia(), auto_apply=False, apply_fn=None)

    assert goi, "phải gọi gpu_installer.install_gpu_deps"
    assert md.get_state()["state"] == "ready"


def test_cancel_during_gpu_setup_never_applies_model():
    from apps import gpu_installer
    from unittest.mock import Mock
    apply = Mock()
    def install(**kwargs):
        kwargs["on_progress"]("GPU setup")
        assert md.get_state()["phase"] == "gpu_setup"
        md.cancel()
        kwargs["check_cancel"]()
    with patch.object(md, "_can_tu_cai_gpu_deps", return_value=True), \
         patch.object(gpu_installer, "install_gpu_deps", side_effect=install), \
         patch.object(md, "_model_info", return_value=_InfoGia()), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
         patch.object(md, "_snapshot_download"):
        md._chay(_spec_gia(), auto_apply=True, apply_fn=apply)
    assert md.get_state()["state"] == "cancelled"
    apply.assert_not_called()


def _may_khong_tao_duoc_symlink(*_a, **_k):
    err = OSError("A required privilege is not held by the client")
    err.winerror = 1314
    raise err


def test_do_truoc_symlink_de_cac_luong_tai_khong_doc_nham_true(tmp_path):
    """Race của huggingface_hub: nó ghi True vào cache TRƯỚC khi thử symlink, nên
    luồng tải song song đọc được True sai rồi chết WinError 1314. Sau khi dò trước,
    mọi luồng phải thấy False và tự chuyển sang chép file."""
    from huggingface_hub import constants
    from huggingface_hub import file_download as fd

    repo = "pnnbao-ump/VieNeu-TTS-v3-Turbo"
    folder = (tmp_path / fd.repo_folder_name(repo_id=repo, repo_type="model")).resolve()
    with patch.object(constants, "HF_HUB_CACHE", str(tmp_path)), \
         patch.object(fd.os, "symlink", side_effect=_may_khong_tao_duoc_symlink), \
         patch.dict(fd._are_symlinks_supported_in_dir, {str(folder): True}):  # True sai từ lần hỏng trước
        md._prime_symlink_check(repo)

        ket_qua = []
        rao = threading.Barrier(4)

        def luong_tai():
            rao.wait()
            ket_qua.append(fd.are_symlinks_supported(str(folder)))

        luong = [threading.Thread(target=luong_tai) for _ in range(4)]
        for t in luong:
            t.start()
        for t in luong:
            t.join()

    assert ket_qua == [False] * 4


def test_snapshot_download_luon_do_truoc_symlink():
    with patch.object(md, "_prime_symlink_check") as do_truoc, \
         patch("huggingface_hub.snapshot_download", return_value="ok"):
        assert md._snapshot_download(repo_id="a/b", repo_type="model") == "ok"
    do_truoc.assert_called_once_with("a/b")


def test_nguon_ghim_revision_thi_tai_dung_revision_do():
    goi = []
    hoi_info = []

    def info(repo, revision=None):
        hoi_info.append(revision)
        return _InfoGia(sha="sha-moi-nhat")

    with patch.object(md, "_model_info", side_effect=info), \
         patch.object(md, "_snapshot_download", side_effect=lambda **kw: goi.append(kw)), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")):
        md._chay(mc.get(mc.SUPERTONIC_ID), auto_apply=False, apply_fn=None)
    assert hoi_info == [mc.SUPERTONIC_REVISION]
    assert goi[0]["revision"] == mc.SUPERTONIC_REVISION
    assert goi[0]["set_main_ref"] is False, "sha ghim trong catalog không phải main của repo"
    assert md.get_state()["state"] == "ready"


def test_tai_ghim_sha_xong_ghi_refs_main_de_tim_offline_duoc(tmp_path):
    """snapshot_download(revision=<sha>) không ghi refs/main. Thiếu nó thì mọi
    hf_hub_download(local_files_only=True) - is_downloaded() và lúc nạp mô hình -
    đều báo "chưa tải" dù file đã nằm đủ (gặp thật với Kokoro tải lần đầu)."""
    from huggingface_hub import constants
    from huggingface_hub import file_download as fd

    repo = "onnx-community/Kokoro-82M-v1.0-ONNX"
    refs = tmp_path / fd.repo_folder_name(repo_id=repo, repo_type="model") / "refs" / "main"
    with patch.object(constants, "HF_HUB_CACHE", str(tmp_path)), \
         patch.object(md, "_prime_symlink_check"), \
         patch("huggingface_hub.snapshot_download", return_value="ok"):
        md._snapshot_download(repo_id=repo, repo_type="model", revision="abc123")
    assert refs.read_text() == "abc123"


def test_tai_khong_ghim_sha_thi_khong_dung_refs(tmp_path):
    from huggingface_hub import constants

    with patch.object(constants, "HF_HUB_CACHE", str(tmp_path)), \
         patch.object(md, "_prime_symlink_check"), \
         patch("huggingface_hub.snapshot_download", return_value="ok"):
        md._snapshot_download(repo_id="a/b", repo_type="model")
        md._snapshot_download(repo_id="c/d", repo_type="model", revision="abc", set_main_ref=False)
    assert not any(tmp_path.rglob("main"))
