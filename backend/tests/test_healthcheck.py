"""The container's HEALTHCHECK command, against a tiny local server."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import healthcheck


@pytest.fixture
def serve_health():
    servers = []

    def start(status: int) -> int:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status if self.path == "/health" else 404)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server.server_address[1]

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_healthy_when_health_answers_200(serve_health):
    assert healthcheck.is_healthy(serve_health(200)) is True


def test_unhealthy_when_health_answers_an_error(serve_health):
    assert healthcheck.is_healthy(serve_health(503)) is False


def test_unhealthy_when_nothing_is_listening():
    with socket.socket() as sock:  # bind to find a free port, then release it
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]

    assert healthcheck.is_healthy(closed_port, timeout=1) is False


def test_main_exits_with_the_result(serve_health, monkeypatch):
    monkeypatch.setenv("PORT", str(serve_health(200)))
    with pytest.raises(SystemExit) as ok:
        healthcheck.main()
    assert ok.value.code == 0

    monkeypatch.setenv("PORT", str(serve_health(500)))
    with pytest.raises(SystemExit) as bad:
        healthcheck.main()
    assert bad.value.code == 1
