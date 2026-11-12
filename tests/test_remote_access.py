import json

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from apps import remote_access as ra

LAN = ("192.168.1.20", 50000)
LOCAL = ("127.0.0.1", 50000)


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "remote-access.json"
    monkeypatch.setattr(ra, "config_path", lambda: path)
    monkeypatch.delenv(ra.LISTEN_ENV, raising=False)
    ra.reset_cache()
    yield path
    ra.reset_cache()


def _app():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(ra.RemoteAccessMiddleware)
    app.include_router(ra.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/tts/generate")
    def generate():
        return {"ok": True}

    @app.get("/api/history")
    def history():
        return []

    @app.get("/openapi-like")
    def other():
        return {}

    return app


def _client(peer, **kw):
    return TestClient(_app(), client=peer, base_url="http://127.0.0.1:8001", **kw)


def _enable():
    return ra._update(enabled=True)


def test_first_read_creates_key_and_defaults_off(cfg):
    state = ra.current()
    assert state["enabled"] is False
    assert state["api_key"].startswith("cit_") and len(state["api_key"]) > 30
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved == state
    ra.reset_cache()
    assert ra.current()["api_key"] == state["api_key"]  # khoa giu nguyen sau khi mo lai app


def test_corrupt_file_falls_back_to_off(cfg):
    cfg.write_text("{hong", encoding="utf-8")
    assert ra.current()["enabled"] is False


def test_local_requests_untouched_without_key(cfg):
    c = _client(LOCAL)
    assert c.get("/health").status_code == 200
    assert c.get("/api/history").status_code == 200


def test_remote_blocked_when_disabled(cfg):
    r = _client(LAN).get("/health")
    assert r.status_code == 403
    assert "đang tắt" in r.json()["detail"]


def test_remote_needs_key(cfg):
    key = _enable()["api_key"]
    c = _client(LAN)
    assert c.get("/health").status_code == 401
    assert c.get("/health", headers={"X-API-Key": "sai"}).status_code == 401
    assert c.get("/health", headers={"X-API-Key": key}).status_code == 200
    assert c.get("/health", headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert c.get(f"/health?api_key={key}").status_code == 200
    assert c.post("/api/tts/generate", headers={"X-API-Key": key}).status_code == 200


def test_remote_cannot_reach_internal_api_even_with_key(cfg):
    key = _enable()["api_key"]
    c = _client(LAN)
    for path in ("/api/history", "/api/remote-access", "/", "/openapi-like"):
        assert c.get(path, headers={"X-API-Key": key}).status_code == 404, path
    assert c.post("/api/remote-access/regenerate-key", headers={"X-API-Key": key}).status_code == 404


def test_proxy_forwarded_request_counts_as_remote(cfg):
    # ngrok / Cloudflare Tunnel ket noi tu 127.0.0.1 nhung mang header chuyen tiep.
    c = _client(LOCAL)
    assert c.get("/health", headers={"X-Forwarded-For": "8.8.8.8"}).status_code == 403
    key = _enable()["api_key"]
    assert c.get("/api/history", headers={"X-Forwarded-For": "8.8.8.8", "X-API-Key": key}).status_code == 404
    assert c.get("/health", headers={"Forwarded": "for=1.2.3.4", "X-API-Key": key}).status_code == 200


def test_ipv4_mapped_loopback_is_local(cfg):
    assert _client(("::ffff:127.0.0.1", 1)).get("/api/history").status_code == 200
    assert _client(("::1", 1)).get("/api/history").status_code == 200


def test_cors_preflight_passes_without_key(cfg):
    _enable()
    r = _client(LAN).options(
        "/api/tts/generate",
        headers={"Origin": "http://192.168.1.20:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"]


def test_error_responses_readable_by_browsers(cfg):
    r = _client(LAN).get("/health")
    assert r.headers["access-control-allow-origin"] == "*"


def test_disable_takes_effect_immediately(cfg):
    key = _enable()["api_key"]
    c = _client(LAN)
    assert c.get("/health", headers={"X-API-Key": key}).status_code == 200
    assert _client(LOCAL).put("/api/remote-access", json={"enabled": False}).status_code == 200
    assert c.get("/health", headers={"X-API-Key": key}).status_code == 403


def test_settings_api_toggle_and_regenerate(cfg):
    c = _client(LOCAL)
    body = c.get("/api/remote-access").json()
    assert body["enabled"] is False and body["listening_all"] is False
    assert body["port"] == 8001 and isinstance(body["addresses"], list)
    old = body["api_key"]
    assert c.put("/api/remote-access", json={"enabled": True}).json()["enabled"] is True
    new = c.post("/api/remote-access/regenerate-key").json()["api_key"]
    assert new != old
    lan = _client(LAN)
    assert lan.get("/health", headers={"X-API-Key": old}).status_code == 401
    assert lan.get("/health", headers={"X-API-Key": new}).status_code == 200
    ra.reset_cache()
    assert ra.current() == {"enabled": True, "api_key": new}


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "http://192.168.1.50:8001"},
        {"Host": "evil.example:8001"},  # DNS rebinding
    ],
)
def test_foreign_web_pages_cannot_read_or_change_key(cfg, headers):
    c = _client(LOCAL)
    assert c.get("/api/remote-access", headers=headers).status_code == 403
    assert c.put("/api/remote-access", json={"enabled": True}, headers=headers).status_code == 403
    assert ra.current()["enabled"] is False


@pytest.mark.parametrize(
    "origin", ["http://127.0.0.1:8001", "http://localhost:1420"]
)
def test_app_origins_allowed(cfg, origin):
    assert _client(LOCAL).get("/api/remote-access", headers={"Origin": origin}).status_code == 200


def test_listen_host_follows_setting(cfg):
    assert ra.listen_host() == "127.0.0.1"
    _enable()
    assert ra.listen_host() == "0.0.0.0"
    ra.mark_listening("0.0.0.0")
    assert ra.is_listening_all()


def test_public_paths_match_openapi():
    from apps.web_stream import app

    documented = set(app.openapi()["paths"]) - {"/cit-voice-studio.md"}
    assert documented == set(ra.PUBLIC_PATHS)
