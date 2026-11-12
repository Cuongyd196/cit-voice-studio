import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps import history_store as hs


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "history_dir", lambda: tmp_path / "history")
    app = FastAPI()
    app.include_router(hs.router)
    with TestClient(app) as c:
        yield c


def add(client, text="Xin chào", audio=b"RIFFdata", fmt="wav", subtitles=None, **extra):
    data = {"text": text, "voice_id": "Minh Đức", "voice_name": "Minh Đức",
            "duration_seconds": "1.5", "format": fmt, "mode": "tts", **extra}
    if subtitles is not None:
        data["subtitles"] = subtitles
    return client.post("/api/history", data=data, files={"audio": ("a." + fmt, audio)})


def test_add_list_get_audio_survives_restart(client):
    r = add(client)
    assert r.status_code == 200
    e = r.json()
    assert e["text"] == "Xin chào" and e["duration_seconds"] == 1.5
    assert client.get(e["audio_url"]).content == b"RIFFdata"
    # "Khởi động lại": đọc lại từ đĩa qua một client mới.
    app = FastAPI()
    app.include_router(hs.router)
    entries = TestClient(app).get("/api/history").json()["entries"]
    assert [x["id"] for x in entries] == [e["id"]]


def test_newest_first_and_mp3(client):
    a = add(client, text="một").json()
    b = add(client, text="hai", audio=b"ID3", fmt="mp3").json()
    ids = [x["id"] for x in client.get("/api/history").json()["entries"]]
    assert ids == [b["id"], a["id"]]
    r = client.get(b["audio_url"])
    assert r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3"


def test_subtitles_stored_and_served(client):
    srt = "1\n00:00:00,000 --> 00:00:01,000\nXin chào\n"
    e = add(client, subtitles=srt).json()
    assert e["has_subtitles"]
    assert client.get(e["subtitles_url"]).text == srt
    plain = add(client).json()
    assert "subtitles_url" not in plain
    assert client.get(f"/api/history/{plain['id']}/subtitles.srt").status_code == 404


def test_delete_one_and_clear_remove_files(client, tmp_path):
    a = add(client, subtitles="x").json()
    b = add(client).json()
    assert client.delete(f"/api/history/{a['id']}").status_code == 200
    assert not (tmp_path / "history" / f"{a['id']}.wav").exists()
    assert not (tmp_path / "history" / f"{a['id']}.srt").exists()
    assert [x["id"] for x in client.get("/api/history").json()["entries"]] == [b["id"]]
    assert client.delete("/api/history").json()["deleted"] == 1
    assert client.get("/api/history").json()["entries"] == []
    assert sorted(p.name for p in (tmp_path / "history").iterdir()) == ["index.json"]


def test_never_deletes_automatically(client, monkeypatch):
    # Trước đây vượt 300 bài / 1 GB thì xoá bài cũ nhất — kể cả bài vừa tạo nếu nó > 1 GB.
    monkeypatch.setattr(hs, "WARN_BYTES", 20)
    ids = [add(client, text=str(i), audio=b"x" * 15).json()["id"] for i in range(3)]
    kept = [x["id"] for x in client.get("/api/history").json()["entries"]]
    assert kept == ids[::-1]
    info = client.get("/api/history/info").json()
    assert info["count"] == 3 and info["bytes"] == 45 and info["warn"] is True


def test_info_reports_size_folder_and_disk(client, tmp_path):
    info = client.get("/api/history/info").json()
    assert info == {"count": 0, "bytes": 0, "folder": str(tmp_path / "history"),
                    "disk_free": info["disk_free"], "warn": False}
    assert info["disk_free"] > 0
    add(client, audio=b"x" * 10)
    info = client.get("/api/history/info").json()
    assert info["count"] == 1 and info["bytes"] == 10


def test_low_disk_warns(client, monkeypatch):
    monkeypatch.setattr(hs, "LOW_DISK_BYTES", 1 << 62)
    assert client.get("/api/history/info").json()["warn"] is True


def test_open_folder(client, monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(hs.os, "startfile", opened.append, raising=False)
    monkeypatch.setattr(hs.subprocess, "Popen", lambda args: opened.append(args[-1]))
    assert client.post("/api/history/open-folder").json()["path"] == str(tmp_path / "history")
    assert [str(p) for p in opened] == [str(tmp_path / "history")]


@pytest.mark.parametrize("bad", ["../index", "abc", "..%2F..%2Fx", "0" * 31])
def test_invalid_ids_are_404(client, bad):
    assert client.get(f"/api/history/{bad}/audio").status_code == 404
    assert client.delete(f"/api/history/{bad}").status_code == 404


def test_rejects_bad_input(client):
    assert add(client, fmt="ogg").status_code == 400
    assert add(client, audio=b"").status_code == 400


def test_corrupt_index_not_overwritten_on_read(client, tmp_path):
    d = tmp_path / "history"
    d.mkdir()
    (d / "index.json").write_text("{broken", encoding="utf-8")
    assert client.get("/api/history").json()["entries"] == []
    assert (d / "index.json").read_text(encoding="utf-8") == "{broken"


def test_unknown_mode_falls_back(client):
    assert add(client, mode="hack").json()["mode"] == "tts"
    assert json.loads((hs.history_dir() / "index.json").read_text(encoding="utf-8"))["version"] == 1


def test_friendly_file_names(client, tmp_path):
    e = add(client, subtitles="1\n00:00:00,000 --> 00:00:01,000\nA\n").json()
    names = sorted(p.name for p in (tmp_path / "history").iterdir() if p.name != "index.json")
    assert len(names) == 2
    stem = names[0].rsplit(".", 1)[0]
    assert stem.endswith(f"_Minh Đức_{e['id'][:8]}")
    assert {n.rsplit(".", 1)[1] for n in names} == {"srt", "wav"}
    assert client.get(e["audio_url"]).content == b"RIFFdata"


def test_bad_voice_name_chars_removed(client, tmp_path):
    add(client, voice_name=r'a/b\c:d*?"<>|e')
    wav = next((tmp_path / "history").glob("*.wav"))
    assert "_abcde_" in wav.name


def test_old_entries_without_file_field_still_work(client, tmp_path):
    # Muc luu truoc khi co ten de doc: file dat theo id, index khong co "file".
    d = tmp_path / "history"
    d.mkdir()
    old_id = "a" * 32
    (d / f"{old_id}.wav").write_bytes(b"OLD")
    (d / "index.json").write_text(json.dumps({"version": 1, "entries": [
        {"id": old_id, "text": "cũ", "format": "wav", "timestamp": 1, "size": 3}]}), encoding="utf-8")
    assert client.get(f"/api/history/{old_id}/audio").content == b"OLD"
    assert client.delete(f"/api/history/{old_id}").status_code == 200
    assert not (d / f"{old_id}.wav").exists()


def test_tampered_file_field_cannot_escape_dir(client, tmp_path):
    d = tmp_path / "history"
    d.mkdir()
    victim = tmp_path / "victim.wav"
    victim.write_bytes(b"KEEP")
    eid = "b" * 32
    (d / "index.json").write_text(json.dumps({"version": 1, "entries": [
        {"id": eid, "file": "../victim", "format": "wav", "timestamp": 1, "size": 1}]}), encoding="utf-8")
    assert client.get(f"/api/history/{eid}/audio").status_code == 404
    client.delete(f"/api/history/{eid}")
    assert victim.read_bytes() == b"KEEP"


def test_reveal_opens_folder_with_file_selected(client, monkeypatch):
    opened = []
    monkeypatch.setattr(hs, "_reveal", opened.append)
    e = add(client).json()
    r = client.post(f"/api/history/{e['id']}/reveal")
    assert r.status_code == 200
    assert len(opened) == 1 and opened[0].name.endswith(".wav") and opened[0].exists()
    assert client.post(f"/api/history/{'c' * 32}/reveal").status_code == 404
    assert client.post("/api/history/..%2F/reveal").status_code == 404
