"""Cửa sổ Desktop phải vừa và nằm giữa trên MỌI màn hình.

Lỗi thật đã gặp: cửa sổ đặt cứng 1200x800 và không truyền x/y, nên pywebview rơi
vào `FormStartPosition.CenterScreen` của WinForms — căn theo toàn bộ chiều cao màn
hình chứ không trừ taskbar. Trên máy 2560x1440 ở scale 175%, vùng làm việc chỉ còn
775 px logic cao, thấp hơn cả chiều cao cửa sổ, nên đáy cửa sổ chui xuống dưới
taskbar và người dùng thấy app "lệch xuống dưới".
"""
from __future__ import annotations

import pytest

from apps.desktop_app import WINDOW_MIN, fit_window_to_screen

# (ten, vung lam viec logic: x, y, rong, cao)
# Vung lam viec = do phan giai chia cho scale, tru taskbar.
SCREENS = [
    ("1366x768 @100%",          (0, 0, 1366, 728)),
    ("1440x900 @100%",          (0, 0, 1440, 860)),
    ("1920x1080 @100%",         (0, 0, 1920, 1040)),
    ("1920x1080 @125%",         (0, 0, 1536, 824)),
    ("1920x1080 @150%",         (0, 0, 1280, 688)),
    ("2560x1440 @175% (máy dev)", (0, 0, 1463, 775)),
    ("3840x2160 @200%",         (0, 0, 1920, 1040)),
    ("3840x2160 @150%",         (0, 0, 2560, 1400)),
    ("1024x768 @100% (máy cũ)",  (0, 0, 1024, 728)),
    ("taskbar bên trái",         (80, 0, 1840, 1080)),
    ("taskbar trên cùng",        (0, 48, 1920, 1032)),
    ("màn phụ bên phải",         (1920, 0, 1920, 1040)),
]


@pytest.mark.parametrize("name,work", SCREENS, ids=[s[0] for s in SCREENS])
def test_cua_so_nam_tron_trong_vung_lam_viec(name, work):
    wx, wy, ww, wh = work
    g = fit_window_to_screen(work)

    assert g["width"] <= ww, f"{name}: rộng hơn vùng làm việc"
    assert g["height"] <= wh, f"{name}: cao hơn vùng làm việc"
    assert g["x"] >= wx, f"{name}: tràn ra trái"
    assert g["y"] >= wy, f"{name}: tràn lên trên"
    assert g["x"] + g["width"] <= wx + ww, f"{name}: tràn ra phải"
    assert g["y"] + g["height"] <= wy + wh, f"{name}: tràn xuống dưới taskbar"


@pytest.mark.parametrize("name,work", SCREENS, ids=[s[0] for s in SCREENS])
def test_can_giua_vung_lam_viec(name, work):
    wx, wy, ww, wh = work
    g = fit_window_to_screen(work)
    # Lech toi da 1 px do chia lay nguyen.
    assert abs((g["x"] - wx) - (ww - g["width"] - (g["x"] - wx))) <= 1, f"{name}: lệch ngang"
    assert abs((g["y"] - wy) - (wh - g["height"] - (g["y"] - wy))) <= 1, f"{name}: lệch dọc"


@pytest.mark.parametrize("name,work", SCREENS, ids=[s[0] for s in SCREENS])
def test_min_size_khong_vuot_man_hinh(name, work):
    """min_size lớn hơn màn hình sẽ bị WinForms ép giữ, cửa sổ lại tràn ra ngoài."""
    _, _, ww, wh = work
    g = fit_window_to_screen(work)
    assert g["min_size"][0] <= ww, f"{name}: min_size rộng hơn màn hình"
    assert g["min_size"][1] <= wh, f"{name}: min_size cao hơn màn hình"
    assert g["min_size"][0] <= g["width"]
    assert g["min_size"][1] <= g["height"]


def test_man_hinh_rong_rai_giu_dung_kich_thuoc_mong_muon():
    g = fit_window_to_screen((0, 0, 1920, 1040))
    assert (g["width"], g["height"]) == (1120, 720)
    assert (g["x"], g["y"]) == (400, 160)


def test_man_hinh_cua_may_dev_bi_kep_lai():
    """775 px cao thì KHÔNG được trả về 800 như trước."""
    g = fit_window_to_screen((0, 0, 1463, 775))
    assert g["height"] <= 775
    assert g["height"] < 800


def test_man_hinh_te_hai_van_khong_vo():
    """Nhỏ hơn cả min_size — vẫn phải cho ra số hợp lệ, không âm, không tràn."""
    g = fit_window_to_screen((0, 0, 640, 480))
    assert 0 < g["width"] <= 640
    assert 0 < g["height"] <= 480
    assert g["x"] >= 0 and g["y"] >= 0
    assert g["min_size"] <= (640, 480)


def test_mac_dinh_van_la_kich_thuoc_mong_muon():
    assert WINDOW_MIN == (800, 500)
