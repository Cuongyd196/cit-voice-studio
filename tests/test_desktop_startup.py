import socket
from unittest.mock import Mock

from apps import desktop_app as desktop


def test_sessions_reserve_distinct_ports_and_survive_other_session_close():
    first = desktop._reserve_backend_socket(0)
    second = None
    try:
        port = first.getsockname()[1]
        second = desktop._reserve_backend_socket(port)
        assert second.getsockname()[1] != port
        first.close()
        with socket.create_connection(second.getsockname(), timeout=1):
            connection, _ = second.accept()
            connection.close()
    finally:
        first.close()
        if second is not None:
            second.close()


def test_dead_backend_cannot_pass_health_check(monkeypatch):
    probe = Mock(return_value={"engine": "test", "sample_rate": 24000})
    monkeypatch.setattr(desktop, "_probe_health", probe)
    thread = Mock()
    thread.is_alive.return_value = False
    assert not desktop.wait_for_server("http://127.0.0.1:8001", thread=thread)
    probe.assert_not_called()


def test_waits_through_initial_connection_failure(monkeypatch):
    monkeypatch.setattr(desktop, "_probe_health", Mock(side_effect=[None, {"status": "loading"}]))
    monkeypatch.setattr(desktop.time, "sleep", lambda _: None)
    thread = Mock()
    thread.is_alive.return_value = True
    assert desktop.wait_for_server("http://127.0.0.1:8001", thread=thread)


def test_backend_failure_closes_reserved_port(monkeypatch):
    import sys
    from types import SimpleNamespace

    monkeypatch.setitem(sys.modules, "apps.web_stream", SimpleNamespace(app=object()))
    monkeypatch.setattr(desktop, "_BACKEND_ERROR", None)
    server = Mock()
    server.run.side_effect = RuntimeError("startup failed")
    monkeypatch.setattr(desktop.uvicorn, "Server", Mock(return_value=server))
    listener = desktop._reserve_backend_socket(0)
    desktop.run_backend(listener)
    assert listener.fileno() == -1
    assert str(desktop._BACKEND_ERROR) == "startup failed"
    server.run.assert_called_once_with(sockets=[listener])


def test_uvicorn_serves_health_on_reserved_socket():
    import threading

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b'{"engine":"test","sample_rate":24000}'})

    listener = desktop._reserve_backend_socket(0)
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    server = desktop.uvicorn.Server(desktop.uvicorn.Config(app, lifespan="off", log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    try:
        assert desktop.wait_for_server(url, timeout=5, thread=thread)
        assert desktop._probe_health(url)["engine"] == "test"
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        listener.close()
    assert not thread.is_alive()


def test_posix_listener_reuses_port_left_in_time_wait(monkeypatch):
    # Linux/macOS: tắt app xong cổng còn TIME_WAIT ~60 giây; thiếu SO_REUSEADDR thì
    # mở lại (hay nút Khởi động lại) bị đẩy sang 8002 và client API gọi 8001 hỏng.
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    listener = desktop._reserve_backend_socket(0)
    try:
        assert listener.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
    finally:
        listener.close()
