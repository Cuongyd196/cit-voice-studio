"""Mô hình đa ngôn ngữ Kokoro: catalog, cài thư viện theo yêu cầu, engine, API.

Không test nào tải mạng hay cần kokoro_onnx/misaki thật: bộ tách âm (phonemizer +
espeak-ng GPL, misaki + từ điển Nhật/Trung) KHÔNG nằm trong .venv của app — chỉ
được cài vào máy khách khi họ bấm Tải về (apps/kokoro_installer.py).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from apps import model_catalog as mc

KOKORO_ID = mc.KOKORO_ID
# current_model_info của Kokoro như load_model_instance ghi: danh sách ngôn ngữ
# kiểu Supertonic nhưng KHÔNG có "vi".
KOKORO_INFO = {
    "name": KOKORO_ID, "backend": "onnx", "precision": "fp32", "device": "cpu",
    "sample_rate": 24_000, "supports_emotions": False, "supports_seed": False,
    "languages": [{"code": "en", "name": "Tiếng Anh"}, {"code": "fr", "name": "Tiếng Pháp"},
                  {"code": "ja", "name": "Tiếng Nhật"}],
}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def test_kokoro_co_trong_catalog_voi_dung_kha_nang():
    spec = mc.get(KOKORO_ID)
    assert spec is not None
    assert spec.sample_rate == 24_000
    assert spec.supports_cloning is False
    assert "kokoro_deps" in spec.requires
    assert spec.approx_bytes > 300 * 1024 * 1024


def test_chi_kokoro_can_bo_tach_am():
    for spec in mc.MODELS:
        assert ("kokoro_deps" in spec.requires) is mc.is_kokoro(spec.id)


def test_kokoro_goi_co_ban_khong_kem_nhat_trung_va_ban_fp32():
    (src,) = mc.get(KOKORO_ID).sources
    assert src.repo == mc.KOKORO_REPO
    assert "onnx/model.onnx" in src.allow_patterns
    # Bản 8-bit chậm ~10 lần trên CPU (đo: RTF 5.7 so với 0.5), cấm lọt vào.
    assert not any("quantized" in p or "int8" in p or "q8" in p for p in src.allow_patterns)
    giong = {p.split("/")[1][:2] for p in src.allow_patterns if p.startswith("voices/")}
    assert {"af", "bm", "ef", "ff", "hf", "if", "pm"} <= giong
    # Nhật/Trung là gói tải thêm: không lọt vào lần tải đầu.
    assert not giong & {"jf", "jm", "zf", "zm"}
    assert "voices/af_heart.bin" in src.marker_paths
    # Cache chỉ có giọng tiếng Anh (bản trước) phải bị coi là chưa tải đủ.
    assert any(m.startswith("voices/f") for m in src.marker_paths)


def test_goi_ngon_ngu_nhat_trung():
    assert [p.code for p in mc.KOKORO_PACKS] == ["ja", "zh"]
    ja = mc.kokoro_pack("ja")
    assert ja.patterns == ("voices/jf_*.bin", "voices/jm_*.bin")
    assert ja.marker.startswith("voices/jf_")
    assert mc.kokoro_pack("fr") is None


@pytest.mark.parametrize("co_deps, mong_doi", [(True, True), (False, False)])
def test_compatible_kokoro_theo_co_thu_vien(co_deps, mong_doi):
    ok, ly_do = mc.compatible(mc.get(KOKORO_ID), has_torch=False, has_cuda=False,
                              has_kokoro_deps=co_deps)
    assert ok is mong_doi
    assert (ly_do is None) is mong_doi


def test_mo_hinh_cu_khong_can_co_kokoro():
    ok, _ = mc.compatible(mc.get("VieNeu-TTS-v3-Turbo (int8)"), has_torch=False, has_cuda=False)
    assert ok is True


# ---------------------------------------------------------------------------
# Cài bộ tách âm theo yêu cầu
# ---------------------------------------------------------------------------

@pytest.fixture
def ki(tmp_path, monkeypatch):
    from apps import kokoro_installer as ki

    monkeypatch.setattr(ki, "venv_dir", lambda: tmp_path / "addons" / "kokoro" / "3.12")
    monkeypatch.setattr(sys, "path", list(sys.path))
    return ki


def _venv_gia(ki):
    """Venv giả đủ để `deps_ready` tin: site-packages, python, và pyvenv.cfg trỏ
    `home` vào một thư mục Python gốc có thật (như gpu_venv/base-python)."""
    from apps import gpu_installer

    venv = ki.venv_dir()
    site = venv / ("Lib/site-packages" if sys.platform == "win32" else "lib/python3.12/site-packages")
    site.mkdir(parents=True, exist_ok=True)
    py = gpu_installer._venv_python(venv)
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("")
    home = venv.parent.parent / "base-python-gia"
    home.mkdir(parents=True, exist_ok=True)
    (venv / "pyvenv.cfg").write_text(f"home = {home}\n", encoding="utf-8")
    return venv, site


def test_chua_cai_thi_khong_kich_hoat(ki):
    assert ki.deps_ready() is False
    assert ki.activate() is False


def test_kich_hoat_them_site_packages_vao_CUOI_sys_path(ki):
    venv, site = _venv_gia(ki)
    (venv / ki._MARKER_NAME).write_text(ki._marker_value(), encoding="utf-8")
    assert ki.activate() is True
    # Cuối, không phải đầu: numpy/onnxruntime của app phải thắng bản trong venv.
    assert sys.path[-1] == str(site)
    assert ki.activate() is True
    assert sys.path.count(str(site)) == 1


def test_marker_khac_phien_ban_thi_coi_nhu_chua_cai(ki):
    venv, _ = _venv_gia(ki)
    (venv / ki._MARKER_NAME).write_text('{"schema": 0}', encoding="utf-8")
    assert ki.deps_ready() is False


def _ghi_lenh(args) -> list:
    """Lệnh đã chạy, với `-r <file khoá>` mở ra thành các dòng `gói==bản` trong file
    (file bị xoá ngay sau khi cài, nên phải đọc lúc lệnh chạy)."""
    out = [str(a) for a in args]
    if "-r" in out:
        req = Path(out[out.index("-r") + 1])
        out += [ln.split()[0] for ln in req.read_text(encoding="utf-8").splitlines()
                if "==" in ln]
    return out


def test_cai_dat_dung_goi_ghim_phien_ban_va_kokoro_khong_keo_deps(ki, monkeypatch, tmp_path):
    from apps import gpu_installer

    venv = ki.venv_dir()
    lenh = []

    def run(args, check_cancel, **kw):
        lenh.append(_ghi_lenh(args))
        if args[1:2] == ["venv"]:
            _venv_gia(ki)
            (venv / ("Scripts" if sys.platform == "win32" else "bin")).mkdir(exist_ok=True)
            gpu_installer._venv_python(venv).write_text("")
        return ""

    monkeypatch.setattr(gpu_installer, "find_uv", lambda: "uv")
    monkeypatch.setattr(gpu_installer, "_install_base_python", lambda *a, **k: tmp_path / "python.exe")
    monkeypatch.setattr(gpu_installer, "_run", run)
    monkeypatch.setattr(ki, "_verify_in_process", lambda: None)

    ki.install_deps()

    pip = [c for c in lenh if c[1:3] == ["pip", "install"]]
    kokoro = next(c for c in pip if any(a.startswith("kokoro-onnx==") for a in c))
    # kokoro-onnx kéo theo onnxruntime + numpy; app đã có sẵn, không cài bản thứ hai.
    # Mọi lệnh cài đều --no-deps + --require-hashes: chỉ đúng các gói trong khoá.
    assert all("--no-deps" in c and "--require-hashes" in c for c in pip)
    assert set(ki.BASE_PACKAGES) <= set(kokoro)
    goi = " ".join(" ".join(c) for c in pip)
    assert f"phonemizer=={ki.PHONEMIZER_VERSION}" in goi
    assert f"espeakng-loader=={ki.ESPEAKNG_LOADER_VERSION}" in goi
    # Bộ cơ bản không kéo từ điển Nhật/Trung (~300 MB trên đĩa).
    assert "misaki" not in goi and "unidic" not in goi and "jieba" not in goi
    assert "onnxruntime" not in goi and "numpy" not in goi
    assert ki.deps_ready() is True
    assert ki.ready_languages() == set(ki.BASE_LANGUAGES)


def _gia_cai(ki, monkeypatch, tmp_path, lenh):
    from apps import gpu_installer

    def run(args, check_cancel, **kw):
        lenh.append(_ghi_lenh(args))
        if args[1:2] == ["venv"]:
            venv = ki.venv_dir()
            _venv_gia(ki)
            (venv / ("Scripts" if sys.platform == "win32" else "bin")).mkdir(exist_ok=True)
            gpu_installer._venv_python(venv).write_text("")
        return ""

    monkeypatch.setattr(gpu_installer, "find_uv", lambda: "uv")
    monkeypatch.setattr(gpu_installer, "_install_base_python", lambda *a, **k: tmp_path / "python.exe")
    monkeypatch.setattr(gpu_installer, "_run", run)
    monkeypatch.setattr(ki, "_verify_in_process", lambda: None)
    monkeypatch.setattr(ki, "_verify_pack_in_process", lambda code: None)


@pytest.mark.parametrize("code, co, khong", [
    ("ja", ("fugashi==", "unidic-lite==", "misaki=="), ("jieba", "pyopenjtalk")),
    ("zh", ("jieba==", "pypinyin==", "misaki=="), ("unidic", "fugashi")),
])
def test_cai_goi_ngon_ngu_chi_cai_dung_goi_do(ki, monkeypatch, tmp_path, code, co, khong):
    lenh = []
    _gia_cai(ki, monkeypatch, tmp_path, lenh)
    ki.install_pack(code)   # chưa có bộ cơ bản: tự cài luôn

    pip = [c for c in lenh if c[1:3] == ["pip", "install"]]
    goi_pack = next(c for c in pip if any(a.startswith("misaki==") for a in c))
    # misaki[ja] kéo pyopenjtalk (không có wheel Windows): cài --no-deps theo danh sách.
    assert "--no-deps" in goi_pack
    assert all(any(a.startswith(x) for a in goi_pack) for x in co)
    assert not any(x in " ".join(goi_pack) for x in khong)
    assert ki.pack_ready(code) is True
    assert code in ki.ready_languages()
    khac = "zh" if code == "ja" else "ja"
    assert ki.pack_ready(khac) is False


def test_goi_ngon_ngu_mat_hieu_luc_khi_bo_co_ban_cai_lai(ki, monkeypatch, tmp_path):
    _gia_cai(ki, monkeypatch, tmp_path, [])
    ki.install_pack("ja")
    (ki.venv_dir() / ki._MARKER_NAME).unlink()
    assert ki.pack_ready("ja") is False
    assert ki.ready_languages() == set()


def test_cai_that_bai_thi_khong_ghi_marker(ki, monkeypatch, tmp_path):
    from apps import gpu_installer

    def run(args, check_cancel, **kw):
        if args[1:2] == ["venv"]:
            _venv_gia(ki)
            (ki.venv_dir() / ("Scripts" if sys.platform == "win32" else "bin")).mkdir(exist_ok=True)
            gpu_installer._venv_python(ki.venv_dir()).write_text("")
            return ""
        if "pip" in args:
            raise RuntimeError("mất mạng")
        return ""

    monkeypatch.setattr(gpu_installer, "find_uv", lambda: "uv")
    monkeypatch.setattr(gpu_installer, "_install_base_python", lambda *a, **k: tmp_path / "python.exe")
    monkeypatch.setattr(gpu_installer, "_run", run)
    with pytest.raises(RuntimeError):
        ki.install_deps()
    assert ki.deps_ready() is False


def test_thieu_uv_thi_bao_loi_tieng_viet(ki, monkeypatch):
    from apps import gpu_installer

    monkeypatch.setattr(gpu_installer, "find_uv", lambda: None)
    with pytest.raises(RuntimeError, match="công cụ cài"):
        ki.install_deps()


def test_co_the_cai_khi_co_uv_hoac_da_cai(ki, monkeypatch):
    from apps import gpu_installer

    monkeypatch.setattr(gpu_installer, "find_uv", lambda: None)
    assert ki.available() is False
    monkeypatch.setattr(gpu_installer, "find_uv", lambda: "uv")
    assert ki.available() is True


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class _TokenizerGia:
    """espeak giả: trả "<lang>:<text>", chèn cờ đổi ngôn ngữ như espeak thật làm."""

    def phonemize(self, text, lang="en-us"):
        return f"{lang}:{text} (en)x(fr)" if lang == "fr-fr" else f"{lang}:{text}"


class _KokoroGia:
    """Thay kokoro_onnx.Kokoro: ghi lại lời gọi, trả âm thanh dài theo số ký tự."""

    def __init__(self, *a, **k):
        self.calls = []
        self.tokenizer = _TokenizerGia()

    @classmethod
    def from_session(cls, session, voices_path, *a, **k):
        inst = cls()
        inst.voices_path = voices_path
        return inst

    def create(self, text, voice, speed=1.0, lang="en-us", is_phonemes=False, **k):
        self.calls.append((text, voice, speed, is_phonemes))
        return np.full(len(text) * 10, 0.1, dtype=np.float32), 24_000


GIONG = ("af_heart", "af_bella", "bm_george", "am_michael", "ef_dora", "pf_dora",
         "ff_siwis", "hf_alpha", "jf_alpha", "zf_xiaoxiao")


@pytest.fixture
def engine(tmp_path, monkeypatch):
    from apps import kokoro_engine as ke

    voices = tmp_path / "voices"
    voices.mkdir()
    for name in GIONG + ("af",):   # "af.bin" (giọng trộn mặc định của repo) không phải giọng
        np.zeros((510, 1, 256), dtype=np.float32).tofile(voices / f"{name}.bin")
    model = tmp_path / "model.onnx"
    model.write_bytes(b"onnx")
    fake = types.ModuleType("kokoro_onnx")
    fake.Kokoro = _KokoroGia
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake)

    # misaki giả: Nhật -> "ja<...>", Trung -> "zh<...>"
    misaki = types.ModuleType("misaki")
    ja, zh = types.ModuleType("misaki.ja"), types.ModuleType("misaki.zh")
    ja.JAG2P = lambda: (lambda t: (f"ja<{t}>", None))
    zh.ZHG2P = lambda version=None: (lambda t: (f"zh<{t}>", None))
    misaki.ja, misaki.zh = ja, zh
    for name, mod in (("misaki", misaki), ("misaki.ja", ja), ("misaki.zh", zh)):
        monkeypatch.setitem(sys.modules, name, mod)
    monkeypatch.setitem(sys.modules, "jieba", types.SimpleNamespace(setLogLevel=lambda _l: None))

    monkeypatch.setattr(ke, "_create_session", lambda path: Mock())
    return ke.KokoroTTS(model, voices, cache_dir=tmp_path / "cache")


def _cuoi(engine):
    return engine.kokoro.calls[-1][0]


def test_engine_liet_ke_giong_kem_gioi_tinh_ngon_ngu_va_vung(engine):
    ids = [vid for _, vid in engine.list_preset_voices()]
    assert ids[0] == "Heart"                 # giọng tốt nhất đứng đầu
    assert len(ids) == len(GIONG)            # "af.bin" bị bỏ qua
    george = engine._preset_voices["George"]
    assert (george["gender"], george["language"]) == ("male", "en")
    assert george["description"] == "Nam · Kokoro · Tiếng Anh (Anh)"
    assert engine._preset_voices["Heart"]["description"] == "Nữ · Kokoro · Tiếng Anh (Mỹ)"
    assert engine._preset_voices["Alpha (JA)"]["language"] == "ja"
    assert engine._preset_voices["Xiaoxiao (ZH)"]["description"] == "Nữ · Kokoro · Tiếng Trung"
    assert all(" - " in label for label, _ in engine.list_preset_voices())


def test_engine_bao_ngon_ngu_kieu_supertonic_khong_co_tieng_viet(engine):
    # Thứ tự theo LANGUAGES, chỉ những tiếng có giọng.
    assert list(engine.languages) == ["en", "es", "fr", "pt", "hi", "ja", "zh"]
    assert engine.languages["fr"] == "Tiếng Pháp"
    assert "vi" not in engine.languages
    from apps import kokoro_engine as ke
    assert set(ke.PREVIEW_TEXTS) == set(ke.LANGUAGES)


@pytest.mark.parametrize("giong, lang, van_ban, mong_doi", [
    ("Heart", "fr", "Bonjour.", "en-us:Bonjour."),          # lang của yêu cầu bị bỏ qua
    ("George", "en", "Hello.", "en-gb:Hello."),             # giọng Anh-Anh giữ en-gb
    ("Siwis (FR)", "en", "Hello.", "fr-fr:Hello. x"),       # giọng Pháp đọc tiếng Pháp
    ("Siwis (FR)", None, "Bonjour.", "fr-fr:Bonjour. x"),
    ("Heart", None, "こんにちは", "ja<こんにちは>"),          # chữ giọng không đọc được: theo chữ
    ("Heart", "en", "你好", "zh<你好>"),
    ("Alpha (JA)", "zh", "東京", "ja<東京>"),               # giọng Nhật đọc kanji bằng tiếng Nhật
    ("Alpha (JA)", "en", "Hello", "en-us:Hello"),           # chữ Latin trong giọng Nhật: espeak Anh
])
def test_engine_doc_theo_tieng_cua_giong_bo_qua_lang(engine, giong, lang, van_ban, mong_doi):
    engine.infer(van_ban, voice=giong, lang=lang)
    assert _cuoi(engine) == mong_doi


def test_engine_hoi_thoai_mot_lang_chung_moi_giong_doc_dung_tieng_minh(engine):
    # Tab Hội thoại gửi một `language` chung cho mọi lượt: giọng Nhật trong hội
    # thoại "en" vẫn đọc bằng bộ tách âm tiếng Nhật, không qua espeak en-us.
    engine.infer("ありがとう", voice="Alpha (JA)", lang="en")
    assert _cuoi(engine) == "ja<ありがとう>"
    engine.infer("Gracias.", voice="Dora (ES)", lang="en")
    assert _cuoi(engine) == "es:Gracias."


def test_engine_lang_chua_cai_khong_bao_loi(tmp_path, engine):
    from apps import kokoro_engine as ke

    e = ke.KokoroTTS(tmp_path / "model.onnx", tmp_path / "voices", cache_dir=tmp_path / "c3",
                     languages={"en"})
    # Mã hợp lệ nhưng máy chưa cài: vẫn đọc (theo giọng), phần mềm gọi API không lỗi.
    e.infer("Hello.", voice="Heart", lang="ja")
    assert e.kokoro.calls[-1][0] == "en-us:Hello."
    # Gặp chữ Nhật khi chưa cài gói: đọc theo giọng, không báo lỗi.
    e.infer("こんにちは", voice="Heart")
    assert e.kokoro.calls[-1][0].startswith("en-us:")


def test_engine_bo_the_cam_xuc_kieu_supertonic(engine):
    engine.infer("Hi <laugh> there <SIGH> ok <breath>.", voice="Heart")
    assert _cuoi(engine) == "en-us:Hi there ok ."


def test_engine_ten_giong_trung_nhau_giua_cac_thu_tieng_van_phan_biet(engine):
    # ef_dora/pf_dora, hf_alpha/jf_alpha: cùng tên, khác ngôn ngữ.
    assert {"Dora (ES)", "Dora (PT)", "Alpha (HI)", "Alpha (JA)"} <= set(engine._preset_voices)
    assert engine.voice_language("Dora (PT)") == "pt"


def test_engine_nhan_ten_giong_va_ma_goc_cho_kiem_tra_giong_cua_api(engine):
    # web_stream._require_voice trả 400 khi resolve_voice_name ra None.
    assert engine.resolve_voice_name("Heart") == "Heart"
    assert engine.resolve_voice_name("af_heart") == "Heart"
    assert engine.resolve_voice_name("Hải Đăng") is None


@pytest.mark.parametrize("giong, mong_doi", [
    ("George", "en-gb:"), ("Heart", "en-us:"), ("af_heart", "en-us:"),
    ("Dora (ES)", "es:"), ("Dora (PT)", "pt-br:"), ("Alpha (HI)", "hi:"),
])
def test_engine_tach_am_espeak_theo_ngon_ngu_cua_giong(engine, giong, mong_doi):
    engine.infer("Hello there.", voice=giong)
    text, _, _, is_phonemes = engine.kokoro.calls[-1]
    assert text.startswith(mong_doi)
    assert is_phonemes is True


def test_engine_bo_co_doi_ngon_ngu_cua_espeak(engine):
    engine.infer("Bonjour voice.", voice="Siwis (FR)")
    assert "(en)" not in _cuoi(engine) and "(fr)" not in _cuoi(engine)


def test_engine_tieng_nhat_trung_dung_misaki(engine):
    engine.infer("こんにちは。", voice="Alpha (JA)")
    assert _cuoi(engine) == "ja<こんにちは。>"
    engine.infer("你好。", voice="Xiaoxiao (ZH)")
    assert _cuoi(engine) == "zh<你好。>"


def test_engine_chu_latin_trong_cau_trung_doc_bang_tieng_anh(engine):
    # misaki v1.0 giữ nguyên chữ Latin, mô hình sẽ bỏ qua -> "CIT" biến mất.
    engine.infer("欢迎使用CIT语音。", voice="Xiaoxiao (ZH)")
    assert _cuoi(engine) == "zh<欢迎使用> en-us:CIT zh<语音。>"


def test_engine_bo_the_cam_xuc_thay_vi_doc_to_len(engine):
    engine.infer("Great news [cười] for everyone.", voice="Heart")
    text = _cuoi(engine)
    assert "[" not in text and "cười" not in text
    assert "Great news" in text and "for everyone." in text


def test_engine_van_ban_rong_tra_ve_mang_rong_khong_goi_mo_hinh(engine):
    out = engine.infer("  [cười]  ", voice="Heart")
    assert out.size == 0
    assert engine.kokoro.calls == []


def test_engine_giong_khong_ton_tai_bao_loi(engine):
    with pytest.raises(ValueError):
        engine.infer("Hi.", voice="Minh Đức")


@pytest.mark.parametrize("giong, van_ban, so_cau", [
    ("Heart", "One. Two is here! Three?", 3),
    ("Alpha (JA)", "一つ。二つ！三つ？", 3),     # không có khoảng trắng sau dấu câu
    ("Alpha (HI)", "एक। दो।", 2),
])
def test_engine_stream_theo_tung_cau(engine, giong, van_ban, so_cau):
    chunks = list(engine.infer_stream(van_ban, voice=giong))
    assert len(chunks) == so_cau
    assert all(c.dtype == np.float32 for c in chunks)


def test_engine_ghi_file_giong_mot_lan_roi_dung_lai(engine, tmp_path):
    npz = Path(engine.kokoro.voices_path)
    assert npz.exists() and npz.parent == tmp_path / "cache"
    with np.load(npz) as z:
        assert set(z.files) == set(GIONG)


def test_nap_lai_voi_bo_giong_khac_khong_ghi_de_file_dang_mo(engine, tmp_path):
    """kokoro_onnx giữ file .npz mở; Windows không cho ghi đè -> WinError 5 khi
    nạp lại sau lúc cài gói tiếng Nhật (đo thật trên máy dev)."""
    from apps import kokoro_engine as ke

    cu = Path(engine.kokoro.voices_path)
    with np.load(cu):   # giữ mở như kokoro_onnx
        moi = ke.KokoroTTS(tmp_path / "model.onnx", tmp_path / "voices",
                           cache_dir=tmp_path / "cache", languages={"en"})
        assert Path(moi.kokoro.voices_path) != cu
    with np.load(moi.kokoro.voices_path) as z:
        assert all(k[0] in "ab" for k in z.files)


def test_engine_khong_ho_tro_nhan_ban(engine):
    assert not hasattr(engine, "add_voice")
    assert engine.sample_rate == 24_000


# ---------------------------------------------------------------------------
# Trình tải: tải file xong thì cài bộ tách âm, trước khi áp dụng
# ---------------------------------------------------------------------------

def test_tai_kokoro_cai_thu_vien_truoc_khi_ap_dung():
    from apps import kokoro_installer
    from apps import model_downloader as md

    thu_tu = []

    class _Info:
        sha = "abc"
        siblings = [type("S", (), {"rfilename": "onnx/model.onnx", "size": 10})()]

    with patch.object(md, "_model_info", return_value=_Info()), \
         patch.object(md, "_snapshot_download"), \
         patch.object(md, "_du_cho_trong_o", return_value=(True, "")), \
         patch.object(kokoro_installer, "install_deps",
                      side_effect=lambda **kw: (thu_tu.append("cai"), kw["on_progress"]("x"))), \
         patch.object(md, "_can_tu_cai_gpu_deps", return_value=False):
        md._chay(mc.get(KOKORO_ID), auto_apply=True, apply_fn=lambda _id: thu_tu.append("ap_dung"))

    assert thu_tu == ["cai", "ap_dung"]
    assert md.get_state()["state"] == "ready"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@pytest.fixture
def ws():
    import apps.web_stream as _ws

    return _ws


def test_mo_ta_model_kokoro_bao_can_cai_thu_vien(ws):
    from apps import kokoro_installer

    with patch.object(mc, "is_downloaded", return_value=True), \
         patch.object(kokoro_installer, "available", return_value=True), \
         patch.object(kokoro_installer, "deps_ready", return_value=False):
        d = ws._mo_ta_model(mc.get(KOKORO_ID), has_torch=False, has_cuda=False)
    assert d["compatible"] is True
    assert d["needs_addon_setup"] is True
    assert d["supports_cloning"] is False


def test_health_bao_kha_nang_cua_mo_hinh_dang_dung(ws, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(ws, "vieneu", Mock(spec=["infer", "list_preset_voices"]))
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", dict(KOKORO_INFO))
    d = TestClient(ws.app).get("/health").json()
    assert [x["code"] for x in d["languages"]] == ["en", "fr", "ja"]
    assert d["supports_emotions"] is False
    assert d["supports_seed"] is False        # đọc lần nào cũng như nhau: ẩn "Ổn định"
    assert d["supports_cloning"] is False     # engine không có add_voice


def test_health_vieneu_van_bao_co_cam_xuc(ws, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)"})
    d = TestClient(ws.app).get("/health").json()
    assert d["supports_emotions"] is True
    assert d["supports_seed"] is True


def test_language_cua_api_chuyen_thang_cho_kokoro(ws, monkeypatch):
    monkeypatch.setattr(ws, "current_model_info", dict(KOKORO_INFO))
    assert ws._language_kwargs("fr") == {"lang": "fr"}
    assert ws._language_kwargs(None) == {}
    with pytest.raises(ws.HTTPException) as e:
        ws._language_kwargs("vi")
    assert e.value.status_code == 400


def _kokoro_dang_chay(ws, monkeypatch):
    engine = Mock(spec=["infer", "list_preset_voices", "_preset_voices"])
    engine._preset_voices = {"Heart": {"language": "en"}}
    engine.infer.return_value = np.full(2400, 0.1, dtype=np.float32)
    monkeypatch.setattr(ws, "vieneu", engine)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", dict(KOKORO_INFO))
    return engine


@pytest.mark.parametrize("path, body", [
    ("/api/tts/generate", {"text": "Xin chào các bạn, hôm nay trời đẹp quá."}),
    ("/api/tts/generate-with-subtitles", {"text": "Xin chào các bạn, hôm nay trời đẹp quá."}),
    ("/api/tts/conversation", {"turns": [
        {"speaker": "A", "voice_id": "Heart", "text": "Hello there."},
        {"speaker": "B", "voice_id": "Heart", "text": "Chúng tôi đang thử nghiệm."}]}),
])
def test_kokoro_tu_choi_van_ban_tieng_viet_thay_vi_doc_sai(ws, monkeypatch, path, body):
    from fastapi.testclient import TestClient

    engine = _kokoro_dang_chay(ws, monkeypatch)
    r = TestClient(ws.app).post(path, json=body)
    assert r.status_code == 400
    assert "tiếng Việt" in r.json()["detail"]
    engine.infer.assert_not_called()


def test_kokoro_stream_tu_choi_tieng_viet_truoc_khi_gui_luong(ws, monkeypatch):
    from fastapi.testclient import TestClient

    _kokoro_dang_chay(ws, monkeypatch)
    r = TestClient(ws.app).get("/stream", params={"text": "Xin chào, đây là giọng đọc thử."})
    assert r.status_code == 400


@pytest.mark.parametrize("text", [
    "Hello, my name is Đăng.",                         # một tên riêng tiếng Việt
    "We flew from Hà Nội to Đà Nẵng.",                  # nhiều địa danh Việt trong câu Anh
    "Nous avons visité Hà Nội, Đà Nẵng et Huế.",        # ... trong câu Pháp
    "Bonjour, ça va? Très bien, à bientôt!",            # dấu tiếng Pháp
    "Olá, você está bem? Não, obrigação.",              # dấu tiếng Bồ Đào Nha
    "Wait [nghỉ 1s] [nghỉ 2s] [nghỉ 1s] ok [cười].",    # chữ trong thẻ không tính
])
def test_kokoro_van_doc_ngoai_ngu_co_dau(ws, monkeypatch, text):
    from fastapi.testclient import TestClient

    engine = _kokoro_dang_chay(ws, monkeypatch)
    r = TestClient(ws.app).post("/api/tts/generate", json={"text": text})
    assert r.status_code == 200, r.text
    engine.infer.assert_called()


def test_vieneu_va_supertonic_khong_bi_kiem_tra_ngon_ngu(ws, monkeypatch):
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)"})
    ws._require_language("Xin chào các bạn, hôm nay trời đẹp quá.")   # không ném lỗi
    # Supertonic liệt kê "vi" nên vẫn nhận tiếng Việt.
    monkeypatch.setattr(ws, "current_model_info", {
        "name": mc.SUPERTONIC_ID, "languages": [{"code": "en", "name": "x"}, {"code": "vi", "name": "y"}]})
    ws._require_language("Xin chào các bạn, hôm nay trời đẹp quá.")


def test_cau_nghe_thu_theo_ngon_ngu_dang_chon_hoac_cua_giong(ws, monkeypatch):
    from apps import kokoro_engine as ke

    monkeypatch.setattr(ws, "vieneu", types.SimpleNamespace(_preset_voices={
        "Alpha (JA)": {"language": "ja"}, "Heart": {"language": "en"}}))
    monkeypatch.setattr(ws, "current_model_info", dict(KOKORO_INFO))
    # Kokoro: luôn câu mẫu bằng tiếng của giọng, dù giao diện đang chọn tiếng khác -
    # engine đọc theo tiếng của giọng, câu tiếng Pháp cho giọng Nhật chỉ ra âm vô nghĩa.
    assert ws._preview_text(None, "Alpha (JA)") == (ke.PREVIEW_TEXTS["ja"], {"lang": "ja"})
    assert ws._preview_text("fr", "Alpha (JA)") == (ke.PREVIEW_TEXTS["ja"], {"lang": "ja"})
    assert ws._preview_text("zh", "Heart") == (ke.PREVIEW_TEXTS["en"], {"lang": "en"})
    # Câu mẫu nằm trong khoá cache: giọng Nhật không dùng lại file mẫu tiếng Pháp cũ.
    assert (ws._voice_preview_path("Alpha (JA)", ke.PREVIEW_TEXTS["ja"])
            != ws._voice_preview_path("Alpha (JA)", ke.PREVIEW_TEXTS["fr"]))
    # Supertonic vẫn đọc câu mẫu bằng ngôn ngữ đang chọn.
    monkeypatch.setattr(ws, "current_model_info", {
        "name": mc.SUPERTONIC_ID, "languages": [{"code": "en", "name": "x"}, {"code": "fr", "name": "y"}]})
    from apps import supertonic_engine as se
    assert ws._preview_text("fr", "Heart") == (se.PREVIEW_TEXTS["fr"], {"lang": "fr"})
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)"})
    assert ws._preview_text("en", "Minh Đức") == (ws.VOICE_PREVIEW_TEXT, {})


def test_danh_sach_giong_kem_ngon_ngu_va_vung(ws, monkeypatch):
    from fastapi.testclient import TestClient

    presets = {
        "Heart": {"gender": "female", "language": "en", "description": "Nữ · Kokoro · Tiếng Anh (Mỹ)"},
        "Alpha (JA)": {"gender": "female", "language": "ja", "description": "Nữ · Kokoro · Tiếng Nhật"},
    }
    fake = Mock(spec=["list_preset_voices", "_preset_voices"])
    fake._preset_voices = presets
    fake.list_preset_voices.return_value = [(f"{k} — x", k) for k in presets]
    monkeypatch.setattr(ws, "vieneu", fake)
    monkeypatch.setattr(ws, "model_status", {"state": "ok", "message": "Sẵn sàng"})
    monkeypatch.setattr(ws, "current_model_info", dict(KOKORO_INFO))
    body = TestClient(ws.app).get("/voices").json()
    voices = {v["id"]: v for v in (body["voices"] if isinstance(body, dict) else body)}
    assert (voices["Heart"]["language"], voices["Heart"]["region"]) == ("en", None)
    assert (voices["Alpha (JA)"]["language"], voices["Alpha (JA)"]["region"]) == ("ja", None)
    assert voices["Heart"]["gender"] == "female"
    assert voices["Heart"]["description"] == "Nữ · Kokoro · Tiếng Anh (Mỹ) · 24 kHz"


def test_tu_dien_phat_am_tieng_viet_khong_ap_len_kokoro(ws, monkeypatch):
    """Từ điển viết cách đọc bằng chính tả tiếng Việt ("CIT" -> "cường ai ti"): đưa
    cho Kokoro thì nó đọc thành tiếng lạ. Đo thật trên máy dev trước khi sửa."""
    from apps import pronunciation_settings

    monkeypatch.setattr(pronunciation_settings, "apply", lambda t: t.replace("CIT", "cường ai ti"))
    doc = []
    infer = lambda seg: (doc.append(seg), np.ones(10, dtype=np.float32))[1]

    monkeypatch.setattr(ws, "current_model_info", dict(KOKORO_INFO))
    ws._synthesize("Welcome to CIT.", 24_000, infer)
    ws._synthesize_with_cues("Welcome to CIT.", 24_000, infer)
    assert doc and all("CIT" in s and "cường" not in s for s in doc)

    doc.clear()
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)"})
    ws._synthesize("Chào CIT.", 48_000, infer)
    assert "cường ai ti" in doc[0]


# ---------------------------------------------------------------------------
# Phụ đề: câu Nhật/Trung/Hindi (giọng Kokoro)
# ---------------------------------------------------------------------------

def test_phu_de_tach_cau_nhat_trung_khong_can_khoang_trang():
    from vieneu_utils.subtitles import build_units

    units = [u.text for u in build_units("一つ目の文です。二つ目の文です。三つ目はもう少し長い文にしてみました。")]
    # Câu ngắn vẫn gộp (chống ảo giác như tiếng Việt), nhưng không chèn dấu cách.
    assert units == ["一つ目の文です。二つ目の文です。", "三つ目はもう少し長い文にしてみました。"]
    assert len(build_units("你好。欢迎使用我们的软件。这是第二句话，比较长一些，对吧？")) == 2


def test_phu_de_tieng_viet_khong_doi():
    from vieneu_utils.subtitles import build_units

    units = [u.text for u in build_units("Xin chào các bạn. Hôm nay trời đẹp quá! Chúng ta đi chơi nhé?")]
    assert units == ["Xin chào các bạn. Hôm nay trời đẹp quá!", "Chúng ta đi chơi nhé?"]


# ---------------------------------------------------------------------------
# Gói ngôn ngữ tải thêm (Nhật, Trung)
# ---------------------------------------------------------------------------

def test_engine_chi_hien_giong_cua_ngon_ngu_da_cai(engine, tmp_path):
    from apps import kokoro_engine as ke

    # File giọng Nhật/Trung có sẵn (vd. tải dở) mà chưa cài bộ tách âm: không hiện.
    e = ke.KokoroTTS(tmp_path / "model.onnx", tmp_path / "voices", cache_dir=tmp_path / "c2",
                     languages={"en", "fr"})
    langs = {v["language"] for v in e._preset_voices.values()}
    assert langs == {"en", "fr"}
    with pytest.raises(ValueError):
        e.infer("こんにちは", voice="jf_alpha")


def test_tai_goi_sai_mo_hinh_hoac_sai_ma_bi_tu_choi():
    from apps import model_downloader as md

    ok, ly_do = md.start("VieNeu-TTS-v3-Turbo (int8)", pack="ja")
    assert ok is False and "gói ngôn ngữ" in ly_do
    ok, _ = md.start(KOKORO_ID, pack="fr")
    assert ok is False


def test_tai_goi_tai_giong_theo_sha_dang_co_roi_cai_roi_nap_lai():
    from apps import kokoro_installer
    from apps import model_downloader as md

    thu_tu, tai = [], {}

    class _Info:
        siblings = [type("S", (), {"rfilename": "voices/jf_alpha.bin", "size": 500})(),
                    type("S", (), {"rfilename": "voices/af_heart.bin", "size": 999})()]

    def snapshot(**kw):
        tai.update(kw)
        thu_tu.append("tai")

    with patch.object(mc, "is_downloaded", return_value=True), \
         patch.object(md, "_model_info", return_value=_Info()) as info, \
         patch.object(md, "_snapshot_download", side_effect=snapshot), \
         patch.object(kokoro_installer, "install_pack",
                      side_effect=lambda code, **kw: thu_tu.append(f"cai:{code}")):
        md._chay_pack(mc.get(KOKORO_ID), mc.kokoro_pack("ja"), True,
                      lambda _id: thu_tu.append("nap_lai"))

    assert thu_tu == ["tai", "cai:ja", "nap_lai"]
    # Đúng sha ghim của mô hình: giọng nằm chung snapshot, không ghi đè refs/main.
    assert tai["revision"] == mc.KOKORO_REVISION == info.call_args.kwargs["revision"]
    assert tai["set_main_ref"] is False
    assert tai["allow_patterns"] == ["voices/jf_*.bin", "voices/jm_*.bin"]
    st = md.get_state()
    assert st["state"] == "ready" and st["pack"] == "ja" and st["total_bytes"] == 500


def test_tai_goi_khi_chua_co_kokoro_bao_loi():
    from apps import model_downloader as md

    with patch.object(mc, "is_downloaded", return_value=False):
        md._chay_pack(mc.get(KOKORO_ID), mc.kokoro_pack("zh"), True, None)
    st = md.get_state()
    assert st["state"] == "error" and "Kokoro trước" in st["message"]


def test_mo_ta_model_kokoro_liet_ke_goi_ngon_ngu(ws):
    from apps import kokoro_installer

    with patch.object(mc, "is_downloaded", return_value=True), \
         patch.object(mc, "kokoro_pack_downloaded", side_effect=lambda p: p.code == "ja"), \
         patch.object(kokoro_installer, "available", return_value=True), \
         patch.object(kokoro_installer, "deps_ready", return_value=True), \
         patch.object(kokoro_installer, "pack_ready", return_value=True):
        d = ws._mo_ta_model(mc.get(KOKORO_ID), has_torch=False, has_cuda=False)
        khac = ws._mo_ta_model(mc.get("VieNeu-TTS-v3-Turbo (int8)"), has_torch=False, has_cuda=False)
    goi = {g["code"]: g for g in d["packs"]}
    assert goi["ja"]["installed"] is True       # đủ cả giọng lẫn bộ tách âm
    assert goi["zh"]["installed"] is False      # thiếu file giọng
    assert goi["ja"]["approx_bytes"] > 0 and goi["ja"]["name"] == "Tiếng Nhật"
    assert khac["packs"] == []


def test_cai_goi_xong_chi_nap_lai_khi_dang_dung_kokoro(ws, monkeypatch):
    goi = []
    monkeypatch.setattr(ws, "load_model_instance", lambda name, *a: goi.append(name))
    monkeypatch.setattr(ws, "current_model_info", {"name": "VieNeu-TTS-v3-Turbo (int8)"})
    ws._reload_kokoro_if_current(KOKORO_ID)
    assert goi == []   # đang dùng VieNeu: không tự đổi mô hình của người dùng
    monkeypatch.setattr(ws, "current_model_info", {"name": KOKORO_ID})
    ws._reload_kokoro_if_current(KOKORO_ID)
    assert goi == [KOKORO_ID]


# ---------------------------------------------------------------------------
# Kokoro GPU (PyTorch trên CUDA)
# ---------------------------------------------------------------------------

def test_kokoro_gpu_trong_catalog():
    spec = mc.get(mc.KOKORO_GPU_ID)
    assert spec is not None and mc.is_kokoro(spec.id)
    assert set(spec.requires) == {"torch", "cuda", "kokoro_deps"}
    assert (spec.device, spec.sample_rate) == ("cuda", 24_000)
    assert spec.supports_cloning is False
    nguon = {src.repo: src for src in spec.sources}
    assert "kokoro-v1_0.pth" in nguon[mc.KOKORO_TORCH_REPO].allow_patterns
    # Giọng lấy chung KOKORO_REPO để gói ngôn ngữ dùng được cho cả hai bản,
    # nhưng không kéo 330 MB bản ONNX về máy GPU.
    giong = nguon[mc.KOKORO_REPO].allow_patterns
    assert giong and all(g.startswith("voices/") for g in giong)
    assert not any(g.startswith(("voices/j", "voices/z")) for g in giong)


def test_kokoro_gpu_can_gpu_va_thu_vien():
    spec = mc.get(mc.KOKORO_GPU_ID)
    ok, _ = mc.compatible(spec, has_torch=True, has_cuda=False, has_kokoro_deps=True)
    assert ok is False
    ok, _ = mc.compatible(spec, has_torch=True, has_cuda=True, has_kokoro_deps=True)
    assert ok is True


def test_engine_chon_pytorch_khi_co_config(tmp_path, monkeypatch):
    from apps import kokoro_engine as ke

    voices = tmp_path / "voices"
    voices.mkdir()
    np.zeros((510, 1, 256), dtype=np.float32).tofile(voices / "af_heart.bin")
    fake = types.ModuleType("kokoro_onnx")
    fake.Kokoro = _KokoroGia
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake)
    goi = []
    monkeypatch.setattr(ke, "_torch_kokoro", lambda *a: (goi.append(a), _KokoroGia())[1])
    e = ke.KokoroTTS(tmp_path / "kokoro-v1_0.pth", voices, cache_dir=tmp_path / "c",
                     torch_config=tmp_path / "config.json", device="cuda")
    assert (e.backend, e.device) == ("pytorch", "cuda")
    cfg, weights, npz, device = goi[0]
    assert (cfg.name, weights.name, device) == ("config.json", "kokoro-v1_0.pth", "cuda")
    assert e.infer("Hello.", voice="Heart").size > 0


def test_torch_kokoro_chi_thay_buoc_suy_luan(tmp_path, monkeypatch):
    """Lớp con giữ tách âm/chia lô của kokoro_onnx, chỉ đổi _infer sang KModel.

    torch giả của riêng test: test khác trong bộ thay torch bằng MagicMock trong
    sys.modules, nên dựa vào torch thật thì lỗi khi chạy cả bộ."""
    from apps import kokoro_engine as ke

    class _T:
        """Tensor giả bọc numpy, đủ các phép engine gọi."""

        def __init__(self, a):
            self.a = np.asarray(a)
            self.shape = self.a.shape

        def to(self, _device):
            return self

        def float(self):
            return _T(self.a.astype(np.float32))

        def cpu(self):
            return self

        def numpy(self):
            return self.a

        def tolist(self):
            return self.a.tolist()

    torch = types.ModuleType("torch")
    torch.long = "long"
    torch.tensor = lambda data, dtype=None, device=None: _T(data)
    torch.from_numpy = _T
    torch.ones = lambda n: _T(np.ones(n, dtype=np.float32))
    monkeypatch.setitem(sys.modules, "torch", torch)

    class _KokoroGoc:
        pass

    class _Tok:
        def __init__(self, espeak_config=None, vocab=None):
            self.vocab = vocab

    fake = types.ModuleType("kokoro_onnx")
    fake.Kokoro = _KokoroGoc
    tok = types.ModuleType("kokoro_onnx.tokenizer")
    tok.Tokenizer = _Tok
    monkeypatch.setitem(sys.modules, "kokoro_onnx", fake)
    monkeypatch.setitem(sys.modules, "kokoro_onnx.tokenizer", tok)

    nhan = {}

    class _KModelGia:
        vocab = {".": 4, " ": 16, "a": 43}

        def __init__(self, config, weights):
            nhan["files"] = (config, weights)

        def to(self, device):
            nhan["device"] = device
            return self

        def eval(self):
            return self

        def forward_with_tokens(self, ids, ref, speed):
            nhan.update(ids=ids.tolist(), ref=tuple(ref.shape), speed=speed)
            return torch.ones(1200), torch.tensor([1, 2, 1])

    mod = types.ModuleType("apps._kokoro_torch.model")
    mod.KModel = _KModelGia
    monkeypatch.setitem(sys.modules, "apps._kokoro_torch.model", mod)

    npz = tmp_path / "v.npz"
    np.savez(npz, af_heart=np.zeros((510, 1, 256), dtype=np.float32))
    k = ke._torch_kokoro(tmp_path / "config.json", tmp_path / "w.pth", npz, "cpu")
    assert isinstance(k, _KokoroGoc) and k.has_timings is True
    assert k._stops == frozenset({4}) and k._spaces == frozenset({16})
    audio, dur = k._infer([43, 43], np.zeros((1, 256), dtype=np.float32), 1.25)
    assert nhan["ids"] == [[0, 43, 43, 0]]      # đệm 0 hai đầu như bản ONNX
    assert nhan["ref"] == (1, 256) and nhan["speed"] == 1.25 and nhan["device"] == "cpu"
    assert audio.dtype == np.float32 and audio.shape == (1200,) and list(dur) == [1, 2, 1]


def test_nap_kokoro_gpu_khi_khong_co_cuda_bao_loi_tieng_viet(ws, monkeypatch):
    from apps import kokoro_installer

    monkeypatch.setattr(kokoro_installer, "activate", lambda: True)
    monkeypatch.setattr(ws, "cuda_is_available", lambda: False)
    with pytest.raises(RuntimeError, match="GPU NVIDIA"):
        ws._load_kokoro(gpu=True)


def test_nap_kokoro_gpu_ghi_dung_thong_tin_mo_hinh(ws, monkeypatch):
    goi = []
    monkeypatch.setattr(ws, "_load_kokoro", lambda gpu=False: (
        goi.append(gpu), types.SimpleNamespace(backend="pytorch", device="cuda", sample_rate=24_000,
                                               languages={"en": "Tiếng Anh"}))[1])
    monkeypatch.setattr(ws, "gpu_name", lambda: "RTX Giả")
    monkeypatch.setattr(ws, "current_model_info", {})
    monkeypatch.setattr(ws, "vieneu", None)
    ws.load_model_instance(mc.KOKORO_GPU_ID)
    info = ws.current_model_info
    assert goi == [True]   # không lọt vào nhánh v3 Turbo GPU dù tên có chữ "GPU"
    assert (info["name"], info["backend"], info["device"]) == (mc.KOKORO_GPU_ID, "pytorch", "cuda")
    assert info["gpu_name"] == "RTX Giả" and info["supports_emotions"] is False
    assert info["supports_seed"] is False
    assert info["languages"] == [{"code": "en", "name": "Tiếng Anh"}]


def test_goi_ngon_ngu_dung_duoc_cho_kokoro_gpu(ws, monkeypatch):
    from apps import model_downloader as md

    monkeypatch.setattr(md, "_chay_pack", lambda *a: None)
    ok, ly_do = md.start(mc.KOKORO_GPU_ID, pack="ja")
    assert ok is True, ly_do
    goi = []
    monkeypatch.setattr(ws, "load_model_instance", lambda name, *a: goi.append(name))
    monkeypatch.setattr(ws, "current_model_info", {"name": mc.KOKORO_GPU_ID})
    ws._reload_kokoro_if_current(mc.KOKORO_GPU_ID)
    assert goi == [mc.KOKORO_GPU_ID]



def test_kokoro_ghim_revision():
    """Người dùng mới phải tải đúng bản đã test, không phải `main` mới nhất của repo."""
    for model_id in mc.KOKORO_IDS:
        for src in mc.get(model_id).sources:
            assert src.revision and len(src.revision) == 40, (model_id, src.repo)


# ---------------------------------------------------------------------------
# Rà soát: nhận diện tiếng Việt, khoá tách âm, bảo mật bộ cài, venv mất Python gốc
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, la_tieng_viet", [
    ("Xin chào các bạn", True),
    ("Chào bạn", True),
    ("Cảm ơn", True),
    ("XIN CHÀO CÁC BẠN", True),
    ("Hôm nay trời đẹp quá, chúng ta đi chơi nhé.", True),
    ("We flew from Hà Nội to Đà Nẵng.", False),
    ("Bonjour, je suis à Hà Nội avec Nguyễn Văn Đức.", False),
    ("I love phở and bánh mì.", False),
    ("Hello world.", False),
])
def test_nhan_dien_tieng_viet_theo_ti_le_tu(ws, text, la_tieng_viet):
    assert ws._looks_vietnamese(text) is la_tieng_viet


def test_tach_am_nhat_khong_goi_dong_thoi_cung_mot_tagger(engine):
    import threading
    import time

    dang_chay, chong_cheo = [0], []

    def g2p(text):
        dang_chay[0] += 1
        if dang_chay[0] > 1:
            chong_cheo.append(text)
        time.sleep(0.01)
        dang_chay[0] -= 1
        return (f"ja<{text}>", None)

    engine._g2p["ja"] = g2p
    luong = [threading.Thread(target=engine.infer, args=(f"こんにちは{i}です",),
                              kwargs={"voice": "Alpha (JA)"}) for i in range(6)]
    for t in luong:
        t.start()
    for t in luong:
        t.join()
    assert chong_cheo == []


def test_stream_giu_ngoac_dong_cung_cau(engine):
    from apps import kokoro_engine as ke

    assert [s for s in ke._SENTENCE_RE.split("「こんにちは。」と言った。次です！") if s] == [
        "「こんにちは。」", "と言った。", "次です！"]


def test_khoa_bo_tach_am_khop_danh_sach_goi_va_co_ma_bam():
    import re as _re

    from apps import kokoro_installer as ki
    from apps import kokoro_locks

    def ghim(lock):
        return {ln.split()[0] for ln in lock.splitlines() if "==" in ln}

    assert ghim(kokoro_locks.BASE_LOCK) == set(ki.BASE_PACKAGES)
    for code, goi in ki.PACK_PACKAGES.items():
        assert ghim(kokoro_locks.PACK_LOCKS[code]) == set(goi)
    for lock in (kokoro_locks.BASE_LOCK, *kokoro_locks.PACK_LOCKS.values()):
        # Mỗi gói ít nhất một mã băm sha256 (định dạng `uv pip compile --generate-hashes`).
        for khoi in _re.split(r"\n(?=\S)", lock.strip()):
            assert _re.search(r"--hash=sha256:[0-9a-f]{64}", khoi), khoi


def test_cai_kokoro_bo_bien_moi_truong_uv_pip_cua_may(monkeypatch):
    from apps import gpu_installer
    from apps import kokoro_installer as ki

    moi_truong = {}

    class _Popen:
        returncode = 0

        def __init__(self, args, **kw):
            moi_truong.update(kw["env"])
            self.pid = 1

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr(gpu_installer.subprocess, "Popen", _Popen)
    monkeypatch.setenv("UV_EXTRA_INDEX_URL", "https://evil.example/simple")
    monkeypatch.setenv("PIP_INDEX_URL", "https://evil.example/simple")
    monkeypatch.setenv("uv_find_links", "https://evil.example/links")
    ki._runner(lambda: None)(["uv", "pip", "install"])
    assert not any(k.upper().startswith(("UV_", "PIP_")) and k not in (
        "UV_NO_PROGRESS", "UV_NO_CONFIG", "UV_CACHE_DIR", "UV_PYTHON_INSTALL_DIR") for k in moi_truong)
    assert moi_truong["UV_NO_CONFIG"] == "1"

    # Bộ cài GPU giữ nguyên hành vi cũ.
    moi_truong.clear()
    gpu_installer._run(["uv"], lambda: None)
    assert moi_truong["UV_EXTRA_INDEX_URL"] == "https://evil.example/simple"


@pytest.mark.parametrize("path, body", [
    ("/api/models/download", {"model_id": KOKORO_ID}),
    ("/api/models/download", {"model_id": KOKORO_ID, "pack": "ja"}),
    ("/api/models/download/cancel", None),
    ("/api/models/load", {"model_name": KOKORO_ID}),
])
def test_trang_web_la_khong_kich_hoat_duoc_tai_cai_mo_hinh(ws, monkeypatch, path, body):
    from fastapi.testclient import TestClient

    start = Mock(return_value=(True, ""))
    load = Mock()
    monkeypatch.setattr(ws.model_downloader, "start", start)
    monkeypatch.setattr(ws.model_downloader, "cancel", Mock(return_value=True))
    monkeypatch.setattr(ws, "load_model_instance", load)
    client = TestClient(ws.app, base_url="http://127.0.0.1:8001")

    # Trang lạ (CORS "*" cho nó gửi được) và DNS rebinding (Host lạ): 403, không làm gì.
    assert client.post(path, json=body, headers={"Origin": "https://evil.example"}).status_code == 403
    lan = TestClient(ws.app, base_url="http://evil.example")
    assert lan.post(path, json=body).status_code == 403
    start.assert_not_called()
    load.assert_not_called()

    # Giao diện của app: cùng gốc, hoặc Vite dev (localhost:1420).
    for origin in (None, "http://127.0.0.1:8001", "http://localhost:1420"):
        headers = {"Origin": origin} if origin else {}
        assert client.post(path, json=body, headers=headers).status_code in (200, 202)


def test_venv_mat_python_goc_thi_bao_chua_cai_va_dung_lai(ki, monkeypatch, tmp_path):
    import shutil as _shutil

    from apps import gpu_installer

    lenh = []
    _gia_cai(ki, monkeypatch, tmp_path, lenh)
    ki.install_deps()
    assert ki.deps_ready() is True

    # Người dùng xoá gpu_venv (chứa Python gốc mà venv mượn).
    home = gpu_installer._venv_home(ki.venv_dir())
    _shutil.rmtree(home)
    assert ki.deps_ready() is False
    assert ki.activate() is False

    lenh.clear()
    (ki.venv_dir() / "rac-cua-venv-cu.txt").write_text("x")
    ki.install_deps()
    # Venv cũ bị xoá và dựng lại từ Python gốc mới, không chỉ cài đè.
    assert any(c[1:2] == ["venv"] for c in lenh)
    assert not (ki.venv_dir() / "rac-cua-venv-cu.txt").exists()
    assert ki.deps_ready() is True


def test_venv_mat_site_packages_thi_bao_chua_cai(ki):
    import shutil as _shutil

    venv, site = _venv_gia(ki)
    (venv / ki._MARKER_NAME).write_text(ki._marker_value(), encoding="utf-8")
    assert ki.deps_ready() is True
    _shutil.rmtree(site)
    assert ki.deps_ready() is False


def test_kokoro_khong_ho_tro_macos(ki, monkeypatch):
    from apps import gpu_installer

    monkeypatch.setattr(gpu_installer, "find_uv", lambda: "uv")
    monkeypatch.setattr(sys, "platform", "darwin")
    assert ki.available() is False
    ok, ly_do = mc.compatible(mc.get(KOKORO_ID), has_torch=False, has_cuda=False,
                              has_kokoro_deps=ki.available())
    assert ok is False
    assert "macOS" in ly_do and "cập nhật" not in ly_do


def test_khoi_van_ban_dai_tieng_nhat_duoc_chia_theo_cau(ws):
    cau = "今日はとても良い天気ですね。"
    text = cau * 400                       # ~5600 ký tự, không có dấu câu Latin nào
    blocks = ws._text_blocks(text)
    assert len(blocks) > 1
    assert all(len(b) <= ws.LONG_TEXT_BLOCK_CHARS for b, _ in blocks)
    # Nối lại không chèn khoảng trắng giữa các câu Nhật, không mất chữ nào.
    assert "".join(b for b, _ in blocks) == text


def test_cai_goi_xong_nhung_nap_lai_hong_thi_bao_ro(monkeypatch):
    from apps import kokoro_installer
    from apps import model_downloader as md

    class _Info:
        siblings = [type("S", (), {"rfilename": "voices/jf_alpha.bin", "size": 500})()]

    def nap_lai(_id):
        raise RuntimeError("hết bộ nhớ")

    with patch.object(mc, "is_downloaded", return_value=True), \
         patch.object(md, "_model_info", return_value=_Info()), \
         patch.object(md, "_snapshot_download"), \
         patch.object(kokoro_installer, "install_pack"):
        md._chay_pack(mc.get(KOKORO_ID), mc.kokoro_pack("ja"), True, nap_lai)
    st = md.get_state()
    assert st["state"] == "error"
    assert "Đã cài xong tiếng Nhật" in st["message"] and "nạp lại" in st["message"]
    assert "hết bộ nhớ" in st["message"]


def test_phu_de_giu_ngoac_dong_cung_cau():
    from vieneu_utils.subtitles import _NON_LATIN_STOP, build_units

    # Cắt ngay sau 。 thì 」 đứng trơ trọi thành một đơn vị đọc riêng.
    assert [s for s in _NON_LATIN_STOP.split("「今日は。」次です。他说：“你好。”然后走了。") if s] == [
        "「今日は。」", "次です。", "他说：“你好。”", "然后走了。"]
    units = [u.text for u in build_units(
        "「今日はとても良い天気ですね、本当に。」「明日も晴れるでしょうか、どう思いますか？」")]
    assert units == ["「今日はとても良い天気ですね、本当に。」", "「明日も晴れるでしょうか、どう思いますか？」"]
    assert not any(u.strip() in ("」", "”") for u in units)
