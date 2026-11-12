"""Giới hạn VRAM cho mô hình GPU: card 4 GB từng treo máy vì CUDA graph chất mãi.

Không cần GPU: torch/batch engine được thay bằng đồ giả.
"""
from collections import OrderedDict

import numpy as np
import pytest
from fastapi.testclient import TestClient

from apps import gpu_memory as gm

GB = gm.GB


@pytest.fixture(autouse=True)
def _cau_hinh_tam(tmp_path, monkeypatch):
    monkeypatch.setattr(gm, "settings_path", lambda: tmp_path / "gpu-memory.json")
    gm._state.clear()


# ---- Tính trần ----

def test_card_4gb_tu_dong_chua_cho_windows_va_giu_it_graph():
    # Card 4 GB, Windows + WebView2 đã chiếm 1 GB, model 0,6 GB.
    p = gm.plan(total=4 * GB, free=int(2.4 * GB), reserved=int(0.6 * GB),
                model_bytes=int(0.6 * GB), limit_gb=None)
    assert p["limit"] == pytest.approx(2.5 * GB, abs=2)   # free + reserved - 0,5 GB dự phòng
    assert 1 <= p["graphs"] <= 3


def test_tu_dong_khong_bao_gio_dung_het_card():
    p = gm.plan(total=8 * GB, free=int(7.5 * GB), reserved=int(0.4 * GB),
                model_bytes=int(0.4 * GB), limit_gb=None)
    assert p["limit"] == 7 * GB                 # luôn chừa 1 GB
    assert p["graphs"] == gm.MAX_GRAPHS


def test_nguoi_dung_dat_muc_thap_van_giu_mot_graph_va_khong_vuot_card():
    assert gm.plan(4 * GB, GB, 0, int(0.6 * GB), 1.5)["graphs"] == 1
    assert gm.plan(4 * GB, GB, 0, int(0.6 * GB), 16.0)["limit"] == 4 * GB


def test_cau_hinh_hong_thi_coi_nhu_tu_dong():
    gm.settings_path().write_text('{"vram_limit_gb": "abc"}', encoding="utf-8")
    assert gm.configured_limit_gb() is None
    gm.settings_path().write_text('{"vram_limit_gb": 0.2}', encoding="utf-8")
    assert gm.configured_limit_gb() is None
    gm.save_limit_gb(3.0)
    assert gm.configured_limit_gb() == 3.0


# ---- Bộ đệm graph LRU trong batch engine ----

def _engine(max_graphs):
    torch = pytest.importorskip("torch")
    if not hasattr(torch, "__path__"):
        # test_factory nhét torch giả vào sys.modules khi chạy cả bộ (xem tests/test_factory.py).
        pytest.skip("torch giả từ test khác - chạy riêng file này để kiểm LRU")
    from vieneu.v3_turbo_serve.engine import V3TurboBatchEngine

    eng = object.__new__(V3TurboBatchEngine)
    eng._fused = OrderedDict()
    eng.max_fused_graphs = max_graphs
    return eng


def test_lru_bo_graph_lau_chua_dung_nhat():
    eng = _engine(2)
    eng._get_fused("a", lambda: "A")
    eng._get_fused("b", lambda: "B")
    assert eng._get_fused("a", lambda: pytest.fail("phải dùng lại graph cũ")) == "A"
    eng._get_fused("c", lambda: "C")            # "b" lâu chưa dùng nhất -> bị bỏ
    assert list(eng._fused) == ["a", "c"]


def test_khong_dat_gioi_han_thi_giu_nhu_upstream():
    eng = _engine(None)
    for k in range(10):
        eng._get_fused(k, lambda k=k: k)
    assert len(eng._fused) == 10


# ---- Hết VRAM giữa chừng: dọn graph, chia đôi lô, đọc lại ----

class _OOM(RuntimeError):
    pass


_OOM.__name__ = "OutOfMemoryError"


class _FakeBatchEngine:
    def __init__(self, max_rows):
        self.max_rows, self.calls, self.trims = max_rows, [], []

    def generate_batch(self, reqs, **_):
        self.calls.append(len(reqs))
        if len(reqs) > self.max_rows:
            raise _OOM("CUDA out of memory. Tried to allocate 512.00 MiB")
        return [np.full(10, float(r["phonemes"][-1]), dtype=np.float32) for r in reqs]

    def trim_fused(self, keep):
        self.trims.append(keep)


def _tts_with(engine, monkeypatch):
    import vieneu.v3turbo as v3

    monkeypatch.setattr(v3, "phonemize_text_with_emotions", lambda c: c)
    tts = object.__new__(v3.V3TurboVieNeuTTS)
    tts._get_batch_engine = lambda: engine
    tts._fused_available = lambda: True
    return tts


def test_het_vram_thi_chia_doi_lo_va_van_ra_du_cau_dung_thu_tu(monkeypatch):
    eng = _FakeBatchEngine(max_rows=2)
    tts = _tts_with(eng, monkeypatch)
    chunks = [f"câu {i}" for i in range(8)]
    wavs = tts._infer_chunks(chunks, None, None, True, 8, {"max_new_frames": 300})
    assert [float(w[0]) for w in wavs] == list(range(8))
    assert eng.calls == [8, 4, 2, 2, 4, 2, 2]     # 8 lỗi -> 4 lỗi -> 2 chạy được
    assert 0 in eng.trims                        # đã bỏ hết graph để trả VRAM


def test_lo_mot_cau_van_het_vram_thi_bao_loi_that(monkeypatch):
    tts = _tts_with(_FakeBatchEngine(max_rows=0), monkeypatch)
    with pytest.raises(RuntimeError, match="out of memory"):
        tts._infer_chunks(["a1", "b2"], None, None, True, 2, {"max_new_frames": 300})


def test_loi_khac_khong_bi_nuot(monkeypatch):
    class Hong(_FakeBatchEngine):
        def generate_batch(self, reqs, **_):
            raise ValueError("lỗi khác")

    tts = _tts_with(Hong(9), monkeypatch)
    with pytest.raises(ValueError):
        tts._infer_chunks(["a1", "b2"], None, None, True, 2, {"max_new_frames": 300})


# ---- API (UI-only) ----

def test_api_khi_khong_chay_model_gpu():
    import apps.web_stream as ws

    client = TestClient(ws.app, base_url="http://127.0.0.1:8001")
    r = client.get("/api/gpu/memory").json()
    assert r["available"] is False and r["limit_gb"] is None
    r = client.put("/api/gpu/memory", json={"limit_gb": 3})
    assert r.status_code == 200 and r.json()["limit_gb"] == 3
    assert client.put("/api/gpu/memory", json={"limit_gb": 0.5}).status_code == 400
    assert client.put("/api/gpu/memory", json={"limit_gb": None}).json()["limit_gb"] is None


def test_api_chi_doi_duoc_tu_may_nay():
    import apps.web_stream as ws

    r = TestClient(ws.app, base_url="http://127.0.0.1:8001").put("/api/gpu/memory", json={"limit_gb": 3},
                               headers={"Origin": "https://trang-la.example"})
    assert r.status_code == 403
