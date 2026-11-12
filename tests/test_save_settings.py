"""Cài đặt lưu file của app desktop (người dùng góp ý: chọn thư mục lưu, mở file
sau khi lưu). Không mở cửa sổ thật: cửa sổ PyWebView và việc mở file được thay giả."""
import base64
from pathlib import Path

import pytest

from apps import desktop_app as desktop
from apps import save_settings as ss


@pytest.fixture(autouse=True)
def _cau_hinh_tam(tmp_path, monkeypatch):
    monkeypatch.setattr(ss, "settings_path", lambda: tmp_path / "cfg" / "save-settings.json")
    monkeypatch.setattr(ss, "default_folder", lambda: tmp_path / "Downloads")
    (tmp_path / "Downloads").mkdir()


@pytest.fixture
def opened(monkeypatch):
    calls = []
    monkeypatch.setattr(ss, "open_path", lambda path, reveal=False: calls.append((Path(path), reveal)))
    return calls


class _Window:
    def __init__(self, answer):
        self.answer, self.asked_dir = answer, None

    def create_file_dialog(self, dialog_type=None, directory=None, **_):
        self.asked_dir = directory
        return self.answer


def _api(window):
    api = desktop.DesktopApi()
    api.set_window(window)
    return api


B64 = base64.b64encode(b"RIFF....").decode()


# ---- Cấu hình ----

def test_mac_dinh_hoi_moi_lan_khong_tu_mo_luu_vao_downloads(tmp_path):
    assert ss.load() == {"folder": None, "ask": True, "open_after": False}
    assert ss.effective_folder() == tmp_path / "Downloads"


def test_thu_muc_khong_ton_tai_thi_tu_choi_va_thu_muc_bi_xoa_thi_ve_mac_dinh(tmp_path):
    with pytest.raises(ValueError):
        ss.save({"folder": str(tmp_path / "khong-co")})
    music = tmp_path / "Nhạc"
    music.mkdir()
    ss.save({"folder": str(music), "ask": False, "open_after": True})
    assert ss.effective_folder() == music.resolve()
    music.rmdir()                          # USB rút ra, thư mục bị xoá...
    assert ss.effective_folder() == tmp_path / "Downloads"


def test_cau_hinh_hong_thi_dung_mac_dinh():
    ss.settings_path().parent.mkdir(parents=True)
    ss.settings_path().write_text("không phải json", encoding="utf-8")
    assert ss.load() == ss.DEFAULTS
    ss.settings_path().write_text('{"ask": "có", "folder": 5}', encoding="utf-8")
    assert ss.load() == ss.DEFAULTS


def test_luu_thang_khong_ghi_de_file_da_co(tmp_path):
    d = tmp_path / "Downloads"
    (d / "bai.wav").write_bytes(b"cu")
    (d / "bai (1).wav").write_bytes(b"cu")
    assert ss.unique_path(d, "bai.wav") == d / "bai (2).wav"
    assert ss.unique_path(d, "moi.mp3") == d / "moi.mp3"


# ---- DesktopApi ----

def test_hoi_save_as_mo_san_o_thu_muc_da_chon(tmp_path, opened):
    music = tmp_path / "Nhac"
    music.mkdir()
    ss.save({"folder": str(music)})
    target = music / "chon.wav"
    win = _Window(str(target))
    res = _api(win).save_file("bai.wav", B64)
    assert win.asked_dir == str(music.resolve())
    assert res["success"] and res["path"] == str(target) and res["opened"] is False
    assert target.read_bytes() == b"RIFF...."
    assert opened == []


def test_tat_hoi_thi_luu_thang_khong_mo_hop_thoai(tmp_path, opened):
    music = tmp_path / "Nhac"
    music.mkdir()
    (music / "bai.wav").write_bytes(b"cu")
    ss.save({"folder": str(music), "ask": False})
    win = _Window(answer=None)
    res = _api(win).save_file("bai.wav", B64)
    assert win.asked_dir is None                       # không hiện hộp thoại
    assert res["path"] == str(music.resolve() / "bai (1).wav")
    assert (music / "bai.wav").read_bytes() == b"cu"   # file cũ còn nguyên


def test_bat_tu_mo_thi_mo_file_vua_luu(tmp_path, opened):
    ss.save({"ask": False, "open_after": True})
    res = _api(_Window(None)).save_file("bai.wav", B64)
    assert res["opened"] is True
    assert opened == [(Path(res["path"]), False)]


def test_huy_hop_thoai_thi_khong_luu(opened):
    res = _api(_Window(None)).save_file("bai.wav", B64)
    assert res == {"success": False, "cancelled": True}


def test_chi_mo_duoc_file_app_vua_luu(tmp_path, opened):
    api = _api(_Window(None))
    ss.save({"ask": False})
    res = api.save_file("bai.wav", B64)
    assert api.open_saved(res["path"], True)["success"]
    assert opened == [(Path(res["path"]), True)]
    # Đường dẫn tuỳ ý (vd. một file .exe) không được mở từ giao diện.
    la = tmp_path / "la.exe"
    la.write_bytes(b"")
    assert api.open_saved(str(la), False)["success"] is False
    assert len(opened) == 1


def test_mo_thu_muc_duong_dan_co_dau_cach_dung_cu_phap_explorer(monkeypatch):
    """Tên file có dấu cách ("Hải Đăng"): explorer chỉ hiểu `/select,"đường dẫn"`;
    truyền dạng list thì cả `/select,...` bị bọc ngoặc kép và explorer mở Documents."""
    calls = []
    monkeypatch.setattr(ss.sys, "platform", "win32")
    monkeypatch.setattr(ss.subprocess, "Popen", lambda cmd, *a, **k: calls.append(cmd))
    p = Path(r"C:\Users\A\Downloads\cit-tts\cit_tts_Hải Đăng_1.mp3")
    ss.open_path(p, reveal=True)
    assert calls == [f'explorer /select,"{p}"']


def test_dat_cai_dat_qua_api(tmp_path):
    api = _api(_Window(None))
    bad = api.set_save_settings({"folder": str(tmp_path / "khong-co")})
    assert bad["success"] is False and "Không tìm thấy" in bad["error"]
    ok = api.set_save_settings({"ask": False, "open_after": True})
    assert ok["success"] and ok["ask"] is False and ok["open_after"] is True
    assert ok["effective_folder"] == str(tmp_path / "Downloads")


def test_chon_thu_muc(tmp_path):
    win = _Window(str(tmp_path))
    assert _api(win).choose_save_folder() == {"success": True, "folder": str(tmp_path)}
    assert _api(_Window(None)).choose_save_folder()["cancelled"]
