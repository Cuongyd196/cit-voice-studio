import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps import server_settings as settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "settings_path", lambda: tmp_path / "server-settings.json")
    monkeypatch.delenv("PORT", raising=False)
    app = FastAPI()
    app.include_router(settings.router)
    with TestClient(app, base_url="http://127.0.0.1:8001") as client:
        yield client


def test_default_and_environment(client, monkeypatch):
    assert settings.setup_port() == 8001
    monkeypatch.setenv("PORT", "9000")
    assert settings.setup_port() == 9000


def test_saved_port_survives_restart_without_changing_listener(client, monkeypatch):
    response = client.put("/api/settings/server-port", json={"port": 9001})
    assert response.status_code == 200
    assert response.json() == {"port": 9001, "active_port": 8001}
    assert os.environ["PORT"] == "9001"
    monkeypatch.delenv("PORT")
    assert settings.setup_port() == 9001
    assert client.get("/api/settings/server-port").json()["active_port"] == 8001
    assert client.put("/api/settings/server-port", json={"port": 8001}).status_code == 200
    monkeypatch.delenv("PORT")
    assert settings.setup_port() == 8001


@pytest.mark.parametrize("port", [0, -1, 65536, 8001.5, True, "9000", None])
def test_rejects_invalid_port_without_saving(client, port):
    assert client.put("/api/settings/server-port", json={"port": port}).status_code == 422
    assert not settings.settings_path().exists()


def test_corrupt_file_and_invalid_environment_fall_back(client, monkeypatch):
    settings.settings_path().write_text("broken", encoding="utf-8")
    monkeypatch.setenv("PORT", "invalid")
    assert settings.setup_port() == 8001


def test_write_failure_is_reported_and_keeps_previous_port(client, monkeypatch):
    settings.save_port(9001)
    monkeypatch.setattr(settings.os, "replace", lambda *_: (_ for _ in ()).throw(PermissionError()))
    assert client.put("/api/settings/server-port", json={"port": 9002}).status_code == 500
    assert settings.configured_port() == 9001
    assert os.environ["PORT"] == "9001"


def test_restart_unsupported_without_desktop_shell(client, monkeypatch):
    monkeypatch.setattr(settings, "restart_handler", None)
    assert client.get("/api/app/restart").json() == {"supported": False}
    assert client.post("/api/app/restart").status_code == 409


def test_restart_calls_handler_after_responding(client, monkeypatch):
    import threading

    called = threading.Event()
    monkeypatch.setattr(settings, "restart_handler", called.set)
    assert client.get("/api/app/restart").json() == {"supported": True}
    response = client.post("/api/app/restart")
    assert response.status_code == 202
    assert called.wait(3)


def test_foreign_page_cannot_restart_app(client, monkeypatch):
    called = []
    monkeypatch.setattr(settings, "restart_handler", lambda: called.append(1))
    response = client.post("/api/app/restart", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert called == []
