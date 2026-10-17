"""App construction and the middleware's edge cases."""

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.api.middleware import RequestContextMiddleware
from app.main import create_app


def test_app_builds_its_own_database_engine_and_closes_it(monkeypatch):
    """Without an injected session factory the app uses DATABASE_URL and disposes the engine."""
    disposed = []
    real_dispose = sa.Engine.dispose

    def tracking_dispose(self, *args, **kwargs):
        disposed.append(self)
        return real_dispose(self, *args, **kwargs)

    monkeypatch.setattr(sa.Engine, "dispose", tracking_dispose)

    with TestClient(create_app()) as client:  # no connection is made: /health needs no database
        assert client.get("/health").json() == {"status": "ok"}

    assert len(disposed) == 1


def test_member_name_can_be_changed_on_its_own(api):
    member = api.make_member(name="Asha Rao", phone="+91 00000 20001")

    response = api.patch(f"/members/{member['id']}", json={"name": "Asha R. Menon"})

    assert response.json()["name"] == "Asha R. Menon"
    assert response.json()["phone"] == "+91 00000 20001"


@pytest.mark.anyio
async def test_a_failure_after_the_response_started_is_not_hidden():
    """Once headers are sent a clean 500 is impossible, so the error must still surface."""
    sent = []

    async def app_that_fails_midway(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("failed after the headers went out")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    middleware = RequestContextMiddleware(app_that_fails_midway)
    scope = {"type": "http", "method": "GET", "path": "/x", "headers": []}

    with pytest.raises(RuntimeError, match="after the headers"):
        await middleware(scope, receive, send)

    assert sent[0]["status"] == 200
    assert any(name == b"x-request-id" for name, _ in sent[0]["headers"])
