"""Tự cập nhật trên Windows: chọn đúng bộ cài, tải + kiểm tra sha256, chạy bộ cài im lặng.

Không chạm mạng: vá ``urlopen``; không chạy bộ cài thật: vá ``subprocess.Popen``.
"""
from __future__ import annotations

import hashlib
import io
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps import app_update as au
from apps import app_updater as up

PAYLOAD = b"MZ fake installer " * 1000
SHA = hashlib.sha256(PAYLOAD).hexdigest()
VERSION = "9.0.0"
NAME = au.windows_asset_name(VERSION)
URL = f"https://github.com/{au.RELEASES_REPO}/releases/download/{VERSION}/{NAME}"


def asset(**over):
    a = {"name": NAME, "browser_download_url": URL, "size": len(PAYLOAD), "digest": f"sha256:{SHA}"}
    a.update(over)
    return a


# ── Chọn bộ cài từ phản hồi GitHub ──────────────────────────────────────────

def test_chon_dung_bo_cai_windows_cua_ban_moi():
    other = asset(name=f"CIT-Voice-Studio-v{VERSION}-amd64.deb")
    got = au.pick_installer([other, asset()], VERSION)
    assert got == {"name": NAME, "url": URL, "size": len(PAYLOAD), "sha256": SHA}
    assert au.pick_installer([asset()], "v9.0.0")["name"] == NAME


@pytest.mark.parametrize("bad", [
    {"name": "CIT-Voice-Studio-v8.0.0-win-x86_64.exe"},                      # bản khác
    {"browser_download_url": "https://evil.example/" + NAME},                 # ngoài kho
    {"browser_download_url": "https://github.com/other/repo/releases/download/9.0.0/" + NAME},
    {"digest": None},                                                         # thiếu mã
    {"digest": "md5:abc"},
    {"size": 0},
])
def test_khong_tu_cap_nhat_khi_bo_cai_dang_ngo(bad):
    assert au.pick_installer([asset(**bad)], VERSION) is None


# ── Tải về + cài ────────────────────────────────────────────────────────────

class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(au, "config_path", lambda: tmp_path / "update-check.json")
    monkeypatch.setattr(up, "updates_dir", lambda: tmp_path / "updates")
    monkeypatch.setattr(up, "supported", lambda: True)
    monkeypatch.setattr(up, "DISK_MARGIN_BYTES", 0)
    up._set(state="idle")
    served = {"body": PAYLOAD}
    monkeypatch.setattr(up.urllib.request, "urlopen",
                        lambda req, **kw: FakeResponse(served["body"]))
    au._write({"latest": {"version": VERSION, "url": au.RELEASES_PAGE,
                          "installer": au.pick_installer([asset()], VERSION)}})
    app = FastAPI()
    app.include_router(up.router)
    client = TestClient(app, base_url="http://127.0.0.1:8001")
    client.served = served
    client.dir = tmp_path / "updates"
    return client


def wait_done(client):
    for _ in range(200):
        state = client.get("/api/app/update/download").json()
        if state["state"] != "downloading":
            return state
        time.sleep(0.01)
    raise AssertionError("tải không xong")


def test_tai_ve_khop_ma_thi_san_sang_cai(env):
    assert env.post("/api/app/update/download").status_code == 202
    state = wait_done(env)
    assert state["state"] == "ready" and state["downloaded"] == len(PAYLOAD)
    assert (env.dir / NAME).read_bytes() == PAYLOAD
    assert not list(env.dir.glob("*.part"))


def test_file_tai_ve_sai_ma_thi_xoa_va_bao_loi(env):
    env.served["body"] = PAYLOAD[:-1] + b"X"          # cùng cỡ, khác nội dung
    env.post("/api/app/update/download")
    state = wait_done(env)
    assert state["state"] == "error" and "mã kiểm tra" in state["error"]
    assert not (env.dir / NAME).exists() and not list(env.dir.glob("*.part"))


def test_khong_tai_khi_ban_da_luu_khong_moi_hon(env):
    au._write({"latest": {"version": "0.0.1", "installer": None}})
    assert env.post("/api/app/update/download").status_code == 409


def test_cai_chay_bo_cai_im_lang_roi_thoat_app(env, monkeypatch):
    calls, quits = [], []
    monkeypatch.setattr(up.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(up, "quit_handler", lambda: quits.append(1))
    monkeypatch.setattr(up.threading, "Timer", lambda delay, fn: type("T", (), {"start": lambda self: fn()})())
    assert env.post("/api/app/update/install").status_code == 409   # chưa tải
    env.post("/api/app/update/download")
    wait_done(env)
    r = env.post("/api/app/update/install")
    assert r.status_code == 202, r.text
    cmd = calls[0]
    assert cmd[0] == str(env.dir / NAME)
    assert {"/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"} <= set(cmd)
    assert quits == [1]


def test_file_bi_sua_sau_khi_tai_thi_khong_chay(env, monkeypatch):
    calls = []
    monkeypatch.setattr(up.subprocess, "Popen", lambda cmd, **kw: calls.append(cmd))
    env.post("/api/app/update/download")
    wait_done(env)
    (env.dir / NAME).write_bytes(PAYLOAD[:-1] + b"Y")
    r = env.post("/api/app/update/install")
    assert r.status_code == 409 and calls == []
    assert not (env.dir / NAME).exists()


def test_trang_web_la_khong_kich_hoat_duoc_cap_nhat(env):
    r = env.post("/api/app/update/download", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_ban_khong_ho_tro_thi_bao_mo_trang_tai(env, monkeypatch):
    monkeypatch.setattr(up, "supported", lambda: False)
    assert env.post("/api/app/update/download").status_code == 409
    assert au._result(au.cached_latest(), checked_at=None)["installable"] is False


def test_supported_chi_khi_ban_cai_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(up, "quit_handler", lambda: None)
    monkeypatch.setattr(up.sys, "frozen", True, raising=False)
    monkeypatch.setattr(up.sys, "platform", "win32")
    monkeypatch.setattr(up, "_install_dir", lambda: tmp_path)
    assert up.supported() is False                    # chạy từ zip / thư mục, không có uninstaller
    (tmp_path / "unins000.exe").write_bytes(b"")
    assert up.supported() is True
    monkeypatch.setattr(up.sys, "platform", "linux")
    assert up.supported() is False


def test_don_bo_cai_da_dung_nhung_giu_ban_moi_hon_va_nhat_ky(env, monkeypatch):
    env.dir.mkdir(parents=True, exist_ok=True)
    for name in ("CIT-Voice-Studio-v0.0.1-win-x86_64.exe", "x.part", NAME, up.INSTALL_LOG):
        (env.dir / name).write_bytes(b"x")
    up.cleanup_after_update()
    assert sorted(p.name for p in env.dir.iterdir()) == sorted([NAME, up.INSTALL_LOG])
